"""
S72-B: Post-procesador de código Python generado por LLM.
S72-C: Fix orden mock oracledb en conftest.py.
S73-A: SQLAlchemy v1 → v2 (declarative_base → DeclarativeBase).
S74-A: Fix variable local que shadowea función del mismo módulo.
S74-D: Detectar secretos hardcoded y SHA-256 para passwords (log only).

Transformaciones aplicadas en _write_artifacts() antes de escribir al disco:
- Renombra funciones de español a inglés (AST NodeTransformer + call sites)
- Convierte @validator (Pydantic v1) → @field_validator + @classmethod (v2)
- Convierte @root_validator → @model_validator
- Convierte orm_mode/allow_population_by_field_name → ConfigDict
- Corrige orden de mock oracledb en conftest.py
- Convierte declarative_base() → DeclarativeBase class (SQLAlchemy 2.x)
- Renombra variable local que shadowea función del módulo (UnboundLocalError)
- Advierte sobre secretos hardcoded y SHA-256 para passwords
"""

from __future__ import annotations

import ast
import re
import logging

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
    _has_v1_import = bool(re.search(r"from\s+pydantic\s+import[^\n]*\bvalidator\b", code))
    _has_v2_decorator = "@field_validator" in code or "@model_validator" in code
    _has_orm_mode = "orm_mode" in code or "allow_population_by_field_name" in code

    if not _has_v1_decorator and not _has_v1_import and not _has_v2_decorator and not _has_orm_mode:
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
        if stripped.startswith("@field_validator(") or stripped.startswith("@model_validator("):
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
            lambda m: f"{m.group(1)}class {m.group(2)}(DeclarativeBase):\n{m.group(1)}    pass",
            code,
            flags=re.MULTILINE,
        )
        changed = True

    if changed:
        log.warning("[S73-A] SQLAlchemy v1→v2: declarative_base() → DeclarativeBase class")

    return code


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
            rf'(?<![.\w]){re.escape(old)}\s*=\s*(?!=)',
            f'{new} = ',
            changed_code,
        )
        log.warning("[S74-A] local shadow fix: %s → %s", old, new)

    return changed_code


# ---------------------------------------------------------------------------
# S74-D — Detección de secretos hardcoded (log only)
# ---------------------------------------------------------------------------

_SECRET_VAR_KEYWORDS = frozenset({'key', 'secret', 'password', 'token', 'api_key', 'passwd', 'auth'})
_SHA256_PWD_RE = re.compile(r'hashlib\.sha256\([^)]+\.encode\(\)\)\.hexdigest\(\)')


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
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                val = node.value.value
                if val and val not in ('', 'changeme', 'your-secret', 'your-secret-key-here'):
                    log.warning(
                        "[S74-D] %s:%d secret hardcoded '%s' — usar os.environ.get('%s')",
                        rel_path, node.lineno, target.id, target.id.upper(),
                    )

    if _SHA256_PWD_RE.search(code):
        log.warning("[S74-D] %s: SHA-256 para password detectado — usar passlib[bcrypt]", rel_path)

    return code  # log only en S74 — no modifica el código


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
        re.search(r"^\s*(import oracledb|from oracledb\s+import)", content, re.MULTILINE)
    )
    has_mock = "sys.modules['oracledb']" in content or 'sys.modules["oracledb"]' in content

    if not has_oracledb_import and not has_mock:
        return content  # no hay oracledb — no tocar

    # Verificar si ya está en orden correcto
    if has_mock and has_oracledb_import:
        mock_pos = min(
            (content.find("sys.modules['oracledb']") if "sys.modules['oracledb']" in content else len(content)),
            (content.find('sys.modules["oracledb"]') if 'sys.modules["oracledb"]' in content else len(content)),
        )
        import_pos = min(
            (content.find("import oracledb") if "import oracledb" in content else len(content)),
            (content.find("from oracledb") if "from oracledb" in content else len(content)),
        )
        if mock_pos < import_pos:
            return content  # ya está correcto

    log.warning("[S72-C] corrigiendo orden mock oracledb en conftest.py")

    # Eliminar imports directos de oracledb (el mock los reemplaza)
    content = re.sub(r"^\s*import oracledb\s*\n", "", content, flags=re.MULTILINE)
    content = re.sub(r"^\s*from oracledb\s+import[^\n]*\n", "", content, flags=re.MULTILINE)

    # Asegurar import pytest
    if "import pytest" not in content:
        content = "import pytest\n" + content

    # Inyectar bloque mock al inicio (preservar shebang/encoding si los hay)
    lines = content.split("\n")
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#!") or stripped.startswith("# -*-") or stripped.startswith("# coding"):
            insert_at = i + 1
        else:
            break

    lines.insert(insert_at, _MOCK_HEADER.rstrip())
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point: postprocess_python_file
# ---------------------------------------------------------------------------

def postprocess_python_file(content: str, rel_path: str) -> str:
    """
    S72-B/C: post-procesa un archivo Python generado por LLM.

    Para conftest.py: corrige orden mock oracledb (S72-C).
    Para otros .py:  renombra español→inglés + Pydantic v1→v2 (S72-B).

    Retorna el contenido transformado (o el original si no hay cambios).
    """
    if not rel_path.endswith(".py") or not content.strip():
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

    # S73-A: SQLAlchemy v1 → v2
    content = _fix_sqlalchemy_v1(content)

    # S74-A: fix variable local que shadowea función del módulo
    if not is_conftest:
        content = _fix_local_variable_shadowing(content)

    # S74-D: advertir secretos hardcoded (log only)
    _warn_hardcoded_secrets(content, rel_path)

    if content != original:
        log.warning(
            "[S72] postprocessed %s (%d → %d chars)",
            rel_path, len(original), len(content),
        )

    return content
