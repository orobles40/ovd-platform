# PLAN S108 — Pytest verde + calidad estructural + roadmap arquitectural

**Fecha:** 2026-05-04  
**Sprint:** S108  
**Autor:** Omar Robles + Claude Sonnet 4.6  
**Baseline:** S107 — QA 94/100, pytest FAIL (Pydantic Date + S79-C falso positivo)  
**Target S108:** QA ≥ 95, pytest PASS sin retries

---

## 1. Contexto y motivación

S107 resolvió el problema estructural de naming cross-contexto (QA 52→94). El objetivo de S108
es llevar el ciclo a un estado donde **pytest pase sin retries** — lo que requiere eliminar los
dos fallos técnicos restantes y mejorar la calidad del feedback de error para que los retries
sean más efectivos cuando inevitablemente ocurran.

### Estado actual (post-S107)

| Componente | Estado | Evidencia |
|---|---|---|
| QA score | 94/100 ✅ | Dos ciclos consecutivos, sin varianza |
| Security | 100/100 ✅ | bypass dev (S48-A) activo |
| Naming consistency | ✅ | `deactivate_contract` en router y services |
| docker-compose | ✅ | `postgres:16-alpine` — sin Oracle |
| Architecture Gate | ✅ | Nodo en SSE stream |
| pytest | ❌ FAIL | TypeError Pydantic Date + S79-C falso positivo |
| Workspace creación | ✅ (fix extra) | `_write_artifacts` crea dir si no existe |

### Fallos confirmados en ciclo d5259ffd y 0426dd25

```
# Fallo 1: Pydantic no reconoce tipos SQLAlchemy
src/contracts/models.py:16: in ContratoCreate(BaseModel)
  pydantic._internal._generate_schema.py: unknown type — Date (SQLAlchemy)

# Fallo 2: S79-C falso positivo bloquea feedback de retry
[S79-C] ⚠️ DATABASE_URL INCONSISTENTE con el FR:
  - El FR solicita Oracle pero database.py tiene URL PostgreSQL
# (El FR dice "NO Oracle" — la detección por keyword es incorrecta)
```

---

## 2. Investigación y evidencia externa

Se investigaron 11 fuentes externas (repos + papers + guías):

| Fuente | Hallazgo clave para S108 |
|---|---|
| **Anthropic — Building Effective Agents** | "Invest in tool definition, not prompt complexity." Separar ORM/Pydantic con ejemplos canónicos en el template es más efectivo que cualquier postprocesador. |
| **LangGraph best practices** | Routing sobre datos validados (structured output), NO sobre raw string. S79-C viola este principio al hacer `"oracle" in fr_text.lower()`. |
| **CrewAI `output_pydantic`** | Guardrails funcionales con feedback al LLM — no corrección silenciosa en disco. El postprocesador de Pydantic Date debe además inyectar la corrección como lesson. |
| **Lilian Weng — Reflexion framework** | Distingue dos tipos de falla: hallucination (mismo error) vs. planning inefficiency. OVD no clasifica errores de pytest — todo fallo activa el mismo retry genérico. |
| **OpenHands SDK** | Residuos entre sesiones (service.py + services.py) son el equivalent de "malformed tool history". Fix: condensación/cleanup antes del siguiente paso. |
| **LangGraph source** | `RetryPolicy` nativo node-level no contamina estado. OVD usa `security_retry_count` en TypedDict — es más frágil. Migrar en S109. |
| **Superpowers methodology** | Two-stage review: spec compliance PRIMERO, code quality SEGUNDO. OVD hace las dos cosas en QA a la vez, lo que puede generar penalizaciones confusas. |
| **obra/superpowers — systematic-debugging** | 4 fases: root cause → defense-in-depth → condition-based-waiting → verificación. S79-C usa la primera fase incorrectamente (keyword matching en lugar de root cause). |

### Conclusión del análisis externo

Tres insights transversales de 3+ fuentes cada uno:

1. **Structured output > keyword matching en cualquier decisión de routing** (Anthropic, LangGraph, Superpowers, Lilian Weng). S79-C debe usar `oracle_involved` del `fr_analysis` resuelto por deepseek-r1:14b.

2. **Separación estricta de layers en templates genera más código correcto que postprocesadores** (Anthropic, CrewAI, LangGraph best practices). La confusión ORM/Pydantic es un problema de instrucción, no de postprocessing.

3. **Clasificar tipos de fallo antes del retry duplica la efectividad del feedback** (Reflexion, Anthropic evaluator-optimizer, OpenHands error recovery).

---

## 3. Propuestas S108

### P1 — Fix S79-C: usar `oracle_involved` del fr_analysis (CRÍTICO)

**Problema:** `_verify_db_url_matches_fr` hace `"oracle" in fr_lower` sobre el texto raw del FR. El FR "PostgreSQL (NO Oracle)" contiene la palabra Oracle → falso positivo → feedback de error incorrecto se inyecta en el retry → LLM confundido → ciclo se degrada.

**Root cause (Superpowers systematic-debugging):** La función usa keyword matching en lugar de la decisión semántica ya resuelta por el analyzer (`deepseek-r1:14b` con structured output).

**Fix:**

```python
# graph.py — en run_tests, ANTES de llamar a _verify_db_url_matches_fr:
_fr_analysis = state.get("fr_analysis", {})
_oracle_involved = _fr_analysis.get("oracle_involved", True)  # True = conservador

# Cambiar firma de la función (graph.py o code_postprocessor.py):
def _verify_db_url_matches_fr(
    work_dir: str,
    fr_text: str,
    oracle_involved: bool,  # ← NUEVO parámetro
) -> str:
    # ANTES (S79-C):
    # _fr_wants_oracle = any(kw in fr_text.lower() for kw in ("oracle", "oracledb", "xepdb"))
    
    # DESPUÉS (S108-A):
    _fr_wants_oracle = oracle_involved  # usa decisión del analizador semántico
    ...
```

**Impacto estimado:** elimina el falso positivo permanentemente. El mensaje erróneo deja de contaminar el feedback de retry. Estimado: +3 a +8 pts QA en ciclos con "NO Oracle".

**Esfuerzo:** 1-2 horas. Cambio de 1 línea en el cuerpo + firma + call site en `run_tests`.

**Tests a agregar en `test_s108.py`:**
- `test_oracle_involved_false_no_genera_warning_S79C` — FR con "NO Oracle", `oracle_involved=False` → ningún warning
- `test_oracle_involved_true_genera_warning_S79C` — FR con Oracle real, `oracle_involved=True` → warning correcto
- `test_negacion_en_fr_text_no_activa_oracle` — verificar que la función no hace keyword matching

---

### P2 — Fix Pydantic Date: separación ORM/Pydantic en template + postprocesador (ALTO)

**Problema:** El agente backend genera `from sqlalchemy import Date` en schemas Pydantic. SQLAlchemy's `Date` es desconocido para Pydantic → `TypeError` en collection time de pytest.

**Root cause (Anthropic — poka-yoke):** El template `system_backend_python.md` no separa explícitamente que ORM y Pydantic schemas usan imports distintos para los mismos tipos.

**Fix en dos capas:**

#### Capa 1 — Template (instrucción explícita)

Agregar sección en `system_backend_python.md`:

```markdown
## SEPARACIÓN CRÍTICA — ORM vs Pydantic schemas (S108-B)

**REGLA ABSOLUTA: NUNCA usar tipos SQLAlchemy en schemas Pydantic.**

### En ORM (models.py, entities.py) — usa SQLAlchemy types:
```python
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column

class ContratoORM(Base):
    fecha_inicio: Mapped[date] = mapped_column(Date)  # Date de SQLAlchemy
```

### En schemas Pydantic (schemas.py, models.py para BaseModel) — usa Python types:
```python
from datetime import date, datetime  # ← SIEMPRE Python nativo
from pydantic import BaseModel

class ContratoCreate(BaseModel):
    fecha_inicio: date   # ← Python date, NO sqlalchemy.Date
    # PROHIBIDO: fecha_inicio: Date  (si Date viene de sqlalchemy)
```

**Tabla de equivalencias obligatoria:**
| SQLAlchemy (solo en ORM) | Python/Pydantic (schemas) |
|---|---|
| `Date` | `date` (from datetime) |
| `DateTime` | `datetime` (from datetime) |
| `Boolean` | `bool` |
| `Integer` | `int` |
| `Float`, `Numeric` | `float` |
| `String`, `Text` | `str` |
```

#### Capa 2 — Postprocesador (safety net)

Agregar en `code_postprocessor.py`:

```python
_SQLALCHEMY_DATE_IN_PYDANTIC_RE = re.compile(
    r"^from\s+sqlalchemy(?:\s+import|\.\w+\s+import).*\bDate\b",
    re.MULTILINE,
)

def _fix_sqlalchemy_date_in_pydantic_schemas(content: str, rel_path: str) -> str:
    """S108-B: reemplaza Date de SQLAlchemy por date de datetime en schemas Pydantic.
    
    Solo aplica a archivos que contienen BaseModel (son schemas Pydantic).
    En archivos ORM puros, Date de SQLAlchemy es correcto y no se toca.
    """
    if "BaseModel" not in content:
        return content  # archivo ORM puro, no tocar
    if not _SQLALCHEMY_DATE_IN_PYDANTIC_RE.search(content):
        return content
    
    # Agregar import datetime si no existe
    if "from datetime import" not in content:
        content = "from datetime import date, datetime\n" + content
    
    # Remover Date del import SQLAlchemy
    def _remove_date_from_sqlalchemy_import(m: re.Match) -> str:
        line = m.group(0)
        names = [n.strip() for n in re.split(r",\s*", line.split("import")[1])]
        names = [n for n in names if n not in ("Date", "DateTime")]
        if not names:
            return ""  # eliminar línea completa si solo tenía Date/DateTime
        return line.split("import")[0] + "import " + ", ".join(names)
    
    content = _SQLALCHEMY_DATE_IN_PYDANTIC_RE.sub(_remove_date_from_sqlalchemy_import, content)
    log.warning("[S108-B] Pydantic Date → datetime.date en %s", rel_path)
    return content
```

Registrar en `postprocess_python_file()` antes de los transformers AST.

**Impacto estimado:** elimina el `TypeError: unknown type` en pytest. Con ambas capas activas, el LLM genera código correcto en primera ronda y el postprocesador actúa como safety net.

**Esfuerzo:** 3-4 horas (template + postprocesador + tests).

**Tests a agregar:**
- `test_pydantic_date_reemplazado_en_schema` — schema con `Date` SQLAlchemy → `date` Python
- `test_orm_date_no_tocado` — modelo ORM con `Date` → no se modifica
- `test_template_separa_orm_de_pydantic` — verificar que sección existe en template

---

### P3 — Cleanup service.py + services.py coexistencia (MEDIO)

**Problema:** El fan-out de agentes puede generar `service.py` (vacío/residual) Y `services.py` (canónico) en el mismo directorio. `sync_service_imports` (S107-P3) puede leer el incorrecto.

**Root cause (OpenHands — contamination between sessions):** Residuos de ciclos anteriores o de archivos stub generados por S102-A pueden coexistir con el archivo real.

**Fix en `code_postprocessor.py`:**

```python
def _remove_duplicate_service_files(work_dir: str) -> list[str]:
    """S108-C: si service.py y services.py coexisten en el mismo dir,
    preserva services.py como canónico y elimina service.py.
    """
    import pathlib
    fixes: list[str] = []
    base = pathlib.Path(work_dir)
    
    for services_file in base.rglob("services.py"):
        if "test" in services_file.name:
            continue
        service_file = services_file.parent / "service.py"
        if not service_file.exists():
            continue
        
        services_content = services_file.read_text(encoding="utf-8")
        service_content = service_file.read_text(encoding="utf-8")
        
        if services_content.strip() == service_content.strip():
            # Idénticos: eliminar el residual
            service_file.unlink()
            fixes.append(f"eliminado {service_file} (idéntico a services.py)")
        elif len(service_content.strip()) < 50:
            # service.py es un stub vacío: eliminar
            service_file.unlink()
            fixes.append(f"eliminado {service_file} (stub vacío)")
        else:
            # Ambos tienen contenido: services.py es canónico, loggear diferencia
            log.warning(
                "[S108-C] %s y services.py difieren — preservando services.py",
                service_file
            )
            fixes.append(f"WARNING: {service_file} difiere de services.py")
    
    return fixes
```

Llamar como **primer paso** en `sync_service_imports()` (antes de construir el alias map).

**Impacto estimado:** elimina la ambigüedad de imports. `sync_service_imports` siempre trabaja con `services.py` como única fuente de verdad.

**Esfuerzo:** 1-2 horas.

---

### P4 — Clasificación de tipos de fallo en feedback de pytest (ALTO)

**Motivación (Lilian Weng — Reflexion):** "Detecting two distinct failure types: hallucination (repeated identical action) vs. planning inefficiency." OVD inyecta todo el output de pytest sin clasificar → el LLM no sabe qué tipo de corrección aplicar.

**Fix en `run_tests` (graph.py):**

```python
def _classify_pytest_failures(output: str) -> dict[str, list[str]]:
    """S108-D: clasifica errores de pytest por tipo para feedback diferenciado."""
    return {
        "import_errors":    re.findall(r"((?:ModuleNotFoundError|ImportError)[^\n]+)", output),
        "type_errors":      re.findall(r"((?:TypeError|ValidationError)[^\n]+)", output),
        "name_errors":      re.findall(r"((?:AttributeError|NameError)[^\n]+)", output),
        "assertion_errors": re.findall(r"((?:AssertionError)[^\n]+)", output),
        "fixture_errors":   re.findall(r"(fixture\s+'[^']+'\s+not\s+found)", output),
    }

def _build_typed_retry_feedback(classified: dict[str, list[str]]) -> str:
    """Construye feedback de retry con instrucción específica por tipo de error."""
    sections: list[str] = []
    
    if classified["type_errors"]:
        sections.append(
            "## ERRORES DE TIPO (corregir PRIMERO)\n"
            "- Si ves `Date` de SQLAlchemy en un schema Pydantic → reemplazar por "
            "`from datetime import date` y usar `date` como tipo.\n"
            f"Errores: {classified['type_errors'][:3]}"
        )
    if classified["import_errors"]:
        sections.append(
            "## ERRORES DE IMPORT\n"
            "- Verificar que el módulo importado existe en el workspace.\n"
            "- Verificar que el nombre de la función coincide exactamente con services.py.\n"
            f"Errores: {classified['import_errors'][:3]}"
        )
    if classified["name_errors"]:
        sections.append(
            "## ERRORES DE NOMBRE (naming mismatch)\n"
            "- Consultar el Architecture Contract VINCULANTE al inicio de este mensaje.\n"
            "- NUNCA renombrar funciones entre services.py, router.py y tests.\n"
            f"Errores: {classified['name_errors'][:3]}"
        )
    if classified["assertion_errors"]:
        sections.append(
            "## ERRORES DE LÓGICA\n"
            "- El código compila pero la lógica de negocio es incorrecta.\n"
            f"Errores: {classified['assertion_errors'][:3]}"
        )
    
    return "\n\n".join(sections) if sections else ""
```

Integrar en `update_test_retry` para que el `retry_feedback` incluya la sección clasificada antes del output raw de pytest.

**Impacto estimado:** reduce el número de retries necesarios en 30-50% para ciclos que fallan por TypeError o ImportError (los más comunes). El LLM recibe instrucción específica en lugar de un dump de traceback.

**Esfuerzo:** 3-4 horas.

---

### P5 — ADR-005: Negación semántica en detección de keywords (BAJO, ARQUITECTURAL)

**Motivación:** La raíz del GAP-4 (negación semántica) es sistémica: cualquier detector de keywords (Oracle, PostgreSQL, React, etc.) puede ser activado por "NO X" o "excepto X". Esto afecta a S79-C y potencialmente a otros nodos.

**Decisión propuesta para ADR-005:**

> **Regla:** Cualquier decisión de routing o configuración basada en keywords del FR debe usar
> el campo `fr_analysis` resuelto por el analyzer LLM (structured output con deepseek-r1:14b),
> NO regex/keyword sobre el texto raw del FR.
>
> **Único caso permitido de keyword en raw FR:** detección de stack (Python vs TypeScript vs Java)
> cuando el `fr_analysis` no incluye ese campo. En ese caso: usar negation-aware regex:
> `r"(?<!no\s)(?<!sin\s)(?<!not\s)\boracle\b"` con lookbehind de 3-4 palabras.

Documentar como ADR-005 para establecer el patrón formal.

**Esfuerzo:** 1 hora (solo documentación + regex helper reutilizable).

---

## 4. Orden de implementación

```
Día 1:
  P1: Fix S79-C (1-2h)   — impacto alto, esfuerzo bajo
  P3: Cleanup service.py  — impacto medio, esfuerzo bajo, prerequisito de P2

Día 2:
  P2: Pydantic Date       — template (1h) + postprocesador (2h) + tests (1h)

Día 3:
  P4: Clasificación errores pytest  — impacto alto en retries, esfuerzo medio
  P5: ADR-005             — documentación, 1h

Día 4:
  test_s108.py            — cobertura de todos los mecanismos
  Ciclo de validación     — target: pytest PASS sin retries
```

---

## 5. Tests obligatorios (test_s108.py)

| # | Clase | Test | Valida |
|---|---|---|---|
| 1 | `TestS79CFix` | `test_oracle_involved_false_no_warning` | `oracle_involved=False` → sin warning S79-C |
| 2 | `TestS79CFix` | `test_oracle_involved_true_warning` | `oracle_involved=True` + DB PostgreSQL → warning correcto |
| 3 | `TestS79CFix` | `test_negacion_no_oracle_en_fr_no_warning` | FR "NO Oracle", `oracle_involved=False` → sin warning |
| 4 | `TestS79CFix` | `test_function_no_hace_keyword_matching` | `_verify_db_url_matches_fr` no inspecciona el texto del FR |
| 5 | `TestPydanticDateFix` | `test_date_sqlalchemy_en_schema_reemplazado` | `Date` de SA en BaseModel → `date` de datetime |
| 6 | `TestPydanticDateFix` | `test_date_orm_no_tocado` | ORM sin BaseModel → `Date` SA intacto |
| 7 | `TestPydanticDateFix` | `test_datetime_sqlalchemy_en_schema_reemplazado` | `DateTime` → `datetime` |
| 8 | `TestPydanticDateFix` | `test_import_datetime_agregado_si_falta` | Agrega `from datetime import date` si no existe |
| 9 | `TestPydanticDateFix` | `test_template_contiene_seccion_separacion` | Sección SEPARACIÓN CRÍTICA en template |
| 10 | `TestServiceFileCleanup` | `test_service_identico_eliminado` | service.py idéntico a services.py → eliminado |
| 11 | `TestServiceFileCleanup` | `test_service_stub_eliminado` | service.py stub vacío → eliminado |
| 12 | `TestServiceFileCleanup` | `test_services_preservado_siempre` | services.py nunca se elimina |
| 13 | `TestServiceFileCleanup` | `test_sin_services_no_hace_nada` | Sin services.py → no elimina nada |
| 14 | `TestPytestFailureClassifier` | `test_clasifica_type_errors` | TypeError → category `type_errors` |
| 15 | `TestPytestFailureClassifier` | `test_clasifica_import_errors` | ImportError → category `import_errors` |
| 16 | `TestPytestFailureClassifier` | `test_clasifica_name_errors` | NameError → category `name_errors` |
| 17 | `TestPytestFailureClassifier` | `test_feedback_type_error_menciona_datetime` | Feedback de type_error incluye instrucción sobre datetime |
| 18 | `TestPytestFailureClassifier` | `test_feedback_import_error_menciona_naming` | Feedback de import_error menciona naming mismatch |

---

## 6. Roadmap post-S108

### S109 — Resiliencia nativa LangGraph (basado en ADR-004 + research)

**Motivación:** LangGraph 1.2 introduce `RetryPolicy` y `error_handler` por nodo. OVD usa `security_retry_count`/`qa_retry_count` en estado TypedDict — más frágil y contamina el checkpoint.

**Propuestas:**

- **S109-A:** Migrar `security_audit` a `RetryPolicy(retry_on=SecurityException, max_attempts=3)` en lugar de `security_retry_count` en estado.
- **S109-B:** `error_handler` post-retry para nodos críticos: cuando se agotan los reintentos de seguridad, rutear a `handle_escalation` vía `compensation_branch` en lugar de terminar con error.
- **S109-C:** Resolver LangGraph issue #6027 — `Pydantic ValidationError` no activa `RetryPolicy`. Envolver llamadas LLM en try/except para convertir `ValidationError` en excepciones capturables por `RetryPolicy`.

**Alineación con ADRs:** ADR-003 (LangGraph stays) — no hay conflicto, es mejora interna.

---

### S110 — Paralelismo real (ADR-004 Opción A, ya parcialmente implementada)

**Contexto:** ADR-004 identificó que el fan-out de 8 agentes con Ollama local serializa en GPU. Opción A (menos agentes) es la de mayor ROI.

**Estado actual:** el SDD ya filtra agentes por FR. `contratos-beneficios` seleccionó 2-3 agentes.

**Propuestas:**

- **S110-A:** Telemetría por nodo — registrar duración individual de cada `agent_executor` en `token_usage`. Prerequisito para ADR-004 decisiones basadas en datos.
- **S110-B:** Opción B (modelos mixtos) — validar con A/B test: `qwen3-coder:8b` para `devops` y `docs`, `qwen3-coder:30b` para `backend` y `database`. Requiere mínimo 3 ciclos por configuración.
- **S110-C:** Evaluar Opción C (multi-instancia Ollama en puertos distintos) si la Opción B no es suficiente.

**Alineación con ADRs:** ADR-004 Opción A/B — en análisis pendiente de datos.

---

### S111 — RAG ciclo-aware + lessons from failures (ADR-001 + S96-H)

**Contexto:** El RAG actual indexa código y docs, pero no tiene memoria de errores de ciclos pasados ni de fixes aplicados. Cada ciclo empieza desde cero — el LLM puede cometer el mismo error que ya fue corregido en S107/S108.

**Propuestas:**

- **S111-A:** Re-bootstrap RAG con código actual (S96-H1) — el RAG tiene foto congelada pre-S107.
- **S111-B:** Post-ciclo: indexar `lesson_backend` (código aprobado QA≥80) y `lesson_error` (error de pytest + fix aplicado) en pgvector. RAG context en agente backend incluirá "en ciclos anteriores este error se corrigió así".
- **S111-C:** `cycle_metrics` — JSON indexado por ciclo: qa_score, duración, stack, errores, fixes. Permite análisis longitudinal de mejora.
- **S111-D:** Índice de errores conocidos — cuando el clasificador (P4/S108-D) detecta un TypeError de Pydantic Date, buscar en RAG si hay una lesson sobre ese fix específico e inyectarla directamente.

**Alineación con ADRs:** ADR-001 (RAG en engine Python) — sin cambio arquitectural.

---

### S112+ — Roadmap de producto

| Sprint | Tema | ADR referencia |
|---|---|---|
| S112 | Dashboard ciclo history + exportación PDF de informes | — |
| S113 | MCP server para OVD como herramienta de Claude Code | ADR-001 |
| S114 | Soporte multi-stack real (Java/Spring, Go, Rust) | ADR-003 |
| S115 | Agente "investigador" con web research por FR complejo | ADR-003 Caso C |
| S116 | Multi-instancia Ollama si Opción B validada | ADR-004 Opción C |

---

## 7. Restricciones (ADRs activos)

Las siguientes restricciones permanecen vigentes durante S108 y los sprints del roadmap:

| ADR | Restricción |
|---|---|
| **ADR-002** | `ChatOllama(reasoning=False)` — no cambiar. Thinking mode produce 50k+ tokens sin output. |
| **ADR-003** | No migrar a AutoGen/CrewAI. LangGraph cubre todos los casos con menos complejidad. |
| **ADR-003** | No cargar 3+ modelos pinned simultáneamente en Apple Silicon (GPU serializa). |
| **ADR-003** | A/B test cuantitativo (≥3 ciclos) antes de cambiar modelo en producción. |
| **ADR-003** | Baseline a superar: QA 93/100, duración ≤13 min (ciclo S76). |
| **ADR-004** | Decisión parallelismo Opción B/C requiere telemetría por nodo primero (S110-A). |

---

## 8. Criterios de aceptación S108

El ciclo de validación S108 debe producir:

| Criterio | Valor objetivo | Método de verificación |
|---|---|---|
| QA score | ≥ 95/100 | SSE stream → mensaje `qa_review` |
| pytest | PASS (0 errores) | SSE stream → `test_results.passed = true` |
| S79-C falso positivo | Ausente | Logs engine: sin `[S79-C] ⚠️` cuando FR no usa Oracle |
| docker-compose | `postgres:16-alpine` | `grep image docker-compose.yml` |
| Naming consistency | `deactivate_contract` en router | `grep deactivate_contract src/contracts/router.py` |
| service.py residual | Ausente | `find . -name service.py` (solo services.py) |
| Retries tests | 0 | SSE: no `test_retry` events |
| test_s108.py | 18 tests PASS | `pytest tests/test_s108.py -v` |
| Regresiones | 0 | Suite completa: ≥1848 PASS |
