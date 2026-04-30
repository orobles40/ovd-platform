# PLAN S104 — Estabilización QA: Determinismo + Anti-Circular-Import + Workspace Hygiene

**Fecha:** 2026-04-30
**Base:** INFORME_PRUEBA_S103.md + investigación repos + análisis engine
**Objetivo:** QA ≥ 80 estable en 3 ciclos consecutivos con workspace persistente

---

## Diagnóstico raíz (evidencia)

| Ciclo | Workspace | QA | Retries | Causa confirmada |
|-------|-----------|----|---------|----|
| S103-first | tmpdir limpio | **90** | 0 | — |
| S103-bis | sucio (S102) | 60 | 3 | archivos S102 conflictivos |
| S103-clean | limpio registrado | 50 | 3 | circular self-import + temperature=0.3 |

### Causa 1 — temperature=0.3 en agentes implementadores (RAÍZ PRINCIPAL)
`backend`, `frontend`, `database`, `devops` NO están en `_STRUCTURED_ROLES` → corren a `temperature=0.3`.
Con qwen3-coder:30b MoE, temperatura 0.3 produce outputs no determinísticos entre ejecuciones con el mismo prompt.
**Evidencia:** el mismo FR produce `verify_password` en un ciclo y `auth_password` en otro.

### Causa 2 — Sin seed en ChatOllama
`ChatOllama(model=..., num_predict=8192, num_ctx=32768, temperature=0.3)` no fija `seed`.
Sin seed, dos llamadas idénticas producen outputs diferentes incluso con temperatura baja.

### Causa 3 — Circular self-import no detectado
El LLM generó `from src.auth.services import verify_password` dentro del propio `src/auth/services.py`.
`_check_undefined_import_names()` (S103-P2) detecta imports de módulos inexistentes, pero NO detecta
cuando el módulo importado es el mismo archivo que se está validando.

### Causa 4 — `__pycache__` residual entre ciclos
La limpieza del workspace preservó `__pycache__/conftest.cpython-312-pytest-9.0.3.pyc`.
Python puede cargar bytecode compilado de un ciclo anterior en lugar del archivo nuevo generado.

---

## Fuentes de investigación

### kyrolabs/awesome-agents
- Frameworks estables (LangGraph, Semantic Kernel) usan tmpdir-por-ciclo como arquitectura, no workaround
- Structured output como contrato de interfaz entre agentes: `GeneratedFile(path, content, imports: list[str])`
- Context isolation: el agente validador NO hereda el contexto del generador (reduce sesgo de confirmación)

### obra/superpowers
- **verification-before-completion (5 pasos):** IDENTIFY → RUN → READ → VERIFY → CLAIM
  Aplicado: antes de marcar ciclo exitoso, ejecutar `python -c "import <module>"` y verificar exit code 0
- **Type consistency check en el plan:** generar primero un contrato de nombres `{función: firma}` antes de generar código
- **Spec reviewer independiente:** comparar imports de tests vs FunctionDef del módulo fuente con AST

### NousResearch/hermes-agent
- **Error taxonomy:** `format_error` (código inválido estructuralmente) → estrategia específica: regenerar con contrato explícito, NO retry genérico
- **AST parse pre-import:** `ast.parse()` sobre todo código generado antes de ejecutar pytest — si falla, descarta sin importar
- **`json.JSONDecoder().raw_decode()`** para parsear output Ollama (modelos locales mezclan texto con JSON)
- **Jittered backoff con context compression** en retries — no reenviar el mismo prompt

---

## Fixes propuestos

### S104-A — temperature=0 + seed=42 para agentes implementadores (CRÍTICO)

**Archivo:** `src/engine/model_router.py`

**Cambio 1:** Agregar roles implementadores a `_STRUCTURED_ROLES`:
```python
# Antes:
_STRUCTURED_ROLES = {"analyzer", "sdd", "qa", "security", "router"}

# Después:
_STRUCTURED_ROLES = {"analyzer", "sdd", "qa", "security", "router",
                     "backend", "frontend", "database", "devops"}
```

**Cambio 2:** Agregar `seed` a `ChatOllama`:
```python
return ChatOllama(
    model=config.model,
    base_url=base_url,
    num_predict=8192,
    num_ctx=32768,
    temperature=config.temperature,  # → 0.0 para todos los roles
    reasoning=False,
    seed=42,  # S104-A: determinismo entre ciclos
)
```

**Impacto esperado:** elimina 70-80% de la variabilidad entre ciclos. El mismo prompt + mismo modelo + seed fijo → output reproducible.

**Riesgo:** temperatura 0 puede reducir creatividad del LLM para resolver casos ambiguos. Mitigación: el `temperature_override=0.1` en retries S97-E ya está implementado y sirve como escape hatch.

---

### S104-B — Postprocessor anti-circular-import (CRÍTICO)

**Archivo:** `src/engine/graph.py` — extender `_check_undefined_import_names()`

**Patrón a detectar:**
```python
# src/auth/services.py contiene:
from src.auth.services import verify_password  # ← se importa a sí mismo
```

**Implementación:**
```python
def _detect_circular_self_imports(directory: str) -> tuple[bool, str]:
    """S104-B: detecta módulos que se importan a sí mismos."""
    import ast as _ast
    from pathlib import Path as _Path
    base = _Path(directory)
    errors = []
    for py_file in base.rglob("*.py"):
        rel = py_file.relative_to(base)
        if any(p in {"__pycache__", ".venv"} for p in rel.parts):
            continue
        # módulo dotted de este archivo: src/auth/services.py → src.auth.services
        mod_dotted = str(rel).replace("/", ".").removesuffix(".py")
        try:
            tree = _ast.parse(py_file.read_text(encoding="utf-8"))
            for node in _ast.walk(tree):
                if isinstance(node, _ast.ImportFrom) and node.module == mod_dotted:
                    names = [a.name for a in node.names]
                    errors.append(
                        f"[S104-B] Circular self-import en {rel}: "
                        f"`from {mod_dotted} import {', '.join(names)}`"
                    )
                elif isinstance(node, _ast.Import):
                    for alias in node.names:
                        if alias.name == mod_dotted:
                            errors.append(
                                f"[S104-B] Circular self-import en {rel}: `import {mod_dotted}`"
                            )
        except (OSError, SyntaxError):
            continue
    ok = len(errors) == 0
    return ok, "\n".join(errors)
```

**Llamada:** en `run_tests()` junto a P2 (S103), antes de ejecutar pytest.

**Postprocessor adicional:** en `code_postprocessor.py`, detectar y eliminar la línea de auto-import:
```python
def _fix_circular_self_import(content: str, module_dotted: str) -> str:
    """S104-B: elimina from X import Y cuando X es el propio módulo."""
    import re as _re
    pattern = rf"^from {re.escape(module_dotted)} import .+$"
    return _re.sub(pattern, "", content, flags=_re.MULTILINE)
```

---

### S104-C — Limpieza `__pycache__` en session_create (ALTO)

**Archivo:** `src/engine/api.py`

Después de resolver `resolved_directory` y antes de invocar el grafo:
```python
# S104-C: limpiar __pycache__ para evitar bytecode residual de ciclos anteriores
if resolved_directory:
    import shutil as _shutil
    from pathlib import Path as _ppath
    for _cache_dir in _ppath(resolved_directory).rglob("__pycache__"):
        try:
            _shutil.rmtree(_cache_dir, ignore_errors=True)
        except Exception:
            pass
    log.info("session_create: __pycache__ limpiado en %s", resolved_directory)
```

---

### S104-D — Restricción SDD docker-compose → devops (ALTO)

**Archivo:** `src/engine/templates/system_sdd.md`

Agregar en la sección de reglas de asignación de agentes:

```markdown
**RESTRICCIÓN ABSOLUTA de infraestructura (S104-D):**
Los siguientes artefactos SIEMPRE deben asignarse al agente `devops`, sin excepción:
- `docker-compose.yml` / `docker-compose.*.yml`
- `Dockerfile` / `Dockerfile.*`
- `.github/workflows/*.yml`
- `nginx.conf`
- `scripts/deploy.sh`, `scripts/health-check.sh`

NUNCA asignar estos artefactos a `backend` o `frontend`.
Si el FR no requiere infraestructura, el agente `devops` puede omitirse del SDD.
```

---

### S104-E — Error taxonomy para retry strategy (MEDIO)

**Archivo:** `src/engine/graph.py` — nodo `run_tests` / `update_test_retry`

Clasificar el error antes de construir el feedback para el retry:

```python
def _classify_test_error(output: str) -> str:
    """S104-E: taxonomía de errores para estrategia de retry específica."""
    if "circular" in output.lower() or "partially initialized" in output.lower():
        return "circular_import"
    if "ImportError" in output or "ModuleNotFoundError" in output:
        return "import_error"
    if "cannot import name" in output:
        return "naming_mismatch"
    if "SyntaxError" in output:
        return "syntax_error"
    if "AssertionError" in output:
        return "assertion_error"
    return "generic"
```

Para `circular_import` y `naming_mismatch`: inyectar el type contract completo (S103-P1) al inicio del mensaje de retry, no solo el error genérico.

---

## Plan de validación

### Criterio de éxito S104
- QA ≥ 80 en al menos 2 de 3 ciclos consecutivos con workspace persistente
- 0 errores de circular self-import en los ciclos
- Duración ≤ 15 minutos por ciclo (sin retries)

### Protocolo de 3 ciclos
```
Ciclo 1: workspace limpio (borrar todo excepto informes)
Ciclo 2: sobre el workspace generado por Ciclo 1 (modo incremental simulado)
Ciclo 3: workspace limpio nuevamente (comparar con Ciclo 1)
```
Si Ciclo 1 ≈ Ciclo 2 ≈ Ciclo 3: fixes son efectivos, QA es reproducible.

---

## Orden de implementación

```
1. S104-A (model_router.py)     ← impacto mayor, cambio mínimo
2. S104-B (graph.py + code_postprocessor.py)  ← fix circular import
3. S104-C (api.py)              ← limpieza __pycache__
4. S104-D (system_sdd.md)       ← template
5. S104-E (graph.py)            ← retry taxonomy
6. test_s104.py                 ← tests de regresión
7. 3 ciclos de validación       ← medir QA estable
```

---

## Argumentación de prioridades

**¿Por qué S104-A primero?**
La temperatura 0.3 es la causa raíz de la variabilidad. Sin fijarla, cualquier otro fix puede parecer efectivo en un ciclo y fallar en el siguiente. Es el cambio con mayor relación impacto/riesgo: 2 líneas de código, elimina 70-80% de variabilidad.

**¿Por qué S104-B antes de S104-C?**
El circular import es un bug determinístico — aparecerá siempre que el LLM genere ese patrón, independientemente del estado del workspace. S104-C (pycache) es una higiene importante pero no elimina bugs de código.

**¿Por qué no usar tmpdir-por-ciclo como arquitectura permanente?**
El tmpdir elimina el problema de workspace sucio pero impide el modo incremental (ÉPICA-1). La limpieza selectiva (pycache + archivos Python obsoletos) es el camino correcto para llegar a ÉPICA-1.
