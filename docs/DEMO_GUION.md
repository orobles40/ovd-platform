# Guión Demo OVD Platform — 2026-05-18

**Presentador:** Omar Robles  
**App:** OVD Desktop v0.3.0 (`OVD Platform_0.3.0_aarch64.dmg`)  
**Engine:** `https://ovd-platform-qjk25.ondigitalocean.app`  
**Duración estimada:** ~15 min en vivo (ciclo ~12 min + navegación ~3 min)

---

## Preparación previa (antes de entrar a la sala)

- [ ] Abrir OVD Desktop, verificar que está configurado con la URL del engine
- [ ] Hacer login con `admin@codigonet.cloud` — confirmar que el Workspace carga
- [ ] Verificar badge del engine (verde) en la barra superior
- [ ] Tener `~/Desktop/turnos-demo/` como carpeta de salida configurada en el proyecto
- [ ] Cerrar otras apps pesadas (liberar GPU para el modelo)
- [ ] Conectar a WiFi estable (el ciclo hace ~200 peticiones al engine en DO)

---

## Paso 1 — Contexto (1 min)

> "OVD Platform es un agente de desarrollo interno. Recibe un requerimiento funcional
> en lenguaje natural y entrega código listo para ejecutar: backend, frontend, base de datos,
> infraestructura y tests. Todo corre en la nube — el motor está en DigitalOcean."

Mostrar: pantalla de Workspace con el proyecto "Sistema de Turnos Médicos".

---

## Paso 2 — Enviar el requerimiento (1 min)

Hacer clic en el proyecto → abrir FrLauncher.

**FR a escribir (copiar exacto):**

```
Implementar módulo de agendamiento de turnos médicos.

El sistema debe permitir:
- Registrar pacientes con RUT, nombre y teléfono
- Registrar médicos con especialidad y disponibilidad semanal
- Agendar turnos: paciente + médico + fecha + hora
- Listar turnos del día con estado (pendiente/confirmado/cancelado)
- Cancelar un turno con motivo

Stack: FastAPI + SQLAlchemy async + PostgreSQL + React + TypeScript
```

Verificar que el selector de rama muestra `main` (o crear rama `feature/agendamiento-turnos`).

Activar **Auto-aprobar SDD** → clic en **Enviar**.

---

## Paso 3 — Pipeline en ejecución (~12 min)

Mostrar el sidebar izquierdo con los pasos del pipeline avanzando:

| Paso | Duración aprox. | Qué mostrar |
|------|----------------|-------------|
| Análisis FR | ~1 min | "El agente está analizando el requerimiento..." |
| Diseño técnico | ~2 min | "Genera el SDD — arquitectura de módulos" |
| Implementación | ~6 min | Eventos SSE apareciendo en el feed |
| Seguridad | ~1 min | — |
| QA Review | ~1 min | Score esperado: ≥ 85/100 |
| Entrega | ~30 s | — |

**Durante la espera:** explicar la arquitectura del pipeline, los agentes especializados
(backend, frontend, database, devops, security, QA), y que todo corre en paralelo cuando es posible.

---

## Paso 4 — Entrega completada

Al aparecer la card verde "Entrega completada":

1. Mostrar el score QA y métricas de telemetría (tokens, duración)
2. Clic en **Abrir** → se abre `~/Desktop/turnos-demo/` con el código generado
3. Mostrar la estructura de archivos generados en Finder
4. Opcional: abrir `src/main.py` y mostrar que es código real y ejecutable

---

## Paso 5 — Cierre (1 min)

> "En ~12 minutos tenemos un backend FastAPI funcional, un frontend React conectado,
> los modelos de BD, los tests y la infraestructura Docker. Lo que antes tomaba días
> de scaffolding ahora es el punto de partida — el equipo entra directo a la lógica
> de negocio específica del cliente."

---

## Plan B — si algo falla

| Problema | Acción |
|---|---|
| SSE se desconecta | Esperar — el engine sigue corriendo, el desktop reconecta automáticamente |
| Ciclo tarda más de 15 min | Normal si el modelo está bajo carga — mostrar el pipeline sidebar y explicar |
| QA < 80 | Aceptable para el demo — mencionar que el baseline de producción es QA ~90 |
| Engine devuelve error | Abrir `https://ovd-platform-qjk25.ondigitalocean.app/health` para verificar; mostrar ciclo pregrabado si es necesario |
| Desktop no conecta | Verificar URL en Settings: `https://ovd-platform-qjk25.ondigitalocean.app` |

---

## Configuración del desktop para el demo

**Settings → Engine URL:**
```
https://ovd-platform-qjk25.ondigitalocean.app
```

**Proyecto en Workspace:**
- Nombre: `Sistema de Turnos Médicos`
- Directorio local: `~/Desktop/turnos-demo`
- Carpeta de salida: `~/Desktop/turnos-demo`
- Stack: `FastAPI + React`

---

## Checklist final pre-demo

- [ ] Engine health: `curl https://ovd-platform-qjk25.ondigitalocean.app/health` → `{"status":"ok"}`
- [ ] Login funcionando con `admin@codigonet.cloud`
- [ ] Carpeta `~/Desktop/turnos-demo/` vacía (limpiar si hubo dry run)
- [ ] OVD Desktop v0.3.0 instalado desde `.dmg`
- [ ] Batería cargada o conectado a corriente
