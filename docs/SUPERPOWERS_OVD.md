# Superpowers — Guía de Referencia para OVD

> **Repo:** https://github.com/obra/superpowers  
> **Versión actual:** v5.0.7 (Marzo 2026)  
> **Proyecto:** OVD — Oficina Virtual de Desarrollo (LangGraph + FastAPI + pgvector + Oracle 19c)  
> **Estado actual:** 15 fases completadas, WF4 con 38 nodos en desarrollo  
> **Fecha:** Abril 2026

---

## Contexto importante

OVD es un sistema multi-agente que **implementa una filosofía similar a Superpowers**, pero con agentes LangGraph persistentes y contexto de negocio de Codigonet embebido. Esto crea dos niveles de uso:

| Nivel | Descripción |
|-------|-------------|
| **Ahora** | Usar Superpowers *para construir* OVD — aplica sobre código nuevo sin tocar lo existente |
| **Cuando OVD esté completo** | OVD reemplaza a Superpowers en proyectos Codigonet — Superpowers queda para proyectos externos |

---

## Incorporación a proyecto existente

Superpowers **no toca el código ya desarrollado**. Opera sobre lo que vas a hacer a continuación. Las 15 fases completadas y los nodos de WF4 ya construidos quedan intactos.

### Bloque de contexto de inicio de sesión

Usar este bloque al iniciar cada sesión de Claude Code en el repo de OVD para evitar que Superpowers haga brainstorming desde cero:

```
Context: I'm continuing development of OVD (Oficina Virtual de Desarrollo).
- Stack: LangGraph + FastAPI + pgvector + Ollama (embeddings) + Multi-LLM router (Claude/OpenAI/Ollama) + Oracle 19c (vía MCP server)
- Architecture: Multi-agent LangGraph system with RAG pipeline
- Integration: soporte-automatizado pipeline (Gmail → Ollama → Oracle → RAG → response)
- Status: 15 phases complete, WF4 has 38 nodes, currently working on [FASE ACTUAL]
- Existing code: do not redesign or refactor already completed phases
- Next task: [DESCRIBIR TAREA CONCRETA]

Skip brainstorming for completed phases. Jump directly to writing-plans
or subagent-driven-development for the next task.
```

### Manejo del código legacy sin tests

Si los nodos existentes no tienen cobertura de tests, agregar esta instrucción para evitar fricción:

```
Apply TDD strictly for new nodes only.
Existing WF4 nodes do not require retroactive test coverage in this session.
New nodes must follow RED-GREEN-REFACTOR from the start.
```

---

## Skills aplicadas a OVD

### 🧠 brainstorming

**Cuándo usarla en OVD:**
- Diseñar un agente nuevo antes de implementarlo
- Definir el contrato de inputs/outputs de un nodo complejo
- Resolver decisiones de arquitectura entre fases

**Prompt de ejemplo:**
```
brainstorm the design of the [nombre agente] agent for OVD:
- Role in the multi-agent graph
- Inputs and outputs schema
- Integration points: pgvector / Oracle 19c / Ollama
- State management within LangGraph
- Edge cases and failure modes
```

---

### 📋 writing-plans

**Cuándo usarla en OVD:**
- Al retomar el desarrollo después de una pausa
- Antes de implementar una fase nueva
- Para desglosar un nodo complejo en tareas atómicas

**Prompt de ejemplo para WF4:**
```
Write an implementation plan for the remaining nodes of WF4.
For each task include:
- Node name and purpose
- Inputs/outputs schema (TypedDict)
- LangGraph integration point (which edge connects to it)
- pgvector/Oracle integration if applicable
- Verification test (what must pass before moving on)
- Estimated complexity: low/medium/high
```

**Qué esperar:** tareas de 2–5 minutos cada una, con suficiente detalle para retomar en cualquier sesión sin perder contexto.

---

### 🧪 test-driven-development

**Cuándo usarla en OVD:** al implementar nodos nuevos desde el punto de incorporación de Superpowers en adelante.

**Estructura de tests sugerida para OVD:**
```
tests/
├── unit/
│   ├── nodes/              ← test por nodo LangGraph
│   │   ├── test_node_intake.py
│   │   ├── test_node_rag.py
│   │   └── test_node_oracle_query.py
│   ├── agents/             ← test por agente
│   └── utils/
├── integration/
│   ├── test_pgvector.py    ← búsqueda semántica + RRF
│   ├── test_oracle.py      ← queries a Oracle 19c
│   └── test_ollama.py      ← respuestas del modelo local
└── e2e/
    └── test_workflow.py    ← flujo completo de un ticket
```

**Ciclo para cada nodo nuevo:**
```python
# 1. RED — escribir el test primero
def test_node_rag_returns_relevant_chunks():
    state = {"query": "error ORA-01722", "chunks": []}
    result = node_rag(state)
    assert len(result["chunks"]) > 0
    assert result["chunks"][0]["score"] > 0.7

# 2. Ver que falla → confirmar RED
# 3. Implementar el mínimo código para que pase → GREEN
# 4. Ver que pasa → confirmar GREEN
# 5. Commit
# 6. Refactor si es necesario
```

---

### 🔍 systematic-debugging

**Cuándo usarla en OVD:** especialmente útil para bugs silenciosos en LangGraph (nodos que no fallan pero retornan estado incorrecto).

**Las 4 fases aplicadas a OVD:**

```
Fase 1 — Reproducir de forma confiable
  → Identificar el input exacto que causa el problema
  → Aislar el nodo o edge específico en el grafo

Fase 2 — Aislar la causa raíz
  → ¿Es el nodo? ¿La edge condition? ¿El estado compartido?
  → Agregar logging temporal en el estado de LangGraph
  → Verificar si el problema es en pgvector, Oracle o Ollama

Fase 3 — Defensa en profundidad
  → ¿Qué otros nodos podrían tener el mismo problema?
  → Agregar validación de estado en los nodos críticos

Fase 4 — Verificar que el fix resolvió el problema
  → Test que reproduce el bug original debe pasar
  → No asumir que funciona sin evidencia concreta
```

**Prompt de ejemplo:**
```
systematic-debug this issue in OVD:
- Symptom: [describir comportamiento incorrecto]
- Node suspected: [nombre del nodo]
- LangGraph state at entry: [mostrar estado]
- Expected output: [qué debería retornar]
- Actual output: [qué retorna]
```

---

### 🤖 subagent-driven-development

**Cuándo usarla en OVD:** para implementar nodos independientes del grafo en paralelo.

**Nodos que pueden desarrollarse en paralelo en WF4:**
```
# Independientes entre sí → candidatos para subagentes paralelos
- node_intake          (recepción y clasificación)
- node_enrichment      (enriquecimiento de contexto)
- node_formatter       (formateo de respuesta)
- node_audit_logger    (registro de auditoría)
```

**⚠️ Importante:** los nodos que comparten estado de LangGraph o tienen dependencias de edge NO deben desarrollarse en paralelo — primero el nodo upstream, luego el downstream.

---

### 🌿 using-git-worktrees

**Cuándo usarla en OVD:** para trabajar en fases o nodos grandes sin afectar el grafo estable.

**Estrategia de branches para OVD:**
```bash
# Branch por fase
git worktree add ../ovd-phase-16 feature/phase-16-[nombre]

# Branch para experimentos de arquitectura
git worktree add ../ovd-experiment feature/experiment-[concepto]

# main siempre debe tener el grafo en estado funcional
```

---

### ✅ verification-before-completion

**Cuándo usarla en OVD:** antes de declarar que un nodo o fase está lista.

**Checklist de verificación para nodos OVD:**
```
□ Test unitario del nodo pasa
□ Test de integración con dependencias externas pasa
   (pgvector / Oracle / Ollama según corresponda)
□ El nodo maneja correctamente el estado LangGraph
   (no muta estado que no le corresponde)
□ Edge conditions cubiertas (¿qué pasa si el nodo retorna vacío?)
□ Logging adecuado para debugging en producción
□ El grafo completo pasa el test e2e con este nodo incluido
```

---

### 🏁 finishing-a-development-branch

**Cuándo usarla en OVD:** al completar una fase o un conjunto de nodos.

**Opciones al finalizar una rama de OVD:**
- **Merge a main** si la fase está completamente testeada
- **PR** si quieres revisión antes de integrar
- **Keep** si la fase está funcional pero incompleta
- **Discard** si el experimento no funcionó (git worktree remove)

---

## Roadmap de aplicación por fase

### Fases pendientes de WF4 (desde punto de incorporación)

```
Para cada nodo nuevo:
1. brainstorming     → definir contrato del nodo
2. writing-plans     → desglosar en tareas atómicas
3. using-git-worktrees → branch aislado
4. test-driven-dev   → RED-GREEN-REFACTOR por tarea
5. verification      → checklist antes de mergear
6. finishing-branch  → merge a main cuando fase completa
```

### Para fases post-WF4

```
Aplicar el flujo completo desde el inicio:
brainstorming → git-worktrees → writing-plans →
subagent-driven-dev → test-driven-dev → code-review →
verification → finishing-branch
```

---

## Relación OVD ↔ Superpowers a futuro

```
Hoy
└── Superpowers guía el desarrollo de OVD
    Claude Code + skills Superpowers = metodología de construcción

Cuando OVD esté operativo
└── OVD reemplaza a Superpowers en proyectos Codigonet
    │
    ├── OVD maneja: agentes persistentes, contexto Codigonet/Alemana,
    │              integración Oracle/pgvector/RAG, memoria entre sesiones
    │
    └── Superpowers sigue siendo útil para:
        AdminCore, proyectos personales, proyectos externos
        donde OVD no está disponible
```

| Aspecto | Superpowers | OVD (completo) |
|---------|-------------|----------------|
| Agentes | Subagentes Claude Code | Agentes LangGraph propios |
| Persistencia | Por sesión | Permanente (pgvector) |
| Contexto | Genérico | Codigonet / Clínica Alemana |
| Customización | Skills Markdown | Nodos Python full-code |
| Integración | Claude Code only | FastAPI + Oracle + RAG + soporte |

---

## Referencias

- Repo Superpowers: https://github.com/obra/superpowers
- Marketplace oficial: https://claude.com/plugins/superpowers
- Blog del autor: https://blog.fsck.com/2025/10/09/superpowers-for-claude-code/
- Discord comunidad: https://discord.gg/Jd8Vphy9jq
