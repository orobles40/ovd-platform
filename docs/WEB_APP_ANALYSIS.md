# OVD Platform — Análisis App Web vs. Backend
**Fecha:** 2026-03-25
**Autor:** Análisis técnico Claude Code / Omar Robles

---

## Contexto

La OVD Platform está construida como fork de opencode. El repositorio tiene dos capas:

- **Backend** (`packages/opencode/src/ovd/` + `server/routes/`) — API completa, multi-tenant, implementada en TypeScript/Bun/Hono.
- **Frontend** (`packages/app/`) — UI SolidJS heredada de opencode, sin modificaciones OVD.

Este documento registra el análisis del gap entre ambas capas y define el trabajo pendiente para el frontend.

---

## 1. Funcionalidades actuales de la app web

La app web es el **frontend opencode sin cambios OVD**. Fue diseñada para uso local de un único desarrollador.

| Area | Funcionalidad disponible |
|---|---|
| Proyectos | Abrir carpetas locales, historial de proyectos recientes |
| Sesiones AI | Chat con Claude/modelos via opencode, historial |
| Editor | Vista de archivos, diff de cambios, file tree |
| Terminal | Terminal integrado en el browser |
| Permisos | Aprobar/rechazar acciones del agente (nivel opencode, no OVD) |
| Configuracion | Proveedores de AI, modelos, MCP servers, keybindings |
| Servidores | Conectar a multiples instancias de opencode |

**Importante:** La app no tiene login, no conoce el concepto de org/usuario, y no tiene ningun componente OVD.

---

## 2. API OVD implementada en el backend

Todo lo siguiente existe y funciona hoy — solo accesible via curl/Postman, no desde la UI.

### Tenant (sin JWT requerido para bootstrap)

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/tenant/org` | Crear organizacion + primer admin (bootstrap) |
| `POST` | `/tenant/auth/login` | Obtener JWT |
| `GET` | `/tenant/org` | Datos de la org autenticada |
| `PATCH` | `/tenant/org` | Actualizar idioma, config |
| `GET` | `/tenant/project` | Listar proyectos de la org |
| `POST` | `/tenant/project` | Crear proyecto |
| `DELETE` | `/tenant/project/:id` | Eliminar proyecto (soft) |
| `POST` | `/tenant/users` | Invitar usuario (admin) |
| `GET` | `/tenant/users` | Listar usuarios de la org |
| `POST` | `/tenant/webhooks` | Crear suscripcion de webhook |
| `GET` | `/tenant/webhooks` | Listar webhooks de la org |

### OVD Sessions (requieren JWT)

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/ovd/session` | Iniciar ciclo OVD (Feature Request → LangGraph) |
| `GET` | `/ovd/session/:id` | Estado de la sesion |
| `POST` | `/ovd/session/:id/approve` | Aprobar/rechazar accion del agente |
| `POST` | `/ovd/session/:id/escalate` | Escalar a supervision humana |
| `GET` | `/ovd/sessions` | Historial de sesiones del proyecto |
| `GET` | `/ovd/health` | Health check del OVD Engine |

### Project Profile & Agent Config

| Metodo | Ruta | Descripcion |
|---|---|---|
| `PUT` | `/ovd/project/:id/profile` | Configurar stack tecnologico del proyecto |
| `GET` | `/ovd/project/:id/profile` | Ver perfil tecnologico |
| `DELETE` | `/ovd/project/:id/profile` | Eliminar perfil |
| `PUT` | `/ovd/config/org` | Config de agentes nivel org |
| `PUT` | `/ovd/config/project/:id` | Config nivel proyecto |
| `PUT` | `/ovd/config/project/:id/agent/:role` | Config nivel agente |
| `GET` | `/ovd/config/project/:id/resolved` | Config efectiva combinada |

### RAG

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/ovd/project/:id/rag/seed` | Seed del RAG desde el perfil del proyecto |
| `POST` | `/ovd/rag/index` | Indexar un documento manualmente |
| `POST` | `/ovd/rag/search` | Busqueda semantica |
| `GET` | `/ovd/rag/search` | Busqueda semantica via query params |
| `POST` | `/ovd/project/:id/index-docs` | Indexar .md del directorio del proyecto |

### Model Registry

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/ovd/models/register` | Registrar modelo fine-tuneado |
| `GET` | `/ovd/models` | Listar todos los modelos de la org |
| `GET` | `/ovd/models/active` | Modelos activos por agente |
| `POST` | `/ovd/models/:id/activate` | Activar modelo |
| `POST` | `/ovd/models/:id/deprecate` | Desactivar modelo |

---

## 3. El gap: lo que falta en el frontend

```
packages/app (SolidJS)          packages/opencode/src (Bun/Hono)
─────────────────────           ─────────────────────────────────
Login / Auth         ✗    ←→    POST /tenant/auth/login         ✅
Dashboard org        ✗    ←→    GET  /tenant/org                ✅
Gestion proyectos    ✗    ←→    CRUD /tenant/project            ✅
Lanzador ciclo OVD   ✗    ←→    POST /ovd/session               ✅
Panel aprobacion     ✗    ←→    POST /ovd/session/:id/approve   ✅
Historial sesiones   ✗    ←→    GET  /ovd/sessions              ✅
Project Profile form ✗    ←→    PUT  /ovd/project/:id/profile   ✅
Agent Config form    ✗    ←→    PUT  /ovd/config/...            ✅
RAG search UI        ✗    ←→    POST /ovd/rag/search            ✅
Model registry view  ✗    ←→    GET  /ovd/models                ✅
Quota dashboard      ✗    ←→    (calculado por org en backend)  ✅
```

**Todo el backend existe. El 100% del frontend OVD esta por construir.**

---

## 4. Opciones para el frontend OVD

### Opcion A — Extender packages/app (recomendada para MVP)
Agregar paginas OVD dentro del mismo SolidJS. Ventajas:
- Design system ya existe (componentes, estilos Tailwind, i18n)
- Routing ya configurado
- Menos codigo duplicado

Desventaja: la app fue disenada para single-user local, hay tension arquitectonica con multi-tenant.

### Opcion B — Nueva app packages/ovd-dashboard
Una SPA separada para OVD. Ventajas:
- Arquitectura limpia desde cero para multi-tenant
- Sin deuda tecnica del upstream opencode

Desventaja: mas trabajo inicial, duplicar design system.

**Recomendacion:** Opcion A para el MVP (Sprint 9-11). Si el producto escala, migrar a Opcion B.

---

## 5. Componentes UI prioritarios (backlog)

### Prioridad critica (bloquea uso del producto)
- [ ] Pantalla de Login (POST /tenant/auth/login)
- [ ] Formulario lanzador de ciclo OVD (Feature Request → POST /ovd/session)
- [ ] Panel de aprobacion humana (polling estado + POST /ovd/session/:id/approve)

### Prioridad alta
- [ ] Historial de sesiones OVD con estado
- [ ] Formulario Project Profile (stack tecnologico)
- [ ] Indicador de health del OVD Engine

### Nice-to-have
- [ ] Dashboard de quota por org
- [ ] Gestion de usuarios/invitaciones (solo admin)
- [ ] RAG search UI
- [ ] Model registry view
- [ ] Gestion de webhooks

---

## 6. Notas de arquitectura

- La app se sirve **desde el Bridge** en el mismo puerto 3000. El frontend esta proxied desde `app.opencode.ai` en la ruta `/` del servidor. Para OVD se necesita servir assets propios desde `/ovd/` o similar.
- Autenticacion: JWT HS256 firmado con `JWT_SECRET`. Expira en 8h por defecto. El token va en `Authorization: Bearer <token>`.
- El tenant middleware extrae `org_id`, `user_id`, `role` del JWT y los inyecta en el contexto de cada request.
- Las rutas OVD estan en `/ovd/...` y `/v1/ovd/...` (ambas funcionales).

---

## 7. Estado al 2026-03-25

- Backend OVD: **100% implementado** (Sprints 1-7 completados)
- Frontend OVD: **0% implementado** (pendiente planificacion)
- Siguiente accion: definir sprint para MVP frontend (ver backlog arriba)
