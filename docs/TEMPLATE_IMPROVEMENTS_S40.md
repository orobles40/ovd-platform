# Template Improvements — S40 (2026-04-23)

## Contexto

Análisis del ciclo `a2c87c99` (gestión de contratos con RUT chileno) reveló 4 problemas recurrentes
que afectan la calidad del código generado. QA score: 62/100, 21 issues, SDD compliance: False.

---

## Problemas detectados y fixes aplicados

### A — Tareas scaffold-only en el SDD (`system_sdd.md`)

**Problema:** El SDD generaba tareas tipo "crear estructura de archivos" o "definir interfaces vacías"
que los agentes implementaban como stubs sin código funcional, inflando el conteo de tareas sin aportar
valor real. Con 12 tareas en 3 agentes, varios agentes recibían 4-5 tareas de las cuales 1-2 eran solo
scaffolding.

**Fix:** Regla explícita en `system_sdd.md` (sección Artefacto 4):
- Prohibición de tareas scaffold-only con ejemplos ❌/✅
- Límite de 6-7 tareas por agente
- Tarea de tests unitarios obligatoria por agente

---

### B — Validación de RUT solo en frontend (`system_backend.md`)

**Problema:** El agente backend no generó validación server-side del RUT chileno. El agente frontend
sí la implementó (parcialmente), pero sin la lógica del dígito verificador en el servidor, cualquier
cliente puede enviar un RUT inválido y pasar la validación.

**Fix:** Nueva sección "Validación de RUT chileno" en `system_backend.md`:
- Implementación de referencia de `validate_rut()` con algoritmo de módulo 11
- `clean_rut()` y `format_rut()` como helpers
- Patrón `require_valid_rut()` para usar en endpoints FastAPI
- Reglas de almacenamiento (sin puntos ni guión) y constraint UNIQUE por org_id
- Casos de test obligatorios listados

---

### C — Tests Vitest ausentes en frontend (`system_frontend.md`)

**Problema:** El agente frontend no generó ningún archivo de test. El ciclo detectó 0 test files
en los artefactos. A pesar de tener la sección TDD en el template, la instrucción era implícita.

**Fix:** Nueva sección "Tests Vitest obligatorios" en `system_frontend.md`:
- Estructura de archivos explícita (`.test.tsx` mismo directorio)
- Qué testear obligatoriamente: componentes y hooks
- Setup mínimo con ejemplo concreto de `ContractWizard.test.tsx`
- Regla: mínimo 2 tests por componente (smoke + comportamiento principal)

---

### D — Hooks generados sin integrar (`system_frontend.md`)

**Problema:** El hook `useContractValidation` fue generado correctamente pero no se usó en el
wizard. El QA detectó esto como issue crítico. La causa: el template no exigía explícitamente
que cada hook generado aparezca en el `import` de algún componente.

**Fix:** Regla "Hooks — regla de integración obligatoria" en `system_frontend.md`:
- Instrucción explícita: si generas un hook, debes usarlo en el componente correspondiente
- Checklist antes de entregar: ¿cada `useXxx` aparece en al menos un `import`?
- Clasificación como bug (no feature) si el hook no está conectado

---

## Archivos modificados

| Archivo | Cambios |
|---------|---------|
| `src/engine/templates/system_sdd.md` | Reglas tasks: max 6-7 por agente, no scaffold, tests obligatorios, hooks explícitos |
| `src/engine/templates/system_backend.md` | Sección validación RUT chileno con implementación de referencia |
| `src/engine/templates/system_frontend.md` | Sección tests Vitest + regla hooks + validación RUT en UI |

---

## Impacto esperado en próximo ciclo

| Métrica | Antes (a2c87c99) | Objetivo |
|---------|-----------------|---------|
| QA score | 62/100 | ≥ 80/100 |
| SDD compliance | False | True |
| Issues QA | 21 | < 5 |
| Test files detectados | 0 | ≥ 1 por agente |
| Hooks sin integrar | 1 (useContractValidation) | 0 |
| Validación RUT backend | ausente | presente |

---

## Próximos pasos

- Lanzar ciclo de validación con el mismo FR (gestión de contratos + RUT)
- Comparar QA score y conteo de issues
- Si QA ≥ 80/100: considerar mejoras completadas
- Si QA < 80/100: revisar issues residuales y aplicar siguiente ronda de fixes
