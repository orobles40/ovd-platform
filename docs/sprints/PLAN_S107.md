# Plan S107 — OVD Platform

**Fecha:** 2026-05-04  
**Autor:** Omar Robles  
**Contexto:** Post-análisis S106 (QA 62) + investigación en profundidad de literatura académica, repos de referencia y stack OVD

---

## Resumen ejecutivo

S106 subió QA de 40 → 62 (+22 pts) pero sigue 18 puntos debajo del target (≥80). La raíz está en **dos problemas distintos** que se suman:

1. **Divergencia de nombres entre agentes** (GAP-S106-1): el mismo agente backend genera `deactivate_contrato` en services.py y `delete_contrato` en router.py. Causa: el tipo contrato compartido es *consultivo*, no *vinculante*, y el agente reinterpreta los nombres según el contexto de cada task.

2. **Oracle en docker-compose desde datos de entrenamiento** (GAP-S106-2): el postprocesador de S106-P3 filtró el RAG correctamente, pero el vector de contaminación es el modelo qwen3-coder:30b entrenado con miles de docker-compose que usan Oracle XE.

La investigación profunda en MetaGPT, SEMAP, LangGraph, Anthropic guidelines y repos de referencia converge en un patrón: **el contrato de interfaces debe resolverse en un nodo dedicado, antes de la generación**, no como hint inyectado en los prompts.

---

## Análisis de causa raíz (consolidado)

### Problema 1 — Divergencia de nombres

```
services.py:  deactivate_contrato, get_contratos, calcular_total_contrato  ← SDD + español
router.py:    delete_contrato,     list_contratos, get_contract_total       ← REST + inglés
tests:        delete_contrato,     list_contratos                           ← copia router
```

**Causa estructural:**
- El agente aplica convenciones distintas según el contexto de la task: español para la capa de negocio, inglés para HTTP/REST, copia el router para los tests.
- El type contract (S103-P1) se inyecta como texto en el prompt, pero el modelo lo ignora al generar cada archivo en contexto diferente.
- El fan-out paralelo hace que router.py y tests se escriban sin ver el código real de services.py.

**Por qué los fixes anteriores no lo resolvieron:**
- S103-P1 (type contract): consultivo, no vinculante → agente lo sobreescribe
- S106-P6 (list_entities): hint correcto pero ignorado al escribir services.py
- S103-P2 (_check_undefined_import_names): detecta el problema DESPUÉS de generado → útil como penalidad QA, no como prevención

### Problema 2 — Oracle en docker-compose

**Causa:** El vector de contaminación no es el RAG (S106-P3 lo resolvió), sino el **conocimiento de entrenamiento** del modelo. qwen3-coder:30b fue entrenado con patrones docker-compose que usan `gvenzl/oracle-xe` como imagen de BD empresarial por defecto.

**Por qué los fixes anteriores no lo resolvieron:**
- S106-P3 filtró el RAG context — correcto, pero Oracle no venía del RAG
- No hay instrucción explícita en el prompt del agente devops que prohíba Oracle
- No hay postprocesador de docker-compose.yml que intercepte la imagen Oracle antes de escribir el archivo

---

## Investigación de referencia

### MetaGPT — SOP pattern (hallazgo más relevante)

MetaGPT define un flujo donde el **Architect** genera interfaces completas (nombres de funciones, tipos, contratos) **antes** de que los Engineers escriban código. Los Engineers no pueden cambiar los contratos: son vinculantes.

> "The architect role generates the system design including exact function signatures that all downstream roles must adhere to." — MetaGPT SOP

Aplicado a OVD: existe un nodo entre `generate_sdd` y `execute_agents` que usa LLM con structured output (Pydantic) para generar el contrato canónico de nombres. Todos los agentes reciben este contrato como parte obligatoria de su context, no como hint.

### Anthropic — Building effective agents (hallazgos relevantes)

- **Orchestrator-subagent pattern**: el orchestrator debe especificar *qué* hacer, no *cómo*. Para OVD: el orchestrator debe especificar los nombres de función exactos.
- **Verification between steps**: Anthropic recomienda verificación determinística entre pasos del pipeline antes de continuar al siguiente. Para OVD: verificar que services.py tiene las funciones canónicas antes de invocar el agente de router.
- **Clear handoff contracts**: "When passing work between agents, the contract must be explicit and verifiable."

### LangGraph — Features subutilizadas en OVD

- **`defer=True` en Send()**: barrera de sincronización entre nodos paralelos — permite que el nodo de router espere a que backend termine antes de ejecutar.
- **Structured output via `with_structured_output()`**: cualquier nodo puede generar salida tipada con Pydantic, no solo texto libre. Ideal para un nodo Architecture Gate.
- **`interrupt_before`**: permite insertar un nodo de validación antes de continuar el grafo.

### SEMAP Agent Cards

SEMAP define Agent Cards (descriptores JSON de inputs/outputs de cada agente) con verificación de compatibilidad antes de la ejecución. El paper reporta **69.6% de reducción de fallos** en pipelines multi-agente con contratos explícitos.

Aplicación directa: cada agente OVD tiene un "output contract" verificado por un nodo Contract Validator antes de pasar a QA.

### Repositorios de referencia

| Repo | Hallazgo relevante para OVD |
|------|---------------------------|
| MetaGPT | Architect define firmas exactas antes de Engineer — el patrón más cercano al fix |
| OpenHands | Sandbox Docker para verificación antes de pytest — patrón de verificación aislada |
| aider | Tree-sitter AST para verificar que el código generado cumple las firmas esperadas |
| CrewAI | Tasks con expected_output → verifica que el agente entrega lo prometido |
| Superpowers | Skills explícitos con output verificado — referencia de OVD ya implementada |

---

## Restricciones de los ADRs

### ADR-003 (modelos LLM)
- **Mantener LangGraph** — migrar a Autogen/CrewAI es regresión de 6+ meses. No aplica.
- **qwen3-coder:30b Q4_K_M** como default — validado QA 93. No cambiar sin A/B test de 3 ciclos.
- Ninguna propuesta S107 requiere cambio de modelo o stack.

### ADR-004 (paralelismo)
- **Opción A recomendada**: reducir agentes seleccionados. Los 3 agentes de S106 (backend+devops+frontend) aumentaron tokens +136% sin mejora proporcional de QA.
- El fan-out paralelo (backend → router.py || tests) es la causa estructural del problema 1. S107-P3 (Fix B) aborda esto con un postprocesador sincrónico.
- No se agregan modelos adicionales — Apple Silicon serializa GPU (ADR-004).

**Implicación:** el Architecture Gate (S107-P1-nueva) corre en el mismo modelo qwen3-coder:30b, como un nodo adicional en el grafo, no como modelo paralelo.

---

## Propuestas S107 — Plan de implementación

### S107-P1 (CRÍTICO) — Architecture Gate: nodo de contrato canónico

**Problema que resuelve:** GAP-S106-1 (naming divergence), GAP-S106-3 (type contract consultivo)

**Qué es:** Un nodo LangGraph nuevo, `generate_architecture_contract`, que corre después de `generate_sdd` y antes de `execute_agents`. Usa el LLM con `with_structured_output(ArchitectureContract)` para generar todas las firmas canónicas.

**Diseño:**

```python
class FunctionSignature(BaseModel):
    name: str                    # nombre exacto: create_contrato, deactivate_contrato
    module: str                  # services.py, router.py, etc.
    params: list[str]            # ["data: ContratoCreate", "db: Session"]
    return_type: str             # "ContratoResponse"

class ArchitectureContract(BaseModel):
    entity: str                  # "contrato"
    service_functions: list[FunctionSignature]   # definidas en services.py
    router_endpoints: list[str]  # GET /contratos/{id}, POST /contratos
    pydantic_schemas: list[str]  # ContratoCreate, ContratoUpdate, ContratoResponse

class FullArchitectureContract(BaseModel):
    contracts: list[ArchitectureContract]
    naming_convention: str       # "español"
```

**Prompt del Architecture Gate:**
```
REGLA ABSOLUTA: Las funciones de services.py y las importaciones en router.py y tests
DEBEN usar EXACTAMENTE los mismos nombres. Define AHORA los nombres canónicos.

Del SDD siguiente, extrae todas las entidades y define:
1. service_functions: funciones en services.py (español, verbo_entidad)
2. router_imports: los mismos nombres, importados desde services.py
3. test_imports: los mismos nombres, usados en tests

NO uses inglés para los nombres de función. Usa el mismo nombre en los 3 archivos.

SDD: {sdd}
```

**Inyección en agentes:** La `FullArchitectureContract` (serializada como JSON) se inyecta al inicio del HumanMessage de CADA agente como bloque `[ARCHITECTURE CONTRACT — VINCULANTE]`:

```
[ARCHITECTURE CONTRACT — VINCULANTE]
Las siguientes firmas son el ÚNICO contrato válido. NO puedes cambiarlos.

services.py DEBE definir:
- def create_contrato(data: ContratoCreate, db: Session) -> ContratoResponse
- def get_contrato(contrato_id: int, db: Session) -> ContratoResponse
- def update_contrato(contrato_id: int, data: ContratoUpdate, db: Session) -> ContratoResponse
- def deactivate_contrato(contrato_id: int, db: Session) -> None
- def list_contratos(db: Session) -> list[ContratoResponse]

router.py DEBE importar EXACTAMENTE: create_contrato, get_contrato, update_contrato, deactivate_contrato, list_contratos
tests DEBE importar EXACTAMENTE: create_contrato, get_contrato, update_contrato, deactivate_contrato, list_contratos
```

**Diferencia con type contract actual (S103-P1):**
- Tipo actual: texto libre, inyectado como hint → ignorado cuando el agente "sabe mejor"
- Architecture Gate: generado por LLM con structured output → JSON tipado → imposible de ignorar (es JSON, no texto)
- La serialización JSON hace que el agente lo trate como datos, no como sugerencia

**Estimación:** 2-3 días  
**Impacto esperado:** -80% naming mismatches → QA +15-20 pts  
**Archivos:** `graph.py` (nuevo nodo + integración), `state.py` (campo `architecture_contract`)

---

### S107-P2 (CRÍTICO) — Postprocesador Oracle→PostgreSQL en docker-compose

**Problema que resuelve:** GAP-S106-2 (Oracle en docker-compose desde training data)

**Dos acciones complementarias:**

**P2-A — Instrucción explícita en system_devops.md:**
```markdown
## RESTRICCIÓN ABSOLUTA — Base de datos en docker-compose (S107-P2)

Si el Feature Request menciona PostgreSQL (o no menciona Oracle explícitamente):
- IMAGEN OBLIGATORIA: `postgres:16-alpine`
- VARIABLES: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- ❌ PROHIBIDO: `gvenzl/oracle-xe`, `oracle/database`, `oracleinanutshell/oracle-xe-11g`
- ❌ PROHIBIDO: cualquier imagen que contenga "oracle" en el nombre
- Si hay duda sobre la BD: usar PostgreSQL por defecto

Ejemplo correcto:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-myapp}
      POSTGRES_USER: ${POSTGRES_USER:-myuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
```

**P2-B — Postprocesador `_fix_oracle_in_docker_compose()` en code_postprocessor.py:**
```python
_ORACLE_DOCKER_IMAGES = re.compile(
    r'image:\s*(gvenzl/oracle-xe|oracle/database|oracleinanutshell/oracle-xe[^\s]*)',
    re.IGNORECASE
)

def _fix_oracle_in_docker_compose(content: str, oracle_involved: bool) -> str:
    """S107-P2: reemplaza imágenes Oracle por postgres:16-alpine cuando oracle_involved=False."""
    if oracle_involved:
        return content  # Oracle es legítimo — no tocar
    return _ORACLE_DOCKER_IMAGES.sub('image: postgres:16-alpine', content)
```

Integrado en `process_file()` para archivos `docker-compose*.yml`.

**Estimación:** 1 día  
**Impacto esperado:** docker-compose PostgreSQL en 100% de ciclos no-Oracle

---

### S107-P3 (CRÍTICO) — `_sync_service_imports()`: sincronizador post-fan-out

**Problema que resuelve:** GAP-S106-4 (sin verificación de imports antes de escribir router/tests)

**Lógica:** Después de que todos los agentes terminan (post-fan-out), antes de `run_tests`:
1. Leer services.py con AST → extraer funciones definidas
2. Leer router.py → encontrar imports de services
3. Por cada import no definido, buscar alias obvio (reglas de mapeo)
4. Reescribir router.py y tests con los nombres correctos

**Implementación:**

```python
def _sync_service_imports(work_dir: str) -> list[str]:
    """
    S107-P3: después del fan-out, sincroniza imports de router/tests con services.py real.
    Retorna lista de correcciones aplicadas.
    """
    fixes = []
    
    # 1. Extraer funciones definidas en services.py
    service_fns = _extract_defined_functions(work_dir, "src/contracts/service.py")
    service_fns |= _extract_defined_functions(work_dir, "src/contracts/services.py")
    
    if not service_fns:
        return fixes
    
    # 2. Reglas de mapeo por patrón (alias obvioss)
    alias_map = _build_alias_map(service_fns)
    # Ej: si service tiene deactivate_X, router importa delete_X → corregir
    # Reglas: delete_ → deactivate_, list_ → get_s, get_all_ → get_s
    
    # 3. Aplicar correcciones en router.py y tests/
    for filepath in _find_python_files(work_dir, ["router.py", "test_*.py"]):
        content = read_file(filepath)
        new_content, applied = _apply_import_corrections(content, alias_map)
        if applied:
            write_file(filepath, new_content)
            fixes.extend(applied)
    
    return fixes

def _build_alias_map(defined_fns: set[str]) -> dict[str, str]:
    """Genera mapeo alias → nombre_real basado en patrones comunes."""
    alias_map = {}
    for fn in defined_fns:
        # deactivate_X → delete_X, disable_X
        if fn.startswith("deactivate_"):
            entity = fn[len("deactivate_"):]
            alias_map[f"delete_{entity}"] = fn
            alias_map[f"disable_{entity}"] = fn
            alias_map[f"remove_{entity}"] = fn
        # get_Xs (plural) → list_Xs
        if fn.startswith("get_") and fn.endswith("s"):
            alias_map[fn.replace("get_", "list_", 1)] = fn
        # calcular_X_total → get_X_total, calculate_X_total
        if fn.startswith("calcular_"):
            rest = fn[len("calcular_"):]
            alias_map[f"get_{rest}"] = fn
            alias_map[f"calculate_{rest}"] = fn
    return alias_map
```

**Estimación:** 2 días  
**Impacto esperado:** 0 ImportError por naming entre service/router/tests en ciclos post-S107

---

### S107-P4 (ALTA) — Instrucción de naming en system_backend_python.md

**Problema que resuelve:** GAP-S106-1 (convenciones distintas por contexto)

Agregar tabla canónica de naming en el template del agente backend:

```markdown
## REGLA DE NAMING — ESPAÑOL CONSISTENTE (S107-P4)

Usa español para TODOS los nombres de función en el backend. Esta regla aplica
a services.py, router.py Y tests. El router importa de services — usa los MISMOS nombres.

| Operación | Nombre correcto | ❌ Prohibido |
|-----------|-----------------|-------------|
| Crear X | create_X | createX, add_X |
| Obtener X | get_X | getX, fetch_X, find_X |
| Listar Xs | get_Xs o list_Xs | listX, get_all_X |
| Actualizar X | update_X | updateX, edit_X |
| Eliminar X | deactivate_X (si es soft delete) o delete_X | remove_X, deleteX |
| Total de X | calcular_total_X o get_total_X | getTotal, calculateTotal |

CRÍTICO: Si services.py define `deactivate_contrato`, router.py IMPORTA `deactivate_contrato`.
NO cambies el nombre al importar. Usa `from src.contracts.service import deactivate_contrato`.
```

**Estimación:** 0.5 días (cambio de template)  
**Impacto esperado:** reducción de divergencia en primer intento

---

### S107-P5 (ALTA) — QA verifica type contract vs implementación

**Problema que resuelve:** GAP-S106-5 (QA review no verifica el contrato)

Extender `qa_review` para, antes de llamar al LLM, hacer verificación AST:

```python
def _verify_contract_vs_implementation(work_dir: str, architecture_contract: dict) -> list[str]:
    """
    S107-P5: verifica que las funciones del architecture contract existen en los archivos generados.
    Retorna lista de funciones faltantes (para penalizar en QA).
    """
    missing = []
    for contract in architecture_contract.get("contracts", []):
        for sig in contract.get("service_functions", []):
            fn_name = sig["name"]
            module = sig["module"]  # "services.py"
            
            # Buscar el archivo en work_dir
            candidates = _find_file(work_dir, module)
            if not candidates:
                missing.append(f"{fn_name} ({module} no existe)")
                continue
            
            defined_fns = _extract_defined_functions(work_dir, candidates[0])
            if fn_name not in defined_fns:
                missing.append(f"{fn_name} ({module})")
    
    return missing
```

La lista `missing` se agrega como sección al prompt del QA reviewer y aplica -5 pts por función faltante (máx -30).

**Estimación:** 1.5 días  
**Impacto esperado:** QA penaliza contratos no cumplidos → presión en retries → convergencia

---

### S107-P6 (MEDIA) — Template devops con PostgreSQL explícito

Ya incluido en S107-P2-A. No requiere trabajo adicional.

---

## Orden de implementación recomendado

```
Día 1:   S107-P2 (postprocessor docker-compose + template devops)
         → Fix rápido, impacto inmediato, 0 riesgo de regresión

Día 2:   S107-P4 (naming en system_backend_python.md)
         → Cambio de template, 0.5 días, mejora comportamiento del agente

Día 3-4: S107-P1 (Architecture Gate)
         → El cambio más impactante, requiere:
           a) ArchitectureContract Pydantic model
           b) Nuevo nodo LangGraph generate_architecture_contract
           c) Integración del contrato en execute_agents
           d) Tests test_s107_p1.py

Día 5:   S107-P3 (_sync_service_imports postprocessor)
         → Safety net después del Architecture Gate

Día 6:   S107-P5 (QA contract verification)
         → Cierra el loop: QA penaliza si el Architecture Gate fue ignorado
```

**Criterio de éxito S107:** ciclo de validación con QA ≥ 80, 0 ImportError por naming, docker-compose con postgres:16

---

## Relación con ADR-003 y ADR-004

### ADR-003 — Modelos LLM

| Propuesta | Impacto en modelos | ¿Requiere cambio? |
|-----------|--------------------|--------------------|
| S107-P1 (Architecture Gate) | Nuevo nodo, mismo modelo (qwen3-coder:30b) | No — 1 línea en .env si se quisiera un modelo menor |
| S107-P2 (docker-compose) | Postprocesador, sin LLM | No |
| S107-P3 (_sync_service_imports) | Determinístico, sin LLM | No |
| S107-P4 (template) | Solo prompt engineering | No |
| S107-P5 (QA contract) | Inyección AST en QA prompt | No |

**Conclusión:** Ninguna propuesta S107 requiere cambio de modelo o stack. ADR-003 no aplica restricciones adicionales.

### ADR-004 — Paralelismo

El Architecture Gate agrega un nodo serial entre `generate_sdd` y `execute_agents`. El tiempo adicional estimado es 45-90 segundos (una inferencia del modelo). El fan-out paralelo se mantiene porque el problema no es el paralelismo en sí, sino la ausencia de un contrato vinculante compartido.

El postprocesador `_sync_service_imports` corre después del fan-out (determinístico, sin LLM, <1 segundo) — no impacta el tiempo total.

**Opción A de ADR-004 (reducir agentes)**: S106 mostró que 3 agentes generaron +136% tokens sin +136% QA. Revisar si el agente frontend es necesario en FR puramente backend. Esto es candidato a S108, no S107.

---

## Roadmap S107–S110 (revisado)

### S107 — Contrato vinculante + Oracle fix (este sprint)
- P1: Architecture Gate (nodo pre-agentes con structured output)
- P2: Postprocesador Oracle→PostgreSQL + template devops
- P3: _sync_service_imports (safety net post-fan-out)
- P4: Tabla de naming en system_backend_python.md
- P5: QA verifica architecture contract vs implementación
- **Target:** QA ≥ 80, 0 naming mismatches, docker-compose PostgreSQL

### S108 — Optimización de agentes (ADR-004 Opción A)
- Filtrado más agresivo en `_select_agents()`: frontend solo cuando FR pide UI explícitamente
- Telemetría por agente: duración individual, tokens por agente
- Evaluación de modelos 8B para devops/docs (ADR-004 Opción B, requiere A/B test)
- **Target:** ciclo completo ≤ 20 min, agentes promedio = 2 para FR backend puras

### S109 — Hardening del contrato
- Architecture Gate como "hard stop": si el agente genera código que no cumple el contrato → retry automático antes de continuar
- Contract Validator Node: nodo dedicado que corre AST sobre todo el código generado antes de pytest
- RAG actualizado: re-indexación incremental en session-close (S96-H pendiente)

### S110 — Plan-then-implement
- Investigación: ¿vale la pena un paso de "plan de firmas" donde el agente lista todas las firmas que va a crear antes de implementar? (S106 roadmap largo plazo)
- ADR-004 Opción C (multi-instancia Ollama): evaluar con datos de telemetría de S108

---

## Métricas objetivo S107

| Métrica | S106 actual | Target S107 |
|---------|-------------|-------------|
| QA Score | 62 | ≥ 80 |
| Naming mismatches | 4 (2 funciones × 2 archivos) | 0 |
| docker-compose imagen | oracle-xe | postgres:16-alpine |
| Retries | 2 | 0-1 |
| Duración | 28m 36s | ≤ 25 min |
| Agentes | 3 | 2-3 |

---

## Argumentación final

### ¿Por qué el Architecture Gate funciona donde el type contract no?

El type contract actual (S103-P1) es texto libre inyectado en el prompt: `"Se espera que services.py defina: create_contrato(...)`. El modelo LLM, al generar router.py en un contexto diferente (HTTP endpoints, REST conventions), reinterpreta ese texto y usa su propio criterio de naming.

El Architecture Gate cambia la naturaleza del contrato: usa `with_structured_output(ArchitectureContract)` para generar un JSON tipado. Cuando ese JSON se inyecta en el prompt del agente como `[ARCHITECTURE CONTRACT — VINCULANTE]`, el modelo lo procesa como **datos estructurados**, no como texto de instrucción. La diferencia psicológica para el LLM es significativa: el texto libre se interpreta, el JSON se usa.

Adicionalmente, el JSON contiene los nombres en forma de lista exacta — sin ambigüedad posible entre `deactivate_contrato` y `delete_contrato`.

### ¿Por qué `_sync_service_imports` como safety net?

El Architecture Gate reduce los mismatches, pero no los elimina al 100% en el primer ciclo. El agente puede ignorar el contrato bajo presión de otras restricciones del contexto. El postprocesador determinístico cierra el gap residual: no depende del LLM, usa AST de Python, opera sobre el código ya escrito.

### ¿Por qué este orden (P2 → P4 → P1 → P3 → P5)?

P2 y P4 son cambios de 1 día sin riesgo. Dan mejora inmediata aunque falle P1. P1 es el cambio central de alto impacto. P3 es el safety net de P1. P5 cierra el loop con QA. Si solo se implementan P2+P4+P3, el QA ya debería mejorar ~10 pts. Con P1+P5, el target ≥80 es alcanzable.

---

*Plan generado en sesión S011 (2026-05-04). Para iteración: editar este archivo y comentar las propuestas.*
