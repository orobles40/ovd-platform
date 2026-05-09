"""
OVD Platform — Knowledge Chunkers (Sprint 8)
Copyright 2026 Omar Robles

Estrategias de chunking por tipo de documento.

Cada chunker recibe una ruta (archivo o directorio) y devuelve
una lista de Chunk con el texto y metadatos relevantes para el RAG.
"""
from __future__ import annotations

import ast
import json
import logging
import pathlib
import re
from dataclasses import dataclass, field
from typing import Iterator

log = logging.getLogger(__name__)

# Tamaño máximo de chunk en caracteres (aprox. 400-600 tokens)
_MAX_CHUNK_CHARS = 2000
# Overlap entre chunks para no perder contexto entre bloques
_CHUNK_OVERLAP = 200


@dataclass
class Chunk:
    """Unidad mínima de conocimiento para indexar en el RAG."""
    content: str
    doc_type: str                        # codebase | doc | schema | contract | ticket
    source_file: str                     # ruta relativa del archivo origen
    metadata: dict = field(default_factory=dict)
    # Metadatos específicos por tipo
    # codebase: {"language": "python", "symbol": "MyClass.method", "kind": "function"}
    # schema:   {"table": "users", "kind": "table|view|procedure"}
    # contract: {"method": "POST", "path": "/api/users", "operation_id": "createUser"}
    # doc:      {"section": "Introducción", "page": 1}
    # ticket:   {"ticket_id": "JIRA-123", "status": "done", "type": "story"}


# ---------------------------------------------------------------------------
# Codebase chunker — AST-based para Python
# ---------------------------------------------------------------------------

def _chunk_python_file(path: pathlib.Path, rel_path: str) -> list[Chunk]:
    """
    Extrae funciones, clases y métodos de un archivo Python usando el AST.
    Cada símbolo se convierte en un chunk independiente con su docstring y código.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        log.warning("chunkers: error AST en %s — %s — usando chunking por líneas", rel_path, e)
        return _chunk_by_lines(source, "codebase", rel_path, {"language": "python"})

    chunks: list[Chunk] = []
    lines = source.splitlines(keepends=True)

    def _extract(node: ast.AST, parent_name: str = "") -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = f"{parent_name}.{node.name}" if parent_name else node.name
            start = node.lineno - 1
            end = node.end_lineno or (start + 1)
            symbol_src = "".join(lines[start:end])

            if len(symbol_src) > _MAX_CHUNK_CHARS:
                # Si el símbolo es muy grande, lo partimos conservando el header
                header_end = min(start + 20, end)
                header = "".join(lines[start:header_end])
                for sub_chunk in _split_text(symbol_src[len(header):], _MAX_CHUNK_CHARS - len(header)):
                    chunks.append(Chunk(
                        content=header + sub_chunk,
                        doc_type="codebase",
                        source_file=rel_path,
                        metadata={"language": "python", "symbol": name, "kind": type(node).__name__.lower()},
                    ))
            else:
                chunks.append(Chunk(
                    content=symbol_src,
                    doc_type="codebase",
                    source_file=rel_path,
                    metadata={"language": "python", "symbol": name, "kind": type(node).__name__.lower()},
                ))

            # Recursivo para métodos dentro de clases
            if isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    _extract(child, name)

    for node in ast.iter_child_nodes(tree):
        _extract(node)

    # Si no encontramos símbolos (archivo de solo imports/configs), chunk completo
    if not chunks:
        chunks.extend(_chunk_by_lines(source, "codebase", rel_path, {"language": "python"}))

    return chunks


def _chunk_generic_code(path: pathlib.Path, rel_path: str, language: str) -> list[Chunk]:
    """
    Chunking por líneas para lenguajes sin parser AST disponible
    (TypeScript, Java, Go, SQL genérico, etc.).
    Intenta detectar bloques de función/clase por indentación y llaves.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log.warning("chunkers: no se pudo leer %s — %s", rel_path, e)
        return []
    return _chunk_by_lines(source, "codebase", rel_path, {"language": language})


_EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".sql": "sql",
    ".kt": "kotlin",
    ".swift": "swift",
}

_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".next", "dist", "build"}
_SKIP_EXTENSIONS = {".min.js", ".map", ".lock", ".pyc", ".class", ".jar", ".war", ".exe", ".bin"}


def chunk_codebase(source_path: pathlib.Path) -> Iterator[Chunk]:
    """
    Itera sobre todos los archivos de código de un directorio y genera chunks.
    Salta directorios de dependencias (.venv, node_modules, etc.).
    """
    if source_path.is_file():
        files: list[pathlib.Path] = [source_path]
        base = source_path.parent
    else:
        files = []
        base = source_path
        for p in source_path.rglob("*"):
            if p.is_file() and not any(part in _SKIP_DIRS for part in p.parts):
                if not any(str(p).endswith(ext) for ext in _SKIP_EXTENSIONS):
                    files.append(p)

    for file_path in sorted(files):
        ext = "".join(file_path.suffixes).lower()
        if ext not in _EXTENSION_LANGUAGE_MAP:
            continue
        language = _EXTENSION_LANGUAGE_MAP[ext]
        rel_path = str(file_path.relative_to(base))
        if language == "python":
            yield from _chunk_python_file(file_path, rel_path)
        else:
            yield from _chunk_generic_code(file_path, rel_path, language)


# ---------------------------------------------------------------------------
# Schema chunker — DDL (PostgreSQL, Oracle, MySQL)
# ---------------------------------------------------------------------------

_DDL_OBJECT_RE = re.compile(
    r"(CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|INDEX|PROCEDURE|FUNCTION|TRIGGER|SEQUENCE|TYPE)\b)",
    re.IGNORECASE,
)
_DDL_NAME_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|INDEX|PROCEDURE|FUNCTION|TRIGGER|SEQUENCE|TYPE)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?(?:[`\"\[]?(\w+)[`\"\]]?\.)?[`\"\[]?(\w+)[`\"\]]?",
    re.IGNORECASE,
)


def chunk_schema(source_path: pathlib.Path) -> Iterator[Chunk]:
    """
    Divide un archivo DDL en chunks por objeto (tabla, vista, procedimiento, etc.).
    Cada objeto DDL se convierte en un chunk independiente.
    """
    if source_path.is_dir():
        sql_files = sorted(source_path.rglob("*.sql"))
    else:
        sql_files = [source_path]

    for sql_file in sql_files:
        try:
            content = sql_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            log.warning("chunkers: no se pudo leer %s — %s", sql_file, e)
            continue

        # Dividir por sentencias CREATE
        parts = _DDL_OBJECT_RE.split(content)
        # split con capture group alterna entre separadores y contenidos
        i = 0
        while i < len(parts):
            part = parts[i].strip()
            if not part:
                i += 1
                continue
            # Si es el keyword CREATE, unirlo con el siguiente fragmento
            if _DDL_OBJECT_RE.match(part) and i + 1 < len(parts):
                statement = part + parts[i + 1]
                i += 2
            else:
                statement = part
                i += 1

            if len(statement.strip()) < 20:
                continue

            # Extraer nombre del objeto
            name_match = _DDL_NAME_RE.search(statement)
            obj_name = name_match.group(2) if name_match else "unknown"

            # Detectar tipo
            kind_match = re.search(
                r"CREATE\s+(?:OR\s+REPLACE\s+)?(TABLE|VIEW|INDEX|PROCEDURE|FUNCTION|TRIGGER|SEQUENCE|TYPE)",
                statement, re.IGNORECASE,
            )
            kind = kind_match.group(1).lower() if kind_match else "statement"

            # Si el statement es muy largo, chunkearlo
            if len(statement) > _MAX_CHUNK_CHARS:
                for idx, sub in enumerate(_split_text(statement, _MAX_CHUNK_CHARS)):
                    yield Chunk(
                        content=sub,
                        doc_type="schema",
                        source_file=str(sql_file.name),
                        metadata={"table": obj_name, "kind": kind, "part": idx},
                    )
            else:
                yield Chunk(
                    content=statement.strip(),
                    doc_type="schema",
                    source_file=str(sql_file.name),
                    metadata={"table": obj_name, "kind": kind},
                )


# ---------------------------------------------------------------------------
# Contract chunker — OpenAPI/Swagger (JSON o YAML)
# ---------------------------------------------------------------------------

def chunk_contract(source_path: pathlib.Path) -> Iterator[Chunk]:
    """
    Divide una spec OpenAPI en chunks por endpoint (método + path).
    Cada operación (GET /users, POST /orders, etc.) es un chunk independiente.
    """
    import yaml  # opcional — graceful fail si no está instalado

    if source_path.is_dir():
        files = sorted(
            list(source_path.rglob("*.json")) +
            list(source_path.rglob("*.yaml")) +
            list(source_path.rglob("*.yml"))
        )
    else:
        files = [source_path]

    for spec_file in files:
        try:
            raw = spec_file.read_text(encoding="utf-8", errors="replace")
            if spec_file.suffix in (".yaml", ".yml"):
                spec = yaml.safe_load(raw)
            else:
                spec = json.loads(raw)
        except Exception as e:
            log.warning("chunkers: no se pudo parsear spec %s — %s", spec_file, e)
            continue

        if not isinstance(spec, dict) or "paths" not in spec:
            # No es OpenAPI — chunk de texto completo
            yield Chunk(
                content=raw[:_MAX_CHUNK_CHARS],
                doc_type="contract",
                source_file=str(spec_file.name),
                metadata={"kind": "raw"},
            )
            continue

        api_title = spec.get("info", {}).get("title", str(spec_file.name))
        for path, methods in spec.get("paths", {}).items():
            if not isinstance(methods, dict):
                continue
            for method, operation in methods.items():
                if method.startswith("x-") or not isinstance(operation, dict):
                    continue
                operation_id = operation.get("operationId", f"{method}_{path}")
                summary = operation.get("summary", "")
                description = operation.get("description", "")
                params = json.dumps(operation.get("parameters", []), ensure_ascii=False)
                request_body = json.dumps(operation.get("requestBody", {}), ensure_ascii=False)
                responses = json.dumps(operation.get("responses", {}), ensure_ascii=False)

                content = (
                    f"API: {api_title}\n"
                    f"Endpoint: {method.upper()} {path}\n"
                    f"OperationId: {operation_id}\n"
                    f"Summary: {summary}\n"
                    f"Description: {description}\n"
                    f"Parameters: {params[:500]}\n"
                    f"RequestBody: {request_body[:500]}\n"
                    f"Responses: {responses[:500]}\n"
                )
                yield Chunk(
                    content=content[:_MAX_CHUNK_CHARS],
                    doc_type="contract",
                    source_file=str(spec_file.name),
                    metadata={"method": method.upper(), "path": path, "operation_id": operation_id},
                )


# ---------------------------------------------------------------------------
# Doc chunker — PDF, Word, Markdown, TXT (chunking por sección)
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Z\s]{3,}:?\s*$)", re.MULTILINE)


def chunk_doc(source_path: pathlib.Path) -> Iterator[Chunk]:
    """
    Divide documentos en chunks por sección.
    Soporta: .md, .txt (nativo), .pdf (requiere pdfplumber), .docx (requiere python-docx).
    """
    if source_path.is_dir():
        files = sorted(
            list(source_path.rglob("*.md")) +
            list(source_path.rglob("*.txt")) +
            list(source_path.rglob("*.pdf")) +
            list(source_path.rglob("*.docx"))
        )
    else:
        files = [source_path]

    for doc_file in files:
        ext = doc_file.suffix.lower()
        if ext in (".md", ".txt"):
            yield from _chunk_text_doc(doc_file)
        elif ext == ".pdf":
            yield from _chunk_pdf(doc_file)
        elif ext == ".docx":
            yield from _chunk_docx(doc_file)


def _chunk_text_doc(path: pathlib.Path) -> Iterator[Chunk]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log.warning("chunkers: no se pudo leer %s — %s", path, e)
        return

    sections = _HEADING_RE.split(text)
    current_heading = str(path.name)
    for part in sections:
        part = part.strip()
        if not part:
            continue
        if _HEADING_RE.match(part):
            current_heading = part.strip("# ").strip()
            continue
        for sub_chunk in _split_text(part, _MAX_CHUNK_CHARS):
            yield Chunk(
                content=sub_chunk,
                doc_type="doc",
                source_file=str(path.name),
                metadata={"section": current_heading},
            )


def _chunk_pdf(path: pathlib.Path) -> Iterator[Chunk]:
    try:
        import pdfplumber
    except ImportError:
        log.error("chunkers: pdfplumber no instalado — no se puede procesar %s", path)
        return
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                for sub_chunk in _split_text(text.strip(), _MAX_CHUNK_CHARS):
                    yield Chunk(
                        content=sub_chunk,
                        doc_type="doc",
                        source_file=str(path.name),
                        metadata={"page": page_num},
                    )
    except Exception as e:
        log.error("chunkers: error procesando PDF %s — %s", path, e)


def _chunk_docx(path: pathlib.Path) -> Iterator[Chunk]:
    try:
        from docx import Document
    except ImportError:
        log.error("chunkers: python-docx no instalado — no se puede procesar %s", path)
        return
    try:
        doc = Document(str(path))
        current_heading = str(path.name)
        buffer: list[str] = []

        for para in doc.paragraphs:
            style_name = para.style.name.lower() if para.style else ""
            if "heading" in style_name:
                # Emitir buffer acumulado
                if buffer:
                    text = "\n".join(buffer)
                    for sub_chunk in _split_text(text, _MAX_CHUNK_CHARS):
                        yield Chunk(
                            content=sub_chunk,
                            doc_type="doc",
                            source_file=str(path.name),
                            metadata={"section": current_heading},
                        )
                    buffer = []
                current_heading = para.text.strip()
            elif para.text.strip():
                buffer.append(para.text.strip())

        # Emitir el último buffer
        if buffer:
            text = "\n".join(buffer)
            for sub_chunk in _split_text(text, _MAX_CHUNK_CHARS):
                yield Chunk(
                    content=sub_chunk,
                    doc_type="doc",
                    source_file=str(path.name),
                    metadata={"section": current_heading},
                )
    except Exception as e:
        log.error("chunkers: error procesando DOCX %s — %s", path, e)


# ---------------------------------------------------------------------------
# Ticket chunker — JSON/CSV de tickets (JIRA, Linear, etc.)
# ---------------------------------------------------------------------------

def chunk_tickets(source_path: pathlib.Path) -> Iterator[Chunk]:
    """
    Procesa exportaciones de tickets (JIRA JSON export, Linear CSV, etc.).
    Cada ticket es un chunk independiente.
    """
    if source_path.is_dir():
        files = sorted(
            list(source_path.rglob("*.json")) +
            list(source_path.rglob("*.csv"))
        )
    else:
        files = [source_path]

    for ticket_file in files:
        ext = ticket_file.suffix.lower()
        if ext == ".json":
            yield from _chunk_tickets_json(ticket_file)
        elif ext == ".csv":
            yield from _chunk_tickets_csv(ticket_file)


def _chunk_tickets_json(path: pathlib.Path) -> Iterator[Chunk]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        log.warning("chunkers: no se pudo parsear tickets JSON %s — %s", path, e)
        return

    # Soportar array directo o {issues: [...]} (formato JIRA)
    tickets = data if isinstance(data, list) else data.get("issues", data.get("tickets", []))
    for ticket in tickets:
        if not isinstance(ticket, dict):
            continue
        ticket_id = ticket.get("key") or ticket.get("id") or "unknown"
        summary = ticket.get("summary") or ticket.get("title") or ""
        description = ticket.get("description") or ticket.get("body") or ""
        status = ticket.get("status") or ticket.get("state") or ""
        ticket_type = ticket.get("issuetype", {}).get("name", "") if isinstance(ticket.get("issuetype"), dict) else ticket.get("type", "")

        content = f"Ticket: {ticket_id}\nTipo: {ticket_type}\nEstado: {status}\nTítulo: {summary}\nDescripción:\n{description}"
        yield Chunk(
            content=content[:_MAX_CHUNK_CHARS],
            doc_type="ticket",
            source_file=str(path.name),
            metadata={"ticket_id": ticket_id, "status": status, "type": ticket_type},
        )


def _chunk_tickets_csv(path: pathlib.Path) -> Iterator[Chunk]:
    import csv
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticket_id = row.get("Key") or row.get("ID") or row.get("id", "unknown")
                summary = row.get("Summary") or row.get("Title") or row.get("title", "")
                description = row.get("Description") or row.get("Body") or ""
                status = row.get("Status") or row.get("State") or ""
                content = f"Ticket: {ticket_id}\nEstado: {status}\nTítulo: {summary}\nDescripción:\n{description}"
                yield Chunk(
                    content=content[:_MAX_CHUNK_CHARS],
                    doc_type="ticket",
                    source_file=str(path.name),
                    metadata={"ticket_id": ticket_id, "status": status},
                )
    except Exception as e:
        log.warning("chunkers: no se pudo parsear tickets CSV %s — %s", path, e)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _split_text(text: str, max_chars: int) -> list[str]:
    """
    Divide texto largo en chunks de max_chars con overlap.
    Intenta cortar en saltos de línea para no partir en medio de una oración.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        # Intentar cortar en salto de línea
        if end < len(text):
            newline_pos = text.rfind("\n", start, end)
            if newline_pos > start + max_chars // 2:
                end = newline_pos + 1
        chunks.append(text[start:end])
        next_start = end - _CHUNK_OVERLAP if end < len(text) else end
        start = max(next_start, start + 1)
    return chunks


def _chunk_by_lines(
    source: str,
    doc_type: str,
    rel_path: str,
    metadata: dict,
) -> list[Chunk]:
    """Chunking simple por líneas para archivos sin parser especializado."""
    return [
        Chunk(content=sub, doc_type=doc_type, source_file=rel_path, metadata=metadata)
        for sub in _split_text(source, _MAX_CHUNK_CHARS)
        if sub.strip()
    ]


# ---------------------------------------------------------------------------
# Delivery chunker — informes ovd-delivery-*.md generados por deliver_node
# ---------------------------------------------------------------------------

_DELIVERY_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _extract_number(text: str, pattern: str) -> int | None:
    """Extrae el primer número que coincida con el patrón regex."""
    m = re.search(pattern, text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def chunk_delivery(source_path: pathlib.Path) -> Iterator[Chunk]:
    """
    Chunker especializado para informes ovd-delivery-*.md (RAG-02).

    Genera hasta 3 chunks por informe:
      1. ciclo       — FR, scores, duración, status
      2. implementacion — archivos generados por agente
      3. qa_issues   — issues de QA (solo si passed=False)

    Los metadatos ricos permiten filtrar por proyecto, score o FR en consultas RAG.
    """
    if source_path.is_dir():
        files = sorted(source_path.rglob("ovd-delivery-*.md"))
    else:
        files = [source_path]

    for report_file in files:
        try:
            text = report_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            log.warning("chunkers.delivery: no se pudo leer %s — %s", report_file, e)
            continue

        # Dividir por secciones ## del informe
        sections: dict[str, str] = {}
        parts = _DELIVERY_SECTION_RE.split(text)
        # parts[0] = contenido antes del primer ##, parts[1::2] = headings, parts[2::2] = body
        i = 1
        while i < len(parts):
            heading = parts[i].strip().lower() if i < len(parts) else ""
            body = parts[i + 1].strip() if (i + 1) < len(parts) else ""
            sections[heading] = body
            i += 2

        fname = report_file.name

        # OB-01/OB-02: parsear YAML frontmatter para metadatos estructurados
        frontmatter: dict = {}
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                fm_text = text[4:end]
                try:
                    import yaml as _yaml  # type: ignore[import]
                    frontmatter = _yaml.safe_load(fm_text) or {}
                except Exception:
                    # Parseo manual de pares clave: valor simples
                    for line in fm_text.splitlines():
                        if ": " in line:
                            k, _, v = line.partition(": ")
                            frontmatter[k.strip()] = v.strip().strip('"')

        # Metadatos combinados: frontmatter (prioritario) + regex fallback
        qa_score: int | None = (
            int(frontmatter["qa_score"]) if "qa_score" in frontmatter and frontmatter["qa_score"] is not None
            else _extract_number(text, r"QA Score\s*\|\s*(\d+)/100")
        )
        sec_score: int | None = (
            int(frontmatter["security_score"]) if "security_score" in frontmatter and frontmatter["security_score"] is not None
            else _extract_number(text, r"Security Score\s*\|\s*(\d+)/100")
        )
        qa_passed_fm = frontmatter.get("qa_passed")
        qa_passed = bool(qa_passed_fm) if qa_passed_fm is not None else ("| QA Passed | ✅" in text)

        # created_at desde frontmatter (YYYY-MM-DD) o mtime del archivo
        created_at: str | None = None
        if "date" in frontmatter:
            created_at = str(frontmatter["date"])[:10]
        else:
            try:
                import datetime
                created_at = datetime.datetime.fromtimestamp(
                    report_file.stat().st_mtime
                ).strftime("%Y-%m-%d")
            except Exception:
                pass

        session_id: str = str(frontmatter.get("session_id", ""))
        provider: str = str(frontmatter.get("provider", ""))

        # --- Chunk 1: resumen del ciclo ---
        cycle_lines = []
        for key in ("resumen", "ciclo", "summary", "estado"):
            if key in sections:
                cycle_lines.append(sections[key])
        # Incluir cabecera del archivo (primera línea = título con FR)
        header = parts[0].strip() if parts else ""
        # Omitir el bloque frontmatter del header si está presente
        if header.startswith("---"):
            end_fm = header.find("\n---", 3)
            header = header[end_fm + 4:].strip() if end_fm != -1 else ""
        cycle_content = f"{header}\n\n" + "\n\n".join(cycle_lines) if cycle_lines else header

        if cycle_content.strip():
            meta: dict = {"kind": "ciclo", "qa_score": qa_score, "security_score": sec_score}
            if created_at:
                meta["created_at"] = created_at
            if session_id:
                meta["session_id"] = session_id
            if provider:
                meta["provider"] = provider
            yield Chunk(
                content=cycle_content[:_MAX_CHUNK_CHARS],
                doc_type="delivery",
                source_file=fname,
                metadata=meta,
            )

        # --- Chunk 2: archivos de implementación ---
        impl_body = ""
        for key in ("archivos generados", "implementación", "artefactos", "files", "archivos", "archivos generados"):
            if key in sections:
                impl_body = sections[key]
                break
        if impl_body.strip():
            yield Chunk(
                content=impl_body[:_MAX_CHUNK_CHARS],
                doc_type="delivery",
                source_file=fname,
                metadata={"kind": "implementacion"},
            )

        # --- Chunk 3: auditoría (scores + compliance) ---
        qa_body = ""
        for key in ("resultados de auditoría", "auditoría", "issues de calidad", "qa issues", "issues qa", "qa"):
            if key in sections:
                qa_body = sections[key]
                break
        if qa_body.strip():
            yield Chunk(
                content=qa_body[:_MAX_CHUNK_CHARS],
                doc_type="delivery",
                source_file=fname,
                metadata={"kind": "qa_issues", "qa_passed": qa_passed},
            )


# ---------------------------------------------------------------------------
# Dispatcher principal
# ---------------------------------------------------------------------------

DOC_TYPE_CHUNKERS = {
    "codebase": chunk_codebase,
    "schema":   chunk_schema,
    "contract": chunk_contract,
    "doc":      chunk_doc,
    "ticket":   chunk_tickets,
    "delivery": chunk_delivery,
}


def get_chunks(source_path: pathlib.Path, doc_type: str) -> Iterator[Chunk]:
    """
    Entry point para obtener chunks de cualquier tipo de documento.
    Uso: for chunk in get_chunks(Path("/src"), "codebase"): ...
    """
    chunker = DOC_TYPE_CHUNKERS.get(doc_type)
    if not chunker:
        raise ValueError(f"doc_type '{doc_type}' no soportado. Opciones: {list(DOC_TYPE_CHUNKERS)}")
    yield from chunker(source_path)
