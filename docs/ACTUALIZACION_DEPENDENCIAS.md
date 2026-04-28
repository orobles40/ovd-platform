# Actualización de Dependencias — OVD Platform Engine

> Fecha: 2026-04-28 | Ejecutada en rama `dev`

---

## Resumen ejecutivo

Se realizó una investigación completa del estado de versiones del proyecto y se aplicaron las actualizaciones consideradas seguras (cambios patch y minor sin breaking changes confirmados). Las dependencias con saltos de versión major se congelaron hasta después de la presentación del 18 de mayo de 2026.

**Resultado:** 1507 tests PASS (antes: 1502). El fix del import `re` en `graph.py` recuperó 5 tests que fallaban por un bug latente del S94-fix.

---

## Actualizaciones aplicadas (2026-04-28)

| Paquete | De | A | Tipo |
|---------|-----|---|------|
| `langgraph` | 1.1.3 | 1.1.10 | patch |
| `fastapi` | 0.135.2 | 0.136.1 | minor |
| `uvicorn` | 0.42.0 | 0.46.0 | minor |
| `pydantic` | 2.12.5 | 2.13.3 | minor |
| `sse-starlette` | 3.3.3 | 3.4.1 | minor |
| `pydantic-settings` | 2.13.1 | 2.14.0 | minor |
| `python-multipart` | 0.0.26 | 0.0.27 | patch |

**Por qué son seguros:** todos son cambios patch o minor. Ninguno introduce cambios en la API pública que el proyecto utiliza. Los tests de regresión lo confirman.

**Fix colateral incluido:** `import re as _re_top` agregado al inicio de `graph.py` — el S94-fix usaba `re.search()` sin que el módulo estuviera importado en ese scope, causando `NameError` en 4 tests que se creía eran pre-existentes.

---

## Dependencias congeladas — pendiente después del 18/5

### `langchain-anthropic` 0.3.x → 1.0.0

**Por qué está congelado:** salto de versión **major** (0.3 → 1.0). El equipo de LangChain publicó v1.0 con cambios de API. En el proyecto se usa `ChatAnthropic` en múltiples nodos de `graph.py` (analyze_fr, generate_sdd, agent_executor, qa_review, security_audit). Actualizar sin testing exhaustivo puede romper el grafo completo.

**Cuándo abordar:** semana del 19 de mayo, después de la presentación al cliente.

**Cómo abordar:**
1. Crear rama `chore/langchain-v1-upgrade` desde `dev`
2. Ejecutar `uv add "langchain-anthropic>=1.0.0" --upgrade`
3. Revisar changelog oficial: https://github.com/langchain-ai/langchain/releases
4. Verificar si `ChatAnthropic()` cambió constructor o métodos `.invoke()` / `.astream()`
5. Correr suite completa: `uv run pytest tests/ -m "not integration and not docker" -q`
6. Lanzar ciclo de validación contratos-beneficios y verificar que el grafo completa

**Dependencias transitivas que se actualizan junto con este paquete:**
- `langchain-core` (~0.3.x → ~1.3.x)
- `langchain-openai` (versión transitiva)
- `langchain-ollama` (versión transitiva)
- `langchain-postgres` (0.0.17 — pre-release, evaluar si hay versión estable)

---

## Dependencias al día (no requieren acción)

| Paquete | Versión | Estado |
|---------|---------|--------|
| `psycopg[binary,pool]` | 3.3.3 | ✅ última versión |
| `alembic` | 1.18.4 | ✅ última versión |
| `python-jose[cryptography]` | 3.5.0 | ✅ última versión |
| `passlib[argon2,bcrypt]` | 1.7.4 | ✅ última versión |
| `httpx` | 0.28.1 | ✅ última versión |
| `tenacity` | 9.1.4 | ✅ última versión |
| `pytest` | 9.0.3 | ✅ última versión |
| `mcp` | 1.27.0 | ✅ última versión |

---

## Python — sin cambios

El proyecto usa **Python 3.12.12**, que es la versión LTS activa (EOL octubre 2027). El sistema tiene disponibles 3.12, 3.13 y 3.14.

**Por qué no se actualiza Python:** LangGraph y el ecosistema LangChain tienen mejor soporte probado en 3.12. Migrar a 3.13 o 3.14 antes de la presentación sería riesgo innecesario sin beneficio concreto.

**Cuándo abordar Python 3.13:** después de que `langchain-anthropic 1.0` esté integrado y estabilizado. Ambas actualizaciones juntas sería demasiado riesgo a la vez.

---

## Paquetes pendientes de verificación manual

Los siguientes paquetes no fueron verificados contra PyPI durante la investigación. Verificar antes de la sesión de actualización post-presentación:

| Paquete | Versión instalada | Acción |
|---------|------------------|--------|
| `nats-py` | 2.6.0 | Verificar si hay versión más reciente |
| `langchain-postgres` | 0.0.17 | Pre-release — evaluar si hay versión estable |
| `duckduckgo-search` | 8.1.1 | Verificar |
| `infisical-python` | 2.3.6 | Verificar |
| `slowapi` | 0.1.9 | Mantenimiento lento — verificar actividad del repo |

---

## Cómo aplicar actualizaciones futuras

```bash
# 1. Ver qué tiene actualizaciones disponibles
cd src/engine && uv lock --upgrade-package <nombre>

# 2. Aplicar actualizaciones patch/minor (seguras)
uv add "<paquete>>=X.Y" --upgrade

# 3. Sincronizar entorno
uv sync

# 4. Correr tests de regresión
uv run pytest tests/ -m "not integration and not e2e and not docker" -q

# 5. Commit solo si tests PASS
git add uv.lock pyproject.toml
git commit -m "chore(deps): actualizar <paquetes>"
```

**Regla general:** nunca actualizar major versions sin rama separada y testing exhaustivo. Para minor/patch, verificar el resultado de la suite antes de hacer commit.
