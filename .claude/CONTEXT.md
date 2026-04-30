# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S102 (completado) / S103 (planificación)
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S102
- **Tests:** 1675 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(5 pre-existentes siguen fallando: test_s31, test_s39, test_s47, test_s55, test_s63b)*
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-04-29 — S102)

**Completado:**
- S102-A: postprocesador `_fix_silent_service_import()` — elimina try/except ImportError silencioso en routers
- S102-B: `_fix_sdd_agent_assignments()` — keyword inference para tareas sin output_file (ACTIVO con falso positivo)
- S102-C: campo `output_file` obligatorio en `system_sdd.md`
- test_s102.py: 24/24 PASS
- INFORME_PRUEBA_S102.md generado (mis-entregas/contratos-beneficios/)

**Ciclo validación S102** (77a54e0c):
- QA: **60/100** (force-deliver — 3 run_tests failures), Security: 100/100, **30m 35s**
- Tokens: 336,861 entrada / 65,269 salida — 4 agentes activados (hito histórico)
- GAP principal: coherencia inter-agente — functions inventadas en tests vs lo que existe en services.py
- S102-B falso positivo: "frontend" sustantivo activa re-routing devops→frontend (docker-compose)
- S91-A auto-genera router.py pero hereda anti-patrón try/except ImportError (S102-A no alcanza)
- Ronda 2 (selective retry): main.py mejoró a 600 bytes con router pattern; aún falla por list_contracts inexistente

---

## Próxima sesión

**Primera tarea S103 (prioridades):**
1. **P1** — Shared Type Contract en SDD: tabla normalizada de clases/funciones para coordinación entre agentes (CRÍTICO)
2. **P2** — Pre-flight import validator: ast.parse() en run_tests para detectar referencias sin import antes de escribir (CRÍTICO)
3. **P3** — Refinar keywords S102-B: solo `.tsx/.jsx`, component names; no sustantivos genéricos como "frontend"
4. **P4** — Propagación rename S101-A: actualizar todos los importadores al renombrar service→services
5. **P5** — Aplicar S102-A a S91-A: los archivos auto-generados también deben pasar por el postprocesador

---

## Fallos pre-existentes a corregir (S96-G)

> Sesión dedicada planificada. No investigar en sesiones de features.
> Usar `/fix-test` para abordarlos sistemáticamente.

| Test | Causa conocida | Prioridad |
|---|---|---|
| `test_s31::test_cycle_start_ts_reciente` | Flaky por timing — race condition | Media |
| `test_s39::test_usa_cap_800_en_truncate` | Cap obsoleto desde S61-B | Alta (fácil) |
| `test_s47::test_dispatch_frontend_despacha_pendientes` | Roto por S94-fix | Alta |
| `test_s55::test_write_artifacts_overwrites_when_new_content_larger` | write_artifacts cambió post-S55 | Alta |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError por S94-fix | Alta |

---

## Issues abiertos

| Issue | Impacto | Estado | Sprint |
|---|---|---|---|
| `POST /auth/login` → 500 | Bloquea dashboard web | ✅ RESUELTO | S96-F |
| `test_s63b_cleanup_in_retry_round_zero` | Suite no limpia | Pendiente | S96-D |
| QA score ≤ 50 en ciclos con 2 agentes | Conflicto BD perfil/FR | Pendiente | S97-A |
| devops sobrescribe tests del backend | write_artifacts sin protección | Pendiente | S97-B |

---

## Ciclos de referencia

| Sprint | Hash | QA | pytest | Duración |
|--------|------|----|--------|----------|
| S76 | c0e2e71e | **93** | collection_error | 13 min |
| S84 | e98bf96e | — | exit 2 | 5m 38s |
| S99 | — | **60** | — | 18m |
| S100 | — | **65** | — | 21m |
| S101 | 1b359097 | **90** (PASS) | 3 passed | 10m 41s |
| S102 | 77a54e0c | **60** | exit 2 × 3 (3 retries) | 30m 35s |

---

## Skills activos (Fase 1 — desde 2026-04-28)

| Skill | Comando | Estado |
|---|---|---|
| `session-start` | `/session-start` | ✅ Activo |
| `session-close` | `/session-close "resumen"` | ✅ Activo |
| `run-tests` | `/run-tests [marker]` | ✅ Activo |
| `pre-push` | `/pre-push` | ✅ Activo |

**Fase 2 — Evaluar impacto en:** 2026-05-12 (2 semanas)
Skills candidatos Fase 2: `tdd-cycle`, `tdd-green`, `cycle-debug`, `fix-test`
