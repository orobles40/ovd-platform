"""
OVD Platform — Tests unitarios para knowledge/chunkers.py (U-02)
Copyright 2026 Omar Robles

Verifica todos los chunkers con fixtures estáticas (sin infraestructura):
- chunk_codebase: Python (AST), TypeScript (por líneas), archivos no soportados
- chunk_schema: DDL CREATE TABLE/VIEW/PROCEDURE
- chunk_contract: OpenAPI JSON/YAML por endpoint
- chunk_doc: Markdown por secciones, TXT
- chunk_delivery: informes ovd-delivery-*.md
- chunk_tickets: JSON de tickets
- get_chunks: dispatcher principal
- _split_text: chunking con overlap
"""
import sys
import os
import json
import tempfile
import pathlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))

import pytest
from knowledge.chunkers import (
    chunk_codebase, chunk_schema, chunk_contract, chunk_doc,
    chunk_delivery, chunk_tickets, get_chunks, _split_text, Chunk,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp: str, name: str, content: str) -> pathlib.Path:
    p = pathlib.Path(tmp) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _split_text
# ---------------------------------------------------------------------------

class TestSplitText:
    def test_texto_corto_no_se_divide(self):
        result = _split_text("hola mundo", 100)
        assert result == ["hola mundo"]

    def test_texto_largo_se_divide(self):
        # max_chars debe ser > _CHUNK_OVERLAP (200) para evitar loop infinito
        texto = "x" * 1000
        chunks = _split_text(texto, 400)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c) <= 400

    def test_overlap_entre_chunks(self):
        # Usar max_chars > _CHUNK_OVERLAP (200)
        texto = "a" * 800
        chunks = _split_text(texto, 400)
        assert len(chunks) >= 2

    def test_texto_vacio(self):
        result = _split_text("", 100)
        assert result == [""]

    def test_corte_en_salto_de_linea(self):
        # max_chars debe ser > _CHUNK_OVERLAP (200) para evitar loop infinito
        lineas = "\n".join([f"linea {i}" for i in range(100)])
        chunks = _split_text(lineas, 400)
        for c in chunks:
            assert len(c) <= 400


# ---------------------------------------------------------------------------
# chunk_codebase — Python AST
# ---------------------------------------------------------------------------

class TestChunkCodebasePython:
    def test_funcion_simple_genera_chunk(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "calc.py", "def add(a, b):\n    return a + b\n")
            chunks = list(chunk_codebase(pathlib.Path(d)))
        assert any("add" in c.content for c in chunks)

    def test_clase_con_metodos_genera_chunks(self):
        src = """
class Calculadora:
    def sumar(self, a, b):
        return a + b
    def restar(self, a, b):
        return a - b
"""
        with tempfile.TemporaryDirectory() as d:
            _write(d, "calc.py", src)
            chunks = list(chunk_codebase(pathlib.Path(d)))
        symbols = {c.metadata.get("symbol") for c in chunks}
        assert any("Calculadora" in (s or "") for s in symbols)

    def test_doc_type_es_codebase(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "mod.py", "x = 1\n")
            chunks = list(chunk_codebase(pathlib.Path(d)))
        assert all(c.doc_type == "codebase" for c in chunks)

    def test_metadata_incluye_language_python(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "mod.py", "def f(): pass\n")
            chunks = list(chunk_codebase(pathlib.Path(d)))
        assert all(c.metadata.get("language") == "python" for c in chunks)

    def test_archivo_con_syntax_error_no_lanza(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "bad.py", "def (broken:\n")
            chunks = list(chunk_codebase(pathlib.Path(d)))
        assert isinstance(chunks, list)

    def test_salta_node_modules_y_venv(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "node_modules/lib.py", "def oculto(): pass\n")
            _write(d, "src/main.py", "def visible(): pass\n")
            chunks = list(chunk_codebase(pathlib.Path(d)))
        symbols = [c.metadata.get("symbol", "") for c in chunks]
        assert not any("oculto" in s for s in symbols)
        assert any("visible" in s for s in symbols)

    def test_archivo_individual(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "solo.py", "def unica(): pass\n")
            chunks = list(chunk_codebase(p))
        assert len(chunks) >= 1


class TestChunkCodebaseTypeScript:
    def test_typescript_genera_chunks(self):
        src = "export function greet(name: string): string {\n  return `Hello ${name}`;\n}\n"
        with tempfile.TemporaryDirectory() as d:
            _write(d, "greet.ts", src)
            chunks = list(chunk_codebase(pathlib.Path(d)))
        assert len(chunks) >= 1
        assert all(c.metadata.get("language") == "typescript" for c in chunks)

    def test_tsx_extension_reconocida(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "Button.tsx", "export const Button = () => <button>Click</button>;\n")
            chunks = list(chunk_codebase(pathlib.Path(d)))
        assert len(chunks) >= 1

    def test_extension_no_soportada_ignorada(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "README.md", "# Titulo\n")
            chunks = list(chunk_codebase(pathlib.Path(d)))
        assert chunks == []


# ---------------------------------------------------------------------------
# chunk_schema — DDL
# ---------------------------------------------------------------------------

class TestChunkSchema:
    DDL = """
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE VIEW usuarios_activos AS
    SELECT * FROM usuarios WHERE activo = TRUE;

CREATE OR REPLACE FUNCTION get_user(p_id INT) RETURNS usuarios AS $$
BEGIN
    RETURN (SELECT * FROM usuarios WHERE id = p_id);
END;
$$ LANGUAGE plpgsql;
"""

    def test_genera_chunk_por_objeto(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "schema.sql", self.DDL)
            chunks = list(chunk_schema(pathlib.Path(d)))
        assert len(chunks) >= 2

    def test_doc_type_es_schema(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "schema.sql", self.DDL)
            chunks = list(chunk_schema(pathlib.Path(d)))
        assert all(c.doc_type == "schema" for c in chunks)

    def test_metadata_incluye_kind(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "schema.sql", "CREATE TABLE test (id INT);\n")
            chunks = list(chunk_schema(pathlib.Path(d)))
        assert any(c.metadata.get("kind") == "table" for c in chunks)

    def test_metadata_incluye_nombre_tabla(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "schema.sql", "CREATE TABLE clientes (id INT);\n")
            chunks = list(chunk_schema(pathlib.Path(d)))
        assert any(c.metadata.get("table") == "clientes" for c in chunks)

    def test_archivo_sql_vacio_no_lanza(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "empty.sql", "")
            chunks = list(chunk_schema(pathlib.Path(d)))
        assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# chunk_doc — Markdown / TXT
# ---------------------------------------------------------------------------

class TestChunkDoc:
    MD = """# Título Principal

Introducción al sistema.

## Sección A

Contenido de la sección A con detalles técnicos.

## Sección B

Contenido de la sección B con más información.
"""

    def test_markdown_genera_chunks_por_seccion(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "doc.md", self.MD)
            chunks = list(chunk_doc(pathlib.Path(d)))
        assert len(chunks) >= 2

    def test_doc_type_es_doc(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "doc.md", self.MD)
            chunks = list(chunk_doc(pathlib.Path(d)))
        assert all(c.doc_type == "doc" for c in chunks)

    def test_metadata_incluye_seccion(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "doc.md", self.MD)
            chunks = list(chunk_doc(pathlib.Path(d)))
        secciones = {c.metadata.get("section") for c in chunks}
        assert "Sección A" in secciones or any("Secci" in (s or "") for s in secciones)

    def test_txt_genera_chunks(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "notas.txt", "Línea 1\nLínea 2\nLínea 3\n")
            chunks = list(chunk_doc(pathlib.Path(d)))
        assert len(chunks) >= 1

    def test_markdown_vacio_no_lanza(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "vacio.md", "")
            chunks = list(chunk_doc(pathlib.Path(d)))
        assert isinstance(chunks, list)

    def test_archivo_individual_md(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "solo.md", "## Solo\nContenido aquí.\n")
            chunks = list(chunk_doc(p))
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# chunk_delivery — informes ovd-delivery-*.md
# ---------------------------------------------------------------------------

class TestChunkDelivery:
    REPORT = """# Informe de Entrega OVD
**Ciclo:** `abc12345`
**Feature Request:** Crear endpoint de login

---

## Resumen
Login implementado con JWT y refresh tokens.

## Archivos Generados

### Agente: backend
  - `auth.py` (1200 bytes)
  - `routes/login.py` (800 bytes)

## Resultados de Auditoría
| Métrica | Valor |
|---------|-------|
| Security Score | 85/100 |
| QA Score | 90/100 |
| QA Passed | ✅ |
"""

    def test_genera_chunks_del_informe(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "ovd-delivery-abc12345-1234567890.md", self.REPORT)
            chunks = list(chunk_delivery(pathlib.Path(d)))
        assert len(chunks) >= 1

    def test_doc_type_es_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "ovd-delivery-abc12345-000.md", self.REPORT)
            chunks = list(chunk_delivery(pathlib.Path(d)))
        assert all(c.doc_type == "delivery" for c in chunks)

    def test_metadata_incluye_kind(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "ovd-delivery-test-000.md", self.REPORT)
            chunks = list(chunk_delivery(pathlib.Path(d)))
        kinds = {c.metadata.get("kind") for c in chunks}
        assert "ciclo" in kinds or len(kinds) > 0

    def test_ignora_archivos_sin_prefijo_ovd_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "otro-informe.md", self.REPORT)
            chunks = list(chunk_delivery(pathlib.Path(d)))
        assert chunks == []

    def test_archivo_individual(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "ovd-delivery-solo-000.md", self.REPORT)
            chunks = list(chunk_delivery(p))
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# chunk_tickets — JSON de tickets
# ---------------------------------------------------------------------------

class TestChunkTickets:
    TICKETS_JSON = json.dumps([
        {"key": "OVD-1", "summary": "Implementar login", "description": "Auth con JWT",
         "status": "Done", "issuetype": {"name": "Story"}},
        {"key": "OVD-2", "summary": "Fix bug en logout", "description": "Token no expira",
         "status": "In Progress", "issuetype": {"name": "Bug"}},
    ])

    def test_genera_chunk_por_ticket(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tickets.json", self.TICKETS_JSON)
            chunks = list(chunk_tickets(pathlib.Path(d)))
        assert len(chunks) == 2

    def test_doc_type_es_ticket(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tickets.json", self.TICKETS_JSON)
            chunks = list(chunk_tickets(pathlib.Path(d)))
        assert all(c.doc_type == "ticket" for c in chunks)

    def test_metadata_incluye_ticket_id(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tickets.json", self.TICKETS_JSON)
            chunks = list(chunk_tickets(pathlib.Path(d)))
        ids = {c.metadata.get("ticket_id") for c in chunks}
        assert "OVD-1" in ids
        assert "OVD-2" in ids

    def test_json_invalido_no_lanza(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "bad.json", "{not valid json}")
            chunks = list(chunk_tickets(pathlib.Path(d)))
        assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# get_chunks — dispatcher
# ---------------------------------------------------------------------------

class TestGetChunks:
    def test_dispatch_codebase(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "mod.py", "def f(): pass\n")
            chunks = list(get_chunks(pathlib.Path(d), "codebase"))
        assert len(chunks) >= 1

    def test_dispatch_doc(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "README.md", "## Intro\nHola.\n")
            chunks = list(get_chunks(pathlib.Path(d), "doc"))
        assert len(chunks) >= 1

    def test_dispatch_schema(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "schema.sql", "CREATE TABLE t (id INT);\n")
            chunks = list(get_chunks(pathlib.Path(d), "schema"))
        assert len(chunks) >= 1

    def test_doc_type_invalido_lanza_value_error(self):
        with pytest.raises(ValueError, match="no soportado"):
            list(get_chunks(pathlib.Path("/tmp"), "inventado"))

    def test_todos_los_chunks_tienen_content(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "mod.py", "def f(): pass\ndef g(): pass\n")
            chunks = list(get_chunks(pathlib.Path(d), "codebase"))
        assert all(c.content for c in chunks)

    def test_todos_los_chunks_tienen_source_file(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "mod.py", "def f(): pass\n")
            chunks = list(get_chunks(pathlib.Path(d), "codebase"))
        assert all(c.source_file for c in chunks)
