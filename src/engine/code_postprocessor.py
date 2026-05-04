"""
S72-B: Post-procesador de código Python generado por LLM.
S72-C: Fix orden mock oracledb en conftest.py.
S73-A: SQLAlchemy v1 → v2 (declarative_base → DeclarativeBase).
S74-A: Fix variable local que shadowea función del mismo módulo.
S74-D: Detectar secretos hardcoded y SHA-256 para passwords (log only).
S75-A: Elimina funciones de módulo que redefinen imports con wrapper trivial (RecursionError).
S77-A: Elimina/corrige parámetros Oracle inválidos en create_engine (thick=True → eliminar).
S77-B: Reordena @field_validator/@model_validator ANTES de @classmethod (Pydantic v2).
S107-P2: Reemplaza imágenes Oracle por postgres:16-alpine en docker-compose.yml.
S107-P3: Sincroniza imports service→router→tests post-fan-out (alias de nombres obvios).

Transformaciones aplicadas en _write_artifacts() antes de escribir al disco:
- Renombra funciones de español a inglés (AST NodeTransformer + call sites)
- Convierte @validator (Pydantic v1) → @field_validator + @classmethod (v2)
- Convierte @root_validator → @model_validator
- Convierte orm_mode/allow_population_by_field_name → ConfigDict
- Reordena decoradores Pydantic: @field_validator ANTES de @classmethod (S77-B)
- Corrige orden de mock oracledb en conftest.py
- Convierte declarative_base() → DeclarativeBase class (SQLAlchemy 2.x)
- Elimina parámetros Oracle inválidos en create_engine (S77-A)
- Renombra variable local que shadowea función del módulo (UnboundLocalError)
- Elimina wrapper trivial que shadea import a nivel módulo (RecursionError)
- Advierte sobre secretos hardcoded y SHA-256 para passwords
- Reemplaza imágenes Oracle en docker-compose.yml por postgres:16-alpine (S107-P2)
"""

from __future__ import annotations

import ast
import logging
import re

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# S72-B — Mapa canónico español → inglés
# ---------------------------------------------------------------------------

_SPANISH_TO_ENGLISH: dict[str, str] = {
    "validar_rut": "validate_rut",
    "es_primo": "is_prime",
    "crear_contrato": "create_contract",
    "obtener_contrato": "get_contract",
    "actualizar_contrato": "update_contract",
    "desactivar_contrato": "deactivate_contract",
    "listar_contratos": "list_contracts",
    "calcular_valor_total": "calculate_total_value",
    "calcular_valor_total_contrato": "calculate_contract_total_value",
    "actualizar_valor_total_contrato": "update_contract_total_value",
    "calcular_imc": "calculate_bmi",
    "validar_tipo_contrato": "validate_contract_type",
    "listar_beneficios": "list_benefits",
    "crear_beneficio": "create_benefit",
    "obtener_beneficio": "get_benefit",
    "actualizar_beneficio": "update_benefit",
    "eliminar_beneficio": "delete_benefit",
    "validar_email": "validate_email",
    "crear_usuario": "create_user",
    "obtener_usuario": "get_user",
    "listar_usuarios": "list_users",
    "calcular_dv": "calculate_check_digit",
}


class _FunctionRenamer(ast.NodeTransformer):
    """S72-B: renombra funciones y actualiza todos sus call sites."""

    def __init__(self, rename_map: dict[str, str]) -> None:
        self._map = rename_map

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name in self._map:
            old = node.name
            node.name = self._map[old]
            log.warning("[S72-B] rename: %s → %s", old, node.name)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        if node.name in self._map:
            node.name = self._map[node.name]
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if isinstance(node.func, ast.Name) and node.func.id in self._map:
            node.func.id = self._map[node.func.id]
        elif isinstance(node.func, ast.Attribute) and node.func.attr in self._map:
            node.func.attr = self._map[node.func.attr]
        return self.generic_visit(node)


def _rename_functions(code: str) -> str:
    """S72-B paso 1: renombra funciones de español a inglés via AST."""
    try:
        tree = ast.parse(code)
        renamer = _FunctionRenamer(_SPANISH_TO_ENGLISH)
        new_tree = renamer.visit(tree)
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)
    except SyntaxError:
        log.warning("[S72-B] SyntaxError al parsear — skip rename AST")
        return code


# ---------------------------------------------------------------------------
# S72-B — Pydantic v1 → v2
# ---------------------------------------------------------------------------


def _fix_pydantic_v1(code: str) -> str:
    """S72-B paso 2: convierte patrones Pydantic v1 → v2 via regex + líneas."""
    _has_v1_decorator = "@validator" in code or "root_validator" in code
    _has_v1_import = bool(
        re.search(r"from\s+pydantic\s+import[^\n]*\bvalidator\b", code)
    )
    _has_v2_decorator = "@field_validator" in code or "@model_validator" in code
    _has_orm_mode = "orm_mode" in code or "allow_population_by_field_name" in code

    if (
        not _has_v1_decorator
        and not _has_v1_import
        and not _has_v2_decorator
        and not _has_orm_mode
    ):
        return code  # fast path: sin patrones v1 ni v2 a reparar

    changed = False

    # @root_validator → @model_validator
    if "root_validator" in code:
        new = re.sub(r"@root_validator\b", "@model_validator", code)
        if new != code:
            changed = True
            code = new
        code = re.sub(
            r"(from\s+pydantic\s+import\s+[^\n]*)\broot_validator\b",
            lambda m: m.group(0).replace("root_validator", "model_validator"),
            code,
        )

    # @validator → @field_validator (decorators)
    if "@validator" in code:
        new = re.sub(r"@validator\(", "@field_validator(", code)
        if new != code:
            changed = True
            code = new

    # from pydantic import ... validator ... → siempre reemplazar en imports
    if re.search(r"from\s+pydantic\s+import[^\n]*\bvalidator\b(?!\w)", code):
        new = re.sub(
            r"(from\s+pydantic\s+import\s+[^\n]*)\bvalidator\b(?!\w)",
            lambda m: m.group(0).replace("validator", "field_validator"),
            code,
        )
        if new != code:
            changed = True
            code = new

    # orm_mode = True → from_attributes = True (dentro de class Config)
    if "orm_mode" in code:
        new = re.sub(r"\borm_mode\s*=\s*True\b", "from_attributes = True", code)
        if new != code:
            changed = True
            code = new

    # allow_population_by_field_name = True → populate_by_name = True
    if "allow_population_by_field_name" in code:
        new = re.sub(
            r"\ballow_population_by_field_name\s*=\s*True\b",
            "populate_by_name = True",
            code,
        )
        if new != code:
            changed = True
            code = new

    # Agregar @classmethod donde haya @field_validator o @model_validator sin él
    # (aplica tanto a código v1 convertido como a código v2 ya existente)
    lines = code.split("\n")
    result: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith("@field_validator(") or stripped.startswith(
            "@model_validator("
        ):
            prev = [l.strip() for l in result[-3:]]
            if "@classmethod" not in prev:
                result.append(f"{indent}@classmethod")
                changed = True
                log.warning("[S72-B] @classmethod inyectado antes de %s", stripped[:50])
        result.append(line)

    if not changed:
        return code

    return "\n".join(result)


# ---------------------------------------------------------------------------
# S77-B — Fix orden decoradores Pydantic v2
# ---------------------------------------------------------------------------


def _fix_pydantic_decorator_order(code: str) -> str:
    """S77-B: reordena decoradores — @field_validator/@model_validator
    DEBE preceder a @classmethod (Pydantic v2). Si está al revés, el validator
    no se registra silenciosamente — bug invisible hasta que tests fallan.
    """
    if "@field_validator" not in code and "@model_validator" not in code:
        return code  # fast path

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    fixed_count = 0

    def _deco_name(deco_node: ast.expr) -> str | None:
        if isinstance(deco_node, ast.Name):
            return deco_node.id
        if isinstance(deco_node, ast.Call) and isinstance(deco_node.func, ast.Name):
            return deco_node.func.id
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if len(node.decorator_list) < 2:
            continue

        deco_names = [_deco_name(d) for d in node.decorator_list]
        try:
            classmethod_idx = deco_names.index("classmethod")
        except ValueError:
            continue

        # Buscar field_validator/model_validator DESPUÉS de classmethod (orden inválido)
        validator_idx = -1
        for i in range(classmethod_idx + 1, len(deco_names)):
            if deco_names[i] in ("field_validator", "model_validator", "validator"):
                validator_idx = i
                break

        if validator_idx == -1:
            continue  # orden ya correcto o no aplica

        # Reordenar: mover @classmethod justo después del validator
        classmethod_deco = node.decorator_list.pop(classmethod_idx)
        # validator_idx ahora está en classmethod_idx (tras el pop)
        node.decorator_list.insert(classmethod_idx + 1, classmethod_deco)
        fixed_count += 1
        log.warning(
            "[S77-B] reordenado decoradores en %s: @%s ahora antes de @classmethod",
            node.name,
            deco_names[validator_idx],
        )

    if fixed_count == 0:
        return code

    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# ---------------------------------------------------------------------------
# S73-A — SQLAlchemy v1 → v2
# ---------------------------------------------------------------------------


def _fix_sqlalchemy_v1(code: str) -> str:
    """S73-A: convierte patrones SQLAlchemy 1.x → 2.x via regex."""
    if "declarative_base" not in code:
        return code  # fast path

    changed = False

    # from sqlalchemy.ext.declarative import declarative_base → orm.DeclarativeBase
    if "from sqlalchemy.ext.declarative import declarative_base" in code:
        code = code.replace(
            "from sqlalchemy.ext.declarative import declarative_base",
            "from sqlalchemy.orm import DeclarativeBase",
        )
        changed = True

    # Base = declarative_base() → class Base(DeclarativeBase): pass
    if "declarative_base()" in code:
        code = re.sub(
            r"^(\s*)(\w+)\s*=\s*declarative_base\(\)\s*$",
            lambda m: (
                f"{m.group(1)}class {m.group(2)}(DeclarativeBase):\n{m.group(1)}    pass"
            ),
            code,
            flags=re.MULTILINE,
        )
        changed = True

    if changed:
        log.warning(
            "[S73-A] SQLAlchemy v1→v2: declarative_base() → DeclarativeBase class"
        )

    return code


# ---------------------------------------------------------------------------
# S77-A — Fix parámetros Oracle inválidos en create_engine
# ---------------------------------------------------------------------------


def _fix_sqlalchemy_oracle_params(code: str) -> str:
    """S77-A: elimina/corrige parámetros inválidos de Oracle en create_engine.

    Patrones detectados:
    - thick=True / thick=False  → parámetro inexistente, eliminar
    - mode="thick"              → parámetro inexistente, eliminar
    - thick_mode="True"         → string en lugar de bool, corregir a thick_mode=True
    """
    if "create_engine" not in code:
        return code

    changed = False

    # Eliminar thick=True/False dentro de create_engine()
    if re.search(r"\bthick\s*=\s*(True|False)", code):
        new = re.sub(
            r",\s*thick\s*=\s*(?:True|False)\s*(?=,|\))",
            "",
            code,
        )
        # también cuando thick= es el primer kwarg justo después de url
        new = re.sub(
            r"(create_engine\s*\([^,)]+),\s*thick\s*=\s*(?:True|False)",
            r"\1",
            new,
        )
        new = re.sub(r",\s*\)", ")", new)  # cleanup trailing comma
        new = re.sub(r",\s*,", ",", new)  # cleanup double comma
        if new != code:
            changed = True
            code = new
            log.warning("[S77-A] thick=True/False eliminado de create_engine()")

    # Eliminar mode="thick" / mode='thick'
    if re.search(r"mode\s*=\s*[\"']thick[\"']", code):
        new = re.sub(r',?\s*mode\s*=\s*["\']thick["\']\s*(?=,|\))', "", code)
        new = re.sub(r",\s*\)", ")", new)
        if new != code:
            changed = True
            code = new
            log.warning("[S77-A] mode='thick' eliminado de create_engine()")

    # Corregir thick_mode="True" string → True bool
    if re.search(r"thick_mode\s*=\s*[\"']True[\"']", code):
        new = re.sub(r"thick_mode\s*=\s*[\"']True[\"']", "thick_mode=True", code)
        if new != code:
            changed = True
            code = new
            log.warning("[S77-A] thick_mode='True' (string) → thick_mode=True (bool)")

    if changed:
        log.warning("[S77-A] Oracle params normalizados en create_engine()")

    return code


# ---------------------------------------------------------------------------
# S101-C — Reemplazar DATABASE_URL hardcodeada por os.environ.get()
# ---------------------------------------------------------------------------


def _fix_database_url_hardcoded(content: str, rel_path: str) -> str:
    """S101-C: reemplaza DATABASE_URL = '...' por os.environ.get() en database.py.

    El LLM hardcodea credenciales pese a la prohibición en el template. Postprocesador
    determinístico: detecta el patrón de asignación directa y lo convierte a env var,
    preservando el valor original como default para facilitar el desarrollo local.
    """
    if not (rel_path.endswith("database.py") or rel_path.endswith("/database.py")):
        return content
    # Solo actúa si hay una asignación directa (no os.environ, no f-string con variable)
    _pattern = re.compile(
        r'^(DATABASE_URL\s*=\s*)["\']([a-zA-Z][a-zA-Z0-9+._-]*://[^"\']+)["\']',
        re.MULTILINE,
    )
    match = _pattern.search(content)
    if not match:
        return content
    hardcoded_url = match.group(2)
    new_content = _pattern.sub(
        r'\g<1>os.environ.get("DATABASE_URL", "' + hardcoded_url + '")',
        content,
    )
    if "import os" not in new_content and "import os\n" not in new_content:
        # Insertar import os antes de la primera línea no-comentario, no-docstring
        lines = new_content.splitlines(keepends=True)
        insert_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith('"""')
                and not stripped.startswith("'''")
            ):
                insert_idx = i
                break
        lines.insert(insert_idx, "import os\n")
        new_content = "".join(lines)
    if new_content != content:
        log.warning(
            "[S101-C] DATABASE_URL hardcodeada reemplazada por os.environ.get() en %s",
            rel_path,
        )
    return new_content


# ---------------------------------------------------------------------------
# S102-A — Promover imports silenciados por try/except ImportError: pass
# ---------------------------------------------------------------------------


def _fix_silent_service_import(content: str, rel_path: str) -> str:
    """S102-A: promueve imports de service silenciados por try/except ImportError: pass.

    El LLM genera:
        try:
            from src.contracts.service import create_contract, ...
            from src.contracts.models import ...
        except ImportError:
            pass

    Esto silencia el error — el router arranca sin excepción pero los endpoints
    crashean con NameError en runtime. Fix: extraer los imports fuera del try/except
    para que el error sea explícito e inmediato (falla en import-time, no en call-time).
    """
    if not rel_path.endswith("router.py"):
        return content
    # Captura cualquier línea indentada dentro del try (incluye imports multi-línea con paréntesis)
    _pattern = re.compile(
        r"^try:\n((?:[ \t]+[^\n]+\n)+)except\s+ImportError:\s*\n[ \t]+pass[ \t]*\n",
        re.MULTILINE,
    )

    def _unwrap(match: re.Match) -> str:
        block = match.group(1)
        lines = [line.lstrip() for line in block.splitlines()]
        return "\n".join(lines) + "\n"

    new_content = _pattern.sub(_unwrap, content)
    if new_content != content:
        log.warning(
            "[S102-A] try/except ImportError silencioso → imports directos en %s",
            rel_path,
        )
    return new_content


# S84-A — Fix Oracle init en database.py con URL PostgreSQL
# ---------------------------------------------------------------------------


def _fix_oracle_init_in_postgres_db(content: str, rel_path: str) -> str:
    """S84-A: elimina oracledb.init_oracle_client() cuando DATABASE_URL es PostgreSQL.

    El LLM combina Oracle init con URL postgres por haber visto proyectos Oracle
    en el historial. Si DATABASE_URL tiene psycopg/postgresql → Oracle init es inválido.
    """
    if not (rel_path.endswith("database.py") or rel_path.endswith("/database.py")):
        return content
    is_postgres = bool(
        re.search(r"DATABASE_URL\s*=\s*f?['\"]postgresql", content)
        or re.search(r"DATABASE_URL\s*=\s*f?['\"].*psycopg", content)
        or re.search(r"postgresql\+psycopg", content)
    )
    if not is_postgres:
        return content
    if "oracledb.init_oracle_client" not in content:
        return content
    lines = content.splitlines(keepends=True)
    new_lines = [
        line
        for line in lines
        if "oracledb.init_oracle_client" not in line
        and not re.match(r"^import oracledb\b", line.strip())
    ]
    new_content = "".join(new_lines)
    if new_content != content:
        log.warning(
            "[S84-A] oracledb.init_oracle_client() eliminado de %s (DATABASE_URL es PostgreSQL)",
            rel_path,
        )
    return new_content


# ---------------------------------------------------------------------------
# S80-C — Fix declarative_base() anti-pattern en archivos que no son database.py
# ---------------------------------------------------------------------------


def _fix_declarative_base_import(content: str, file_path: str) -> str:
    """S80-C: reemplaza patrones de Base local con 'from src.database import Base'.

    Cubre dos variantes del LLM:
    - old style: Base = declarative_base()
    - new style: from sqlalchemy.orm import DeclarativeBase (sin crear Base)
    Solo aplica a archivos que NO son src/database.py.
    """
    if "database.py" in file_path:
        return content

    new = content
    changed = False

    # Variante 1 (vieja): Base = declarative_base()
    if "Base = declarative_base()" in content:
        new = re.sub(
            r"from sqlalchemy\.orm import ([^#\n]*\bdeclarative_base\b[^#\n]*)\n",
            lambda m: (
                ""
                if m.group(1).strip() == "declarative_base"
                else f"from sqlalchemy.orm import {m.group(1).replace('declarative_base,', '').replace(', declarative_base', '').replace('declarative_base', '').strip().rstrip(',')}\n"
            ),
            new,
        )
        new = re.sub(
            r"^Base\s*=\s*declarative_base\(\)\s*\n", "", new, flags=re.MULTILINE
        )
        changed = True

    # Variante 2 (nueva): import DeclarativeBase sin definir Base como subclase
    # El LLM importa DeclarativeBase pero usa UserORM(Base) sin crear Base
    if "DeclarativeBase" in new and re.search(
        r"\bclass\s+\w+ORM\s*\(\s*Base\s*\)", new
    ):
        # Eliminar la línea de import DeclarativeBase si no se usa para definir Base
        if not re.search(r"\bclass\s+Base\s*\(\s*DeclarativeBase\s*\)", new):
            new = re.sub(
                r"from sqlalchemy\.orm import ([^#\n]*\bDeclarativeBase\b[^#\n]*)\n",
                lambda m: (
                    ""
                    if m.group(1).strip() == "DeclarativeBase"
                    else f"from sqlalchemy.orm import {m.group(1).replace('DeclarativeBase,', '').replace(', DeclarativeBase', '').replace('DeclarativeBase', '').strip().rstrip(',')}\n"
                ),
                new,
            )
            changed = True

    if not changed and "from src.database import Base" not in content:
        return content

    # Agregar import correcto si aún no está
    if "from src.database import Base" not in new:
        new = "from src.database import Base\n" + new
    if new != content:
        log.warning(
            "[S80-C] Base local reemplazado con 'from src.database import Base' en %s",
            file_path,
        )
    return new


# ---------------------------------------------------------------------------
# S74-A — Fix variable local que shadowea función del mismo módulo
# ---------------------------------------------------------------------------


def _fix_local_variable_shadowing(code: str) -> str:
    """S74-A: renombra variables locales que shadowean funciones del mismo módulo."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    # Recolectar nombres de funciones/clases definidas en el módulo raíz (no anidadas)
    module_fn_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_fn_names.add(node.name)

    if not module_fn_names:
        return code

    # Detectar asignaciones dentro de funciones que shadowean nombres del módulo
    shadows: dict[str, str] = {}
    for fn_node in ast.walk(tree):
        if not isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(fn_node):
            if not isinstance(child, ast.Assign):
                continue
            for target in child.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id in module_fn_names
                    and target.id != fn_node.name  # no renombrar la función a sí misma
                ):
                    shadows[target.id] = f"_{target.id}_val"

    if not shadows:
        return code

    changed_code = code
    for old, new in shadows.items():
        # Solo reemplazar assignments: `old =` → `new =`, no los call sites
        changed_code = re.sub(
            rf"(?<![.\w]){re.escape(old)}\s*=\s*(?!=)",
            f"{new} = ",
            changed_code,
        )
        log.warning("[S74-A] local shadow fix: %s → %s", old, new)

    return changed_code


# ---------------------------------------------------------------------------
# S75-A — Elimina función de módulo que redefine import con wrapper trivial
# ---------------------------------------------------------------------------


def _fix_function_import_shadowing(code: str) -> str:
    """S75-A: elimina FunctionDef que shadowea un import con wrapper trivial (RecursionError).

    Detecta:
        from src.utils.rut_validator import validate_rut   # import OK

        def validate_rut(rut: str) -> bool:   # ← redefine el import
            return validate_rut(rut)           # ← RecursionError en runtime

    Fix: elimina la FunctionDef redundante. El import existente ya provee la función.
    Solo elimina wrappers triviales: body = [Return(Call(func=Name(same_name)))].
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    # Recolectar nombres importados a nivel módulo
    imported_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)

    if not imported_names:
        return code

    # Detectar FunctionDef a nivel módulo que shadowean imports con wrapper trivial
    to_remove: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in imported_names:
            continue
        # Solo elimina si el cuerpo es exactamente: return fn(args) — wrapper trivial
        if (
            len(node.body) == 1
            and isinstance(node.body[0], ast.Return)
            and isinstance(node.body[0].value, ast.Call)
            and isinstance(node.body[0].value.func, ast.Name)
            and node.body[0].value.func.id == node.name
        ):
            to_remove.add(node.name)
            log.warning(
                "[S75-A] wrapper trivial eliminado: def %s() → usa import directo",
                node.name,
            )

    if not to_remove:
        return code

    class _RemoveWrapper(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST | None:
            if node.name in to_remove:
                return None
            return self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST | None:
            if node.name in to_remove:
                return None
            return self.generic_visit(node)

    new_tree = _RemoveWrapper().visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


# ---------------------------------------------------------------------------
# S74-D — Detección de secretos hardcoded (log only)
# ---------------------------------------------------------------------------

_SECRET_VAR_KEYWORDS = frozenset(
    {"key", "secret", "password", "token", "api_key", "passwd", "auth"}
)
_SHA256_PWD_RE = re.compile(r"hashlib\.sha256\([^)]+\.encode\(\)\)\.hexdigest\(\)")


def _warn_hardcoded_secrets(code: str, rel_path: str) -> str:
    """S74-D: detecta secretos hardcoded y SHA-256 para passwords (log only, no modifica)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name_lower = target.id.lower()
            if not any(kw in name_lower for kw in _SECRET_VAR_KEYWORDS):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(
                node.value.value, str
            ):
                val = node.value.value
                if val and val not in (
                    "",
                    "changeme",
                    "your-secret",
                    "your-secret-key-here",
                ):
                    log.warning(
                        "[S74-D] %s:%d secret hardcoded '%s' — usar os.environ.get('%s')",
                        rel_path,
                        node.lineno,
                        target.id,
                        target.id.upper(),
                    )

    if _SHA256_PWD_RE.search(code):
        log.warning(
            "[S74-D] %s: SHA-256 para password detectado — usar passlib[bcrypt]",
            rel_path,
        )

    return code  # log only en S74 — no modifica el código


# ---------------------------------------------------------------------------
# S81-A — Elimina clases ORM definidas en service.py (duplicado de models.py)
# ---------------------------------------------------------------------------


def _fix_orm_in_service(content: str, rel_path: str, work_dir: str = "") -> str:
    """S81-A: detecta clases ORM en service.py y las elimina, agregando import desde models.py.

    El LLM a veces define ContractORM(Base) tanto en models.py como en service.py.
    SQLAlchemy lanza InvalidRequestError cuando se registran dos clases con el mismo __tablename__.

    S82-A: verifica que models.py existe en disco antes de remover ORM.
    Si models.py no existe, preserva ORM en service.py para evitar phantom imports.
    """
    if "service.py" not in rel_path:
        return content
    # S82-A: verificar que models.py existe antes de crear phantom import
    if work_dir:
        import pathlib as _pl

        _models_path = _pl.Path(work_dir) / _pl.Path(rel_path).parent / "models.py"
        if not _models_path.exists():
            log.warning(
                "[S82-A] S81-A omitido — %s no existe: preservando ORM en %s para evitar phantom import",
                _models_path,
                rel_path,
            )
            return content
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return content

    orm_class_names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_id = getattr(base, "id", None) or getattr(base, "attr", None)
            if base_id in ("Base", "DeclarativeBase"):
                orm_class_names.append(node.name)
                break

    if not orm_class_names:
        return content

    # Construir import correcto: src/contracts/service.py → src.contracts.models
    module_path = rel_path.replace("/", ".").removesuffix(".py")
    models_module = module_path.rsplit(".", 1)[0] + ".models"
    import_line = f"from {models_module} import {', '.join(sorted(orm_class_names))}\n"

    class _OrmRemover(ast.NodeTransformer):
        def visit_ClassDef(self, node: ast.ClassDef):
            for base in node.bases:
                base_id = getattr(base, "id", None) or getattr(base, "attr", None)
                if base_id in ("Base", "DeclarativeBase"):
                    return None
            return node

    new_tree = _OrmRemover().visit(tree)
    ast.fix_missing_locations(new_tree)
    try:
        new_content = ast.unparse(new_tree)
    except Exception:
        return content

    if import_line.strip() not in new_content:
        new_content = import_line + new_content

    log.warning(
        "[S81-A] ORM classes %s eliminadas de service.py — reemplazadas con import de models.py",
        orm_class_names,
    )
    return new_content


# ---------------------------------------------------------------------------
# S72-C — Fix conftest.py oracledb mock order
# ---------------------------------------------------------------------------

_MOCK_HEADER = """\
import sys
from unittest.mock import MagicMock
# S72-C: mock oracledb ANTES de cualquier import que lo use
sys.modules['oracledb'] = MagicMock()

"""


def _fix_conftest_mock_order(content: str) -> str:
    """
    S72-C: corrige el orden del mock oracledb en conftest.py.

    El mock debe estar ANTES de cualquier `import oracledb` o
    `from oracledb import ...`. Si ya está en orden correcto, no toca nada.
    """
    has_oracledb_import = bool(
        re.search(
            r"^\s*(import oracledb|from oracledb\s+import)", content, re.MULTILINE
        )
    )
    has_mock = (
        "sys.modules['oracledb']" in content or 'sys.modules["oracledb"]' in content
    )

    if not has_oracledb_import and not has_mock:
        return content  # no hay oracledb — no tocar

    # Verificar si ya está en orden correcto
    if has_mock and has_oracledb_import:
        mock_pos = min(
            (
                content.find("sys.modules['oracledb']")
                if "sys.modules['oracledb']" in content
                else len(content)
            ),
            (
                content.find('sys.modules["oracledb"]')
                if 'sys.modules["oracledb"]' in content
                else len(content)
            ),
        )
        import_pos = min(
            (
                content.find("import oracledb")
                if "import oracledb" in content
                else len(content)
            ),
            (
                content.find("from oracledb")
                if "from oracledb" in content
                else len(content)
            ),
        )
        if mock_pos < import_pos:
            return content  # ya está correcto

    log.warning("[S72-C] corrigiendo orden mock oracledb en conftest.py")

    # Eliminar imports directos de oracledb (el mock los reemplaza)
    content = re.sub(r"^\s*import oracledb\s*\n", "", content, flags=re.MULTILINE)
    content = re.sub(
        r"^\s*from oracledb\s+import[^\n]*\n", "", content, flags=re.MULTILINE
    )

    # Asegurar import pytest
    if "import pytest" not in content:
        content = "import pytest\n" + content

    # Inyectar bloque mock al inicio (preservar shebang/encoding si los hay)
    lines = content.split("\n")
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            stripped.startswith("#!")
            or stripped.startswith("# -*-")
            or stripped.startswith("# coding")
        ):
            insert_at = i + 1
        else:
            break

    lines.insert(insert_at, _MOCK_HEADER.rstrip())
    return "\n".join(lines)


def _fix_orm_phantom_module_import(content: str) -> str:
    """S88-A: reescribe imports desde módulos fantasma *.orm → *.models.

    El LLM a veces genera 'from src.contracts.orm import ContractORM' en vez de
    'from src.contracts.models import ContractORM'. El módulo *.orm nunca existe.
    """
    return re.sub(
        r"\bfrom\s+(src\.\w+)\.orm\s+import\b",
        r"from \1.models import",
        content,
    )


def _fix_phantom_repository_import(content: str) -> str:
    """S89-B: elimina imports desde módulos *.repository que nunca existen.

    El LLM a veces genera patrón Repository (ContractRepository, BenefitRepository)
    pero nunca crea el archivo. La línea se elimina porque los mismos routers ya
    importan las funciones CRUD directamente desde *.service.
    """
    return re.sub(
        r"^from\s+src\.\w+\.repository\s+import[^\n]*\n?",
        "",
        content,
        flags=re.MULTILINE,
    )


def _fix_benefits_module_import(content: str) -> str:
    """S90-B: redirige imports desde src.benefits.* → src.contracts.*.

    El LLM a veces crea un paquete src/benefits/ separado pero los beneficios
    siempre viven en src/contracts/service.py. Redirección determinística.
    """
    return re.sub(
        r"\bfrom\s+src\.benefits\.(\w+)\s+import\b",
        r"from src.contracts.\1 import",
        content,
    )


# Módulos que pertenecen a proyectos anteriores y nunca deben aparecer en código nuevo.
# El LLM los inyecta cuando su contexto se contamina con sesiones previas.
_SPURIOUS_IMPORT_PATTERNS: list[str] = [
    r"^(?:from|import)\s+src\.utils\.prime_validator\b[^\n]*\n?",
    r"^(?:from|import)\s+src\.utils\.imc_validator\b[^\n]*\n?",
    r"^(?:from|import)\s+src\.calculadora\b[^\n]*\n?",
    r"^(?:from|import)\s+src\.utils\.calculadora\b[^\n]*\n?",
]
_SPURIOUS_IMPORT_RE = re.compile(
    "|".join(_SPURIOUS_IMPORT_PATTERNS),
    flags=re.MULTILINE,
)


def _fix_spurious_utility_imports(content: str) -> str:
    """S96-B: elimina imports de módulos de proyectos anteriores inyectados por el LLM.

    Causa raíz: el LLM contamina el contexto con proyectos previos (calculadora IMC,
    validador de primos) y genera imports que no pertenecen al dominio actual.
    Eliminación determinística vía regex.
    """
    cleaned, count = _SPURIOUS_IMPORT_RE.subn("", content)
    if count:
        log.warning(
            "[S96-B] eliminados %d imports espurios de proyectos anteriores", count
        )
    return cleaned


# Mapa determinístico de clases ORM en español → inglés.
# El template system_backend.md prohíbe los nombres en español, pero el LLM
# los genera igualmente. Este postprocessor corrige el código generado.
_ORM_CLASS_RENAME: dict[str, str] = {
    "ContratoORM": "ContractORM",
    "BeneficioORM": "BenefitORM",
    "UsuarioORM": "UserORM",
    "EmpleadoORM": "EmployeeORM",
    "ProductoORM": "ProductORM",
    "PedidoORM": "OrderORM",
    "FacturaORM": "InvoiceORM",
    "ClienteORM": "CustomerORM",
    "PagoORM": "PaymentORM",
    "CategoriaORM": "CategoryORM",
}

_ORM_RENAME_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _ORM_CLASS_RENAME) + r")\b"
)


def _fix_orm_class_names_es_to_en(content: str) -> str:
    """S96-C: renombra clases ORM generadas en español al equivalente en inglés.

    El LLM sigue generando ContratoORM/BeneficioORM/UsuarioORM pese a las
    restricciones en el template. Corrección determinística vía re.sub().
    """
    result, count = _ORM_RENAME_RE.subn(
        lambda m: _ORM_CLASS_RENAME[m.group(0)], content
    )
    if count:
        log.warning("[S96-C] renombradas %d clases ORM español→inglés", count)
    return result


# ---------------------------------------------------------------------------
# S107-P2 — Fix Oracle image in docker-compose
# ---------------------------------------------------------------------------

_ORACLE_DOCKER_IMAGE_RE = re.compile(
    r"(image:\s*)(gvenzl/oracle-xe[^\s\n]*|oracle/database[^\s\n]*"
    r"|oracleinanutshell/oracle-xe[^\s\n]*)",
    re.IGNORECASE,
)


def _fix_oracle_in_docker_compose(content: str, oracle_involved: bool) -> str:
    """S107-P2: reemplaza imágenes Oracle por postgres:16-alpine cuando oracle_involved=False.

    El modelo qwen3-coder:30b genera gvenzl/oracle-xe por conocimiento de entrenamiento
    incluso cuando el FR pide PostgreSQL. Este postprocesador es el safety net.
    """
    if oracle_involved:
        return content
    if not _ORACLE_DOCKER_IMAGE_RE.search(content):
        return content
    fixed, n = _ORACLE_DOCKER_IMAGE_RE.subn(r"\1postgres:16-alpine", content)
    if n:
        log.warning(
            "[S107-P2] %d imagen(es) Oracle reemplazada(s) por postgres:16-alpine "
            "en docker-compose (oracle_involved=False)",
            n,
        )
    return fixed


# ---------------------------------------------------------------------------
# S107-P3 — Sync service imports in router/tests post-fan-out
# ---------------------------------------------------------------------------

_SERVICE_IMPORT_RE = re.compile(
    r"^from\s+(src\.\S+\.(?:service|services))\s+import\s+(.+)$",
    re.MULTILINE,
)


def _extract_defined_functions(filepath: str) -> set[str]:
    """Extrae nombres de funciones definidas en un archivo Python via AST."""
    import pathlib

    path = pathlib.Path(filepath)
    if not path.exists():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
    except SyntaxError:
        return set()


def _build_service_alias_map(defined_fns: set[str]) -> dict[str, str]:
    """Construye mapeo alias→nombre_real basado en patrones de naming cross-language.

    El agente usa español para services.py (deactivate_X, get_Xs) e inglés/REST
    para router.py y tests (delete_X, list_Xs). Este mapa corrige las divergencias.
    """
    alias_map: dict[str, str] = {}
    for fn in defined_fns:
        if fn.startswith("deactivate_"):
            entity = fn[len("deactivate_") :]
            for alt in (f"delete_{entity}", f"disable_{entity}", f"remove_{entity}"):
                alias_map[alt] = fn
        if fn.startswith("get_") and fn.endswith("s"):
            alias_map[fn.replace("get_", "list_", 1)] = fn
        if fn.startswith("calcular_"):
            rest = fn[len("calcular_") :]
            for alt in (f"get_{rest}", f"calculate_{rest}", "get_contract_total"):
                alias_map[alt] = fn
        if fn.startswith("create_") and not fn.startswith("create_access"):
            pass  # create_ es generalmente consistente
    return alias_map


def _apply_import_corrections(
    content: str, alias_map: dict[str, str]
) -> tuple[str, list[str]]:
    """Reemplaza imports con alias por sus nombres canónicos en alias_map."""
    if not alias_map:
        return content, []
    applied: list[str] = []

    def _fix_names_in_import(m: re.Match) -> str:
        module = m.group(1)
        names_str = m.group(2)
        names = [n.strip() for n in names_str.split(",")]
        fixed: list[str] = []
        for name in names:
            canonical = alias_map.get(name)
            if canonical:
                applied.append(f"{name} → {canonical} (en {module})")
                fixed.append(canonical)
            else:
                fixed.append(name)
        return f"from {module} import {', '.join(fixed)}"

    new_content = _SERVICE_IMPORT_RE.sub(_fix_names_in_import, content)
    return new_content, applied


def sync_service_imports(work_dir: str) -> list[str]:
    """S107-P3: sincroniza imports de router/tests con las funciones reales de services.py.

    Después del fan-out paralelo, router.py y tests pueden importar nombres que no
    existen en services.py (divergencia de naming cross-context). Este postprocesador
    aplica un mapa de alias determinístico para corregir las importaciones.

    Retorna lista de correcciones aplicadas (para logging).
    """
    import pathlib

    base = pathlib.Path(work_dir)
    if not base.exists():
        return []

    # 1. Recopilar funciones definidas en todos los services.py / service.py
    all_defined: set[str] = set()
    for service_file in base.rglob("service*.py"):
        if "test" not in service_file.name:
            all_defined |= _extract_defined_functions(str(service_file))

    if not all_defined:
        return []

    alias_map = _build_service_alias_map(all_defined)
    if not alias_map:
        return []

    fixes: list[str] = []

    # 2. Corregir router.py y test_*.py que importen desde service(s).py
    for py_file in base.rglob("*.py"):
        rel = py_file.relative_to(base)
        rel_str = str(rel)
        if "router" not in rel_str and "test_" not in py_file.name:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        new_content, applied = _apply_import_corrections(content, alias_map)
        if applied:
            py_file.write_text(new_content, encoding="utf-8")
            fixes.extend(applied)
            log.warning(
                "[S107-P3] %s: %d imports corregidos: %s",
                rel_str,
                len(applied),
                applied,
            )

    return fixes


# ---------------------------------------------------------------------------
# Entry point: postprocess_python_file / postprocess_yaml_file
# ---------------------------------------------------------------------------


def postprocess_python_file(content: str, rel_path: str, work_dir: str = "") -> str:
    """
    S72-B/C: post-procesa un archivo Python generado por LLM.

    Para conftest.py: corrige orden mock oracledb (S72-C).
    Para otros .py:  renombra español→inglés + Pydantic v1→v2 (S72-B).

    work_dir: directorio raíz del workspace — usado por S82-A para verificar models.py en disco.

    Retorna el contenido transformado (o el original si no hay cambios).
    """
    if not rel_path.endswith(".py"):
        return content

    # S86-C: __init__.py vacío recibe comentario mínimo antes de cualquier otro procesamiento
    if not content.strip() and rel_path.endswith("__init__.py"):
        _pkg = (
            rel_path.replace("/__init__.py", "")
            .replace("\\__init__.py", "")
            .replace("\\", "/")
        )
        return f"# {_pkg} package\n"

    if not content.strip():
        return content

    original = content

    # S72-C: conftest.py tiene tratamiento especial
    is_conftest = rel_path.endswith("conftest.py")
    if is_conftest:
        content = _fix_conftest_mock_order(content)

    # S72-B: renaming + Pydantic v2 para todos los .py
    if not is_conftest:
        content = _rename_functions(content)

    content = _fix_pydantic_v1(content)

    # S77-B: reordenar decoradores Pydantic (field_validator ANTES de classmethod)
    if not is_conftest:
        content = _fix_pydantic_decorator_order(content)

    # S80-C: fix declarative_base() anti-pattern en modelos que no son database.py
    # DEBE correr ANTES de S73-A para interceptar el patrón crudo antes de que se transforme
    if not is_conftest:
        content = _fix_declarative_base_import(content, rel_path)

    # S73-A: SQLAlchemy v1 → v2
    content = _fix_sqlalchemy_v1(content)

    # S102-A: promover imports silenciados por try/except ImportError: pass en router.py
    content = _fix_silent_service_import(content, rel_path)

    # S101-C: reemplazar DATABASE_URL hardcodeada por os.environ.get()
    content = _fix_database_url_hardcoded(content, rel_path)

    # S84-A: eliminar Oracle init cuando DATABASE_URL es PostgreSQL
    content = _fix_oracle_init_in_postgres_db(content, rel_path)

    # S77-A: fix parámetros Oracle inválidos en create_engine
    content = _fix_sqlalchemy_oracle_params(content)

    # S88-A: fix import desde módulo fantasma *.orm → *.models
    if not is_conftest:
        content = _fix_orm_phantom_module_import(content)

    # S89-B: eliminar imports desde módulos fantasma *.repository
    if not is_conftest:
        content = _fix_phantom_repository_import(content)

    # S90-B: redirigir imports src.benefits.* → src.contracts.*
    if not is_conftest:
        content = _fix_benefits_module_import(content)

    # S96-B: eliminar imports espurios de proyectos anteriores (prime_validator, imc, calculadora)
    if not is_conftest:
        content = _fix_spurious_utility_imports(content)

    # S96-C: renombrar clases ORM español→inglés (ContratoORM→ContractORM, etc.)
    if not is_conftest:
        content = _fix_orm_class_names_es_to_en(content)

    # S81-A / S82-A: eliminar clases ORM duplicadas en service.py (solo si models.py existe en disco)
    if not is_conftest:
        content = _fix_orm_in_service(content, rel_path, work_dir=work_dir)

    # S74-A: fix variable local que shadowea función del módulo
    if not is_conftest:
        content = _fix_local_variable_shadowing(content)

    # S75-A: fix función de módulo que redefine import con wrapper trivial (RecursionError)
    if not is_conftest:
        content = _fix_function_import_shadowing(content)

    # S74-D: advertir secretos hardcoded (log only)
    _warn_hardcoded_secrets(content, rel_path)

    if content != original:
        log.warning(
            "[S72] postprocessed %s (%d → %d chars)",
            rel_path,
            len(original),
            len(content),
        )

    return content


def postprocess_yaml_file(
    content: str, rel_path: str, oracle_involved: bool = False
) -> str:
    """S107-P2: post-procesa archivos YAML generados por LLM (docker-compose, etc.).

    Actualmente aplica:
    - Reemplazo de imágenes Oracle por postgres:16-alpine en docker-compose (S107-P2)
    """
    if not (rel_path.endswith(".yml") or rel_path.endswith(".yaml")):
        return content

    fname = rel_path.lower()
    if "docker-compose" in fname or "docker_compose" in fname:
        content = _fix_oracle_in_docker_compose(content, oracle_involved)

    return content
