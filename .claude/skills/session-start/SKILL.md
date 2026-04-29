---
name: session-start
description: >
  Carga el contexto completo del sprint activo y propone la primera tarea.
  Lee CURRENT.md, CONTEXT.md, verifica infra Docker y branch de trabajo.
  Invocar al inicio de cada sesión de desarrollo de OVD Platform.
argument-hint: "[tarea-específica-opcional]"
allowed-tools: Read Bash(docker *) Bash(git *) Bash(grep *)
disable-model-invocation: false
---

# Inicio de sesión OVD Platform

Al invocar este skill, ejecuta los siguientes pasos en orden:

## 1. Leer contexto del sprint

Lee los siguientes archivos:
- `docs/sprints/CURRENT.md` — sprint activo, tareas, métricas objetivo
- `.claude/CONTEXT.md` — estado dinámico: fallos conocidos, issues abiertos, último avance

Extrae y muestra:
- Sprint activo (número y nombre)
- Tareas pendientes (con prioridad)
- Fallos pre-existentes vigentes
- Issues abiertos críticos

## 2. Verificar infraestructura

Ejecuta:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "postgres_db|nats|infisical"
```

Reporta:
- `postgres_db` — UP o DOWN (crítico — sin esto el engine no arranca)
- `nats` — UP o DOWN (warning — ciclos siguen sin NATS)
- Si alguno está DOWN: mostrar el comando para levantarlo

Comando de recuperación si postgres_db está DOWN:
```bash
docker start postgres_db
```

## 3. Verificar rama de trabajo

```bash
git branch --show-current && git status --short
```

- Si la rama no es `dev` ni `feature/S*` → advertir
- Si hay cambios sin commit del día anterior → mostrarlos como contexto

## 4. Verificar engine

```bash
curl -s --max-time 3 http://localhost:8001/health 2>/dev/null && echo "ENGINE UP" || echo "ENGINE DOWN"
```

Si está DOWN: mostrar comando de inicio:
```bash
cd src/engine && .venv/bin/uvicorn api:app --port 8001
```

## 5. Proponer primera tarea

Con base en CURRENT.md y el argumento `$ARGUMENTS` (si se proporcionó):

- Si `$ARGUMENTS` está vacío → proponer la primera tarea pendiente con mayor prioridad
- Si `$ARGUMENTS` tiene contenido → confirmar que esa tarea es coherente con el sprint activo y enfocar el contexto

Formato de salida esperado:
```
SPRINT ACTIVO: S96
BRANCH: dev ✓
POSTGRES: UP ✓ | NATS: UP ✓ | ENGINE: DOWN ⚠

TAREAS PENDIENTES:
  [CRÍTICO] S96-A: Auto-generador stubs
  [CRÍTICO] S96-B: Filtro imports espurios
  [ALTO]    S96-F: Fix /auth/login 500 ← PRIORIDAD S96
  ...

FALLOS CONOCIDOS (no investigar salvo /fix-test):
  test_s31, test_s39, test_s47, test_s55, test_s63b

PROPUESTA PRIMERA TAREA: S96-F — Fix /auth/login 500
Razón: issue bloqueante para el dashboard, prioridad explícita en S96.
```
