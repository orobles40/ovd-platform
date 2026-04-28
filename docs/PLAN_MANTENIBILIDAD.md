# Plan de Mantenibilidad — OVD Platform Engine

> Fecha: 2026-04-28 | Investigación sobre rama `dev` (S95)
> Objetivo: código mantenible en el tiempo, fácil de refactorizar y legible.

---

## Diagnóstico general

El engine tiene una base técnica sólida: Pydantic v2, LangGraph con fan-out nativo, tests con markers, logging con contexto, manejo explícito de errores y gestión de secrets. El problema central es de **escala**: el proyecto creció de forma iterativa (sprint a sprint) y hoy concentra demasiado en pocos archivos, lo que hace difícil incorporar nuevos colaboradores, refactorizar sin miedo y encontrar rápido dónde vive cada comportamiento.

---

## Estado actual por área

### 1. Tamaño de módulos

| Archivo | Líneas | Estado |
|---------|--------|--------|
| `graph.py` | 6,773 | **CRÍTICO** |
| `routers/api_v1.py` | 1,339 | Mejorable |
| `api.py` | 1,203 | Mejorable |
| `code_postprocessor.py` | 866 | Mejorable |
| `template_loader.py` | 595 | Normal |
| `model_router.py` | 511 | Normal |

**Hallazgo clave:** `graph.py` tiene 101 funciones en un solo archivo. Contiene el estado del grafo, los 16 nodos, los schemas Pydantic de output, los reducers, los helpers de costo/tokens, la lógica de auto-generación de stubs, los postprocessors de ORM y los validadores de imports. Todo junto.

**Consecuencia práctica:** cuando se agrega un fix (ej. S96-B), hay que buscar entre 6,773 líneas. Un error en una función de 300 líneas puede romper otra de 200 líneas que está a 4,000 líneas de distancia.

---

### 2. Tipado

**Lo bueno:**
- `OVDState` usa `TypedDict` con 50+ campos tipados explícitamente
- 7 schemas Pydantic bien definidos con field validators
- 85%+ de funciones tienen type hints en parámetros y retorno
- Fan-out usa `Annotated` con reducers personalizados

**Lo mejorable:**
```python
# graph.py — 5 campos críticos sin tipo específico
fr_analysis: dict[str, Any]           # debería ser FRAnalysisOutput
sdd: dict[str, Any]                   # debería ser SDDOutput
security_result: dict[str, Any]       # debería ser SecurityAuditOutput
test_results: dict[str, Any]          # debería ser TestResultsOutput
security_scan_results: dict[str, Any] # debería ser SecurityScanOutput
```
Usar `Any` en campos del estado del grafo significa que el compilador no puede avisar si un nodo retorna la clave equivocada o con el tipo equivocado.

---

### 3. Linting y formatting

**Estado actual:**
- `pyproject.toml` solo tiene configuración de pytest
- No existe `ruff.toml`, ni `.flake8`, ni `mypy.ini`
- No existe `.pre-commit-config.yaml`
- No existe `Makefile`
- Formato del código es inconsistente entre archivos (algunos usan comillas simples, otros dobles; espaciado variable en type hints)

**Consecuencia:** cada desarrollador aplica su propio criterio. En un proyecto de 6,773 líneas eso se acumula.

---

### 4. Tests

**Lo bueno:**
- 105 archivos de test con markers por tipo (unit/integration/e2e/docker/regression)
- `conftest.py` con autouse fixtures: `mock_telemetry`, `mock_nats`, `mock_audit_logger`
- `factories.py` con helpers reutilizables: `make_llm_mock`, `make_agent_result`
- Los tests de comportamiento prueban el output del grafo, no las funciones internas

**Lo mejorable:**
- Los `test_sXX.py` de postprocessors (S88-S95) sí prueban funciones privadas directamente (`_fix_orm_phantom_module_import`, `_validate_artifacts_imports`). Esto es un anti-patrón: si renombras esa función al refactorizar, el test se rompe aunque el comportamiento sea correcto.
- No hay `pytest-cov` configurado — no se sabe qué porcentaje del código está cubierto
- No hay umbral mínimo de cobertura en CI

---

### 5. Gestión de errores

**Estado:** Sólido. No hay bare `except:` sin logging. Excepciones específicas capturadas:
```python
except asyncio.TimeoutError:    # graph.py:734
except OSError as e:            # graph.py:1441
except SyntaxError:             # graph.py:1462
except OutputParserException:   # graph.py:722
```
Todos incluyen `log.error()` con contexto y `exc_info=True` donde aplica.

**Lo mejorable:** No hay jerarquía de excepciones propias del dominio. Cuando falla algo en el ciclo, el error llega como `Exception` genérica al SSE. Con custom exceptions (`OVDCycleError`, `OVDAgentError`, `OVDValidationError`) sería más fácil filtrar y responder diferente por tipo de fallo.

---

### 6. Separación de capas

**Estado actual:**
```
api.py          ← configura FastAPI, SSE, rutas principales
routers/        ← lógica de proyectos, ciclos, stats (con SQL raw)
graph.py        ← estado + nodos + lógica de negocio + side effects + BD
model_router.py ← selección de LLM
template_loader ← templates de agentes
```

**Problema:** `graph.py` mezcla tres capas en un solo archivo:
- **Orquestación** (StateGraph, edges, fan-out)
- **Lógica de negocio** (validar imports, detectar ORM, generar stubs)
- **Persistencia** (INSERT en `ovd_cycles` desde el nodo `deliver`)

`routers/api_v1.py` usa SQL raw directamente sin abstracción:
```python
# api_v1.py:98
async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
    rows = await conn.execute("SELECT p.id, p.name ... FROM ovd_projects WHERE ...")
```
Si cambia el esquema de BD, hay que buscar todas las queries dispersas en el router.

---

### 7. Configuración centralizada

**Estado parcial:**
- `graph.py` centraliza sus variables al inicio (líneas 75-107) — bien
- `api.py` tiene variables dispersas en 3 lugares distintos
- `model_router.py`, `auth.py`, `rate_limiter.py` leen `os.environ.get()` cada uno por su cuenta
- Sin validación de que las variables requeridas existan al arrancar

**Consecuencia:** el engine puede arrancar sin `JWT_SECRET` y fallar en runtime al primer login, en lugar de fallar al inicio con un mensaje claro.

---

### 8. Documentación inline

**Estado:** Bueno. 185 bloques docstring en `graph.py`, comentarios GAP-001 a GAP-007 que explican decisiones de diseño, comentarios de sprint que registran por qué existe cada fix.

**Lo mejorable:** los comentarios de sprint (`# S94-fix`, `# S79-A`, etc.) mezclan historia de implementación con documentación de comportamiento. Son útiles hoy pero en 6 meses confunden a quien no vivió ese sprint.

---

### 9. Dependencias entre módulos

**Sin ciclos** — la jerarquía es clara:
```
api.py → graph.py → model_router.py
                  → template_loader.py
                  → nats_client.py
                  → telemetry.py
```

**Mejorable:** imports de módulos locales sin alias:
```python
import model_router    # ¿es local o de PyPI?
import template_loader # no queda claro
import nats_client
```
Un lector nuevo no distingue módulos locales de dependencias externas. La convención es usar `from . import X` o comentario explícito.

---

### 10. Patrones LangGraph y FastAPI

**Lo que está bien aplicado:**
- Fan-out nativo con `Send()` y reducers `Annotated`
- Retry loops con estado (`security_retry_count`, `qa_retry_count`)
- Dependency injection en FastAPI: `Depends(inject_current_user)`
- Checkpointer en PostgreSQL para persistencia del grafo

**Mejorable:**
- Los nodos del grafo no son funciones puras — tienen side effects (telemetría, NATS, BD). Esto es aceptable en LangGraph, pero dificulta testear un nodo en aislamiento sin mockear 3-4 dependencias distintas.

---

## Plan de acción

El plan se divide en tres fases ordenadas por impacto/esfuerzo. Cada fase es independiente — se puede ejecutar una sin la otra.

---

### Fase 1 — Estructura (impacto alto, esfuerzo alto)

**Objetivo:** que sea posible encontrar cualquier comportamiento en menos de 30 segundos.

#### 1-A — Dividir `graph.py` en módulos

Estructura propuesta:
```
src/engine/
├── graph.py              ← solo StateGraph, edges, compilación (~200 líneas)
├── state.py              ← OVDState + schemas Pydantic (~400 líneas)
├── nodes/
│   ├── __init__.py
│   ├── analyze_fr.py     ← nodo analyze_fr
│   ├── generate_sdd.py   ← nodo generate_sdd + _ensure_* helpers
│   ├── agent_executor.py ← nodo agent_executor + _run_agent_with_tools
│   ├── run_tests.py      ← nodo run_tests + _validate_artifacts_imports
│   ├── qa_review.py      ← nodo qa_review + security_audit
│   └── deliver.py        ← nodo deliver + _generate_delivery_report
├── validators/
│   ├── __init__.py
│   ├── imports.py        ← _validate_artifacts_imports
│   └── orm.py            ← _verify_orm_class_names
├── code_postprocessor.py ← ya separado ✅
├── reducers.py           ← _merge_token_usage, _keep_best_qa, _list_reset_or_add
└── helpers.py            ← _estimate_cost, _extract_usage, _truncate
```

**Criterio de éxito:** `graph.py` tiene menos de 300 líneas. Cada archivo de `nodes/` tiene menos de 700 líneas.

**Riesgo:** alto — requiere actualizar todos los imports en tests. Mitigar haciendo la división en una rama dedicada con los tests existentes como red de seguridad.

#### 1-B — Dividir `api.py`

```
src/engine/
├── api.py                ← solo app = FastAPI() + lifespan + include_router (~150 líneas)
├── session_handler.py    ← /session POST + SSE stream (~400 líneas)
└── routers/
    ├── api_v1.py         ← proyectos, ciclos, stats (ya existe)
    └── auth_router.py    ← auth (ya existe)
```

---

### Fase 2 — Calidad de código (impacto alto, esfuerzo bajo)

**Objetivo:** que el toolchain detecte problemas antes de que lleguen al grafo.

#### 2-A — Configurar `ruff` como linter y formatter

Agregar a `pyproject.toml`:
```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes (imports no usados, variables no definidas)
    "I",   # isort (orden de imports)
    "B",   # flake8-bugbear (errores comunes)
    "UP",  # pyupgrade (modernizar sintaxis Python)
    "ANN", # type annotations faltantes
]
ignore = ["ANN101", "ANN102"]  # self y cls no necesitan anotación

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ANN"]  # tests no requieren anotaciones
```

Comando de uso:
```bash
cd src/engine && .venv/bin/ruff check . --fix
cd src/engine && .venv/bin/ruff format .
```

#### 2-B — Configurar `mypy` para tipado estático

Agregar a `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.12"
strict = false          # empezar sin strict, activar gradualmente
ignore_missing_imports = true
disallow_untyped_defs = true
warn_return_any = true
```

#### 2-C — Pre-commit hooks

Crear `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

Instalar:
```bash
pip install pre-commit
pre-commit install
```

#### 2-D — Makefile para tareas comunes

```makefile
.PHONY: lint test test-unit test-cov

lint:
	cd src/engine && .venv/bin/ruff check . --fix
	cd src/engine && .venv/bin/ruff format .

test:
	cd src/engine && .venv/bin/pytest tests/ -m "not integration and not docker" -v

test-unit:
	cd src/engine && .venv/bin/pytest tests/ -m unit -v

test-cov:
	cd src/engine && .venv/bin/pytest tests/ --cov=. --cov-report=html -m "not integration and not docker"
```

---

### Fase 3 — Arquitectura de datos y configuración (impacto medio, esfuerzo medio)

**Objetivo:** que el engine falle rápido y con mensajes claros cuando algo está mal configurado.

#### 3-A — Módulo de configuración centralizado

Crear `src/engine/settings.py`:
```python
from pydantic_settings import BaseSettings

class OVDSettings(BaseSettings):
    # Base de datos
    database_url: str
    ovd_db_pool_min: int = 2
    ovd_db_pool_max: int = 10

    # LLM
    ovd_model: str = "qwen3-coder:30b"
    ovd_model_sdd: str = "qwen3-coder:30b"
    ovd_llm_timeout_secs: float = 300.0
    ovd_node_timeout_secs: float = 120.0

    # Auth
    jwt_secret: str
    ovd_access_token_ttl_hours: int = 1

    # Engine
    ovd_security_min_score: int = 70
    ovd_sse_stream_timeout_secs: float = 900.0
    ovd_secret: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = OVDSettings()  # Falla al arrancar si falta variable requerida
```

Reemplazar en todos los módulos:
```python
# Antes
_JWT_SECRET = os.environ.get("JWT_SECRET", "")

# Después
from settings import settings
_JWT_SECRET = settings.jwt_secret
```

**Beneficio:** el engine no arranca si falta `JWT_SECRET` o `DATABASE_URL`. El error es claro y en el momento correcto.

#### 3-B — Reemplazar `dict[str, Any]` en `OVDState`

```python
# Antes (graph.py)
fr_analysis: dict[str, Any]

# Después (state.py)
class FRAnalysisState(TypedDict):
    summary: str
    complexity: str
    type: str
    fr_type: str
    raw: str

fr_analysis: FRAnalysisState
```

Hacer el cambio gradual: un campo por sprint, empezando por `fr_analysis` (el más usado).

#### 3-C — Excepciones de dominio

Crear `src/engine/exceptions.py`:
```python
class OVDError(Exception):
    """Base para todas las excepciones de OVD."""

class OVDCycleError(OVDError):
    """Error durante la ejecución de un ciclo."""

class OVDAgentError(OVDError):
    """Error en la ejecución de un agente específico."""

class OVDValidationError(OVDError):
    """Error de validación de artefactos generados."""

class OVDConfigError(OVDError):
    """Configuración incorrecta o faltante."""
```

Usar en los nodos:
```python
# Antes
raise Exception(f"Agent {agent} failed: {error}")

# Después
raise OVDAgentError(f"Agent {agent} failed: {error}")
```

#### 3-D — Repository pattern para `api_v1.py`

Crear `src/engine/repositories/`:
```python
# repositories/projects.py
class ProjectRepository:
    def __init__(self, conn: psycopg.AsyncConnection):
        self.conn = conn

    async def list_by_org(self, org_id: str, include_inactive: bool = False) -> list[dict]:
        rows = await self.conn.execute(
            "SELECT id, name, ... FROM ovd_projects WHERE org_id = %s",
            (org_id,)
        )
        return [dict(r) async for r in rows]
```

Esto permite cambiar PostgreSQL por otro motor sin tocar los routers.

#### 3-E — Cobertura de tests

Agregar a `pyproject.toml`:
```toml
[tool.pytest.ini_options]
addopts = "--cov=. --cov-fail-under=60"  # Umbral inicial conservador

[tool.coverage.run]
omit = ["tests/*", "migrations/*", "alembic.ini"]
```

Instalar:
```bash
uv add --dev pytest-cov
```

---

## Resumen ejecutivo

| # | Acción | Esfuerzo | Impacto | Fase |
|---|--------|---------|---------|------|
| 1 | Configurar `ruff` en pyproject.toml | 30 min | Alto | 2 |
| 2 | Crear `Makefile` con comandos lint/test | 20 min | Medio | 2 |
| 3 | Crear `.pre-commit-config.yaml` | 20 min | Alto | 2 |
| 4 | Crear `settings.py` con Pydantic Settings | 2h | Alto | 3 |
| 5 | Crear `exceptions.py` con jerarquía | 30 min | Medio | 3 |
| 6 | Agregar `pytest-cov` con umbral 60% | 30 min | Medio | 3 |
| 7 | Extraer `state.py` de `graph.py` | 1 día | Muy alto | 1 |
| 8 | Extraer `nodes/` de `graph.py` | 3-4 días | Muy alto | 1 |
| 9 | Extraer `validators/` de `graph.py` | 1 día | Alto | 1 |
| 10 | Reemplazar 5 `dict[str, Any]` en OVDState | 1 día | Medio | 3 |
| 11 | Repository pattern en `api_v1.py` | 1 día | Medio | 3 |

**Secuencia recomendada:**
1. Empezar por las acciones 1-3 (Fase 2) — bajo esfuerzo, no rompen nada, se obtiene feedback inmediato
2. Continuar con 4-6 (Fase 3) — configuración y excepciones son fundamento para lo siguiente
3. Abordar 7-9 (Fase 1) una vez que el toolchain esté activo y los tests pasen en CI

---

## Criterios de éxito

Al completar las tres fases, el engine debe cumplir:

- `graph.py` ≤ 300 líneas
- Ningún archivo supera 800 líneas
- `ruff check .` retorna 0 errores
- `pytest --cov` reporta ≥ 60% de cobertura
- El engine no arranca si falta `DATABASE_URL` o `JWT_SECRET`
- Un desarrollador nuevo puede ubicar cualquier nodo del grafo en < 30 segundos

---

## Decisiones arquitectónicas registradas

### Gunicorn + Uvicorn — decisión: NO implementar (2026-04-28)

**Contexto:** Se evaluó agregar Gunicorn como process manager sobre Uvicorn para escalar el engine horizontalmente (múltiples workers).

**Decisión:** mantener Uvicorn single-process (`workers=1`). Documentado en `main.py`.

**Razones:**

1. **Estado en memoria no compartible.** `_graph_tasks`, `_event_queues` y `_stream_done` en `api.py` son diccionarios Python en memoria. Con múltiples procesos Gunicorn, el proceso que recibe el SSE puede ser distinto al que creó la task del grafo — y no encontrará nada en su memoria local. El SSE se rompe irremediablemente.

2. **El bottleneck no es CPU.** Cada ciclo pasa la mayor parte del tiempo esperando respuesta de Ollama o la API de Anthropic (I/O de red). `asyncio` maneja decenas de ciclos concurrentes en un solo proceso sin bloquear. Agregar workers de proceso no acelera las llamadas al LLM.

3. **El grafo LangGraph es stateful vía PostgreSQL.** El checkpointer ya comparte estado entre sesiones a través de la BD — ese problema está resuelto. El problema es el estado efímero del SSE handler, no el del grafo.

**Cuándo reevaluar:** si en el futuro se implementa el SSE handler con estado externo (Redis pub/sub o NATS JetStream en lugar de `asyncio.Queue`), el bloqueo desaparece y Gunicorn vuelve a ser una opción válida.

**Prerrequisito para multi-process:**
```
Estado actual:  cliente SSE → asyncio.Queue (en memoria del proceso)
Estado futuro:  cliente SSE → Redis pub/sub o NATS JetStream (externo al proceso)
```

---

## Notas de implementación

- La Fase 1 (división de `graph.py`) debe hacerse en una rama separada (`refactor/graph-split`) con los ~1,507 tests actuales como red de seguridad
- Los tests de `test_sXX.py` que prueban funciones privadas deberán actualizarse para importar desde el nuevo módulo
- Cada commit de la Fase 1 debe mantener los tests en verde — no mezclar refactor con fix de comportamiento
- La Fase 2 no requiere rama separada — es configuración, no cambia código productivo
