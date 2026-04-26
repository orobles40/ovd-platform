## Convenciones OVD — TypeScript Backend (S58-pre)

### Infraestructura obligatoria — ORDEN DE ESCRITURA

Escribe estos archivos PRIMERO:

1. **`package.json`** — dependencias y scripts (`dev`, `build`, `test`) ← PRIMERO
2. **`tsconfig.json`** con `strict: true` ← SEGUNDO
3. **Configuración del test runner** (Vitest o Jest según el stack) ← TERCERO
4. **Módulos base** — tipos, schemas, interfaces ← ANTES de los que los importan
5. **`tests/<modulo>.test.ts`** — tests del módulo ← OBLIGATORIO SIEMPRE

**CHECKLIST antes de entregar:**
- [ ] `package.json` con todos los paquetes usados en el código
- [ ] `tsconfig.json` con `strict: true`
- [ ] Cada import corresponde a un archivo que creaste
- [ ] Al menos un archivo de tests por agente

### Estructura válida

✅ **CORRECTO:**
```
proyecto/
├── package.json
├── tsconfig.json
├── vitest.config.ts
├── src/
│   ├── routes/
│   │   └── users.ts
│   └── services/
│       └── userService.ts
└── tests/
    ├── users.test.ts
    └── userService.test.ts
```

### tsconfig.json mínimo

```json:tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src/**/*", "tests/**/*"]
}
```

### vitest.config.ts (si usa Vitest)

```typescript:vitest.config.ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
  },
})
```

---

### Validación de inputs con Zod

Usa Zod para validar todos los inputs en endpoints. Nunca confíes en tipos de TypeScript en tiempo de ejecución.

```typescript
import { z } from 'zod'

const CreateUserSchema = z.object({
  email: z.string().email(),
  orgId: z.string().uuid(),
  role: z.enum(['admin', 'user']),
})

// En el handler:
const parsed = CreateUserSchema.safeParse(req.body)
if (!parsed.success) {
  return res.status(422).json({ errors: parsed.error.issues })
}
```

---

### Tests Vitest — Formato obligatorio

Para cada módulo generado, incluye su archivo de test en la misma entrega.

```typescript:tests/userService.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { createUser, getUserById } from '../src/services/userService'

describe('UserService', () => {
  it('creates a user with valid data', async () => {
    const user = await createUser({ email: 'test@example.com', orgId: 'org-1', role: 'user' })
    expect(user.email).toBe('test@example.com')
    expect(user.orgId).toBe('org-1')
  })

  it('rejects invalid email', async () => {
    await expect(createUser({ email: 'not-email', orgId: 'org-1', role: 'user' })).rejects.toThrow()
  })
})
```

**Reglas:**
- Co-ubicados en `tests/` o junto al archivo (`*.test.ts`)
- Mínimo: happy path + input inválido + caso límite
- Sin `any` explícito en tests
- Verificación: `vitest run → N/N passed`

---

### Conexión a base de datos externa (Drizzle + PostgreSQL)

```typescript
// ✅ CORRECTO — desde variable de entorno
import { drizzle } from 'drizzle-orm/postgres-js'
import postgres from 'postgres'

const client = postgres(process.env.DATABASE_URL!)
export const db = drizzle(client)
```

```yaml
# docker-compose.yml — ✅ CORRECTO
environment:
  - DATABASE_URL=postgresql://user:pass@host.docker.internal:5432/dbname

# ❌ INCORRECTO — hardcoded
environment:
  - DATABASE_URL=postgresql://user:pass@postgres:5432/dbname  # 'postgres' es nombre de servicio Docker
```
