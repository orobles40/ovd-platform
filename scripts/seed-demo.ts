/**
 * OVD Platform — Seed de datos de demo
 * Copyright 2026 Omar Robles
 *
 * Crea una organizacion, usuario y proyecto de demo en la base de datos.
 * Diseñado para usar en demos internas de Omar Robles y en entornos de CI.
 *
 * Uso:
 *   DATABASE_URL=postgresql://... bun run scripts/seed-demo.ts
 *   DATABASE_URL=postgresql://... bun run scripts/seed-demo.ts --reset
 *
 * --reset: elimina los datos de demo antes de volver a crearlos.
 *
 * Credenciales que crea:
 *   Org:    omar-demo  (slug)
 *   Email:  demo@omarrobles.dev
 *   Pass:   Demo2026!
 *   Rol:    admin
 */
import { drizzle } from "drizzle-orm/postgres-js"
import postgres from "postgres"
import { eq } from "drizzle-orm"
import { ulid } from "ulid"
import {
  OrganizationTable,
  UserTable,
  TenantProjectTable,
} from "../packages/opencode/src/tenant/schema"

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const DATABASE_URL = process.env.DATABASE_URL
if (!DATABASE_URL) {
  console.error("ERROR: DATABASE_URL no configurada")
  process.exit(1)
}

const RESET = process.argv.includes("--reset")

const DEMO_ORG = {
  id: "01DEMO0000000000000000ORG0",
  name: "Omar Robles Demo",
  slug: "omar-demo",
  plan: "pro" as const,
}

const DEMO_USER = {
  id: "01DEMO0000000000000000USR0",
  org_id: DEMO_ORG.id,
  email: "demo@omarrobles.dev",
  password: "Demo2026!",
  role: "admin" as const,
}

const DEMO_PROJECT = {
  id: "01DEMO0000000000000000PRJ0",
  org_id: DEMO_ORG.id,
  name: "OVD Platform — Demo",
  description: "Proyecto de demo para mostrar el ciclo FR → SDD → Agentes → Entrega",
  directory: process.cwd(),
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const sql = postgres(DATABASE_URL, { max: 1 })
const db = drizzle({ client: sql })

async function clean() {
  console.log("Limpiando datos de demo previos...")
  await db.delete(TenantProjectTable).where(eq(TenantProjectTable.org_id, DEMO_ORG.id))
  await db.delete(UserTable).where(eq(UserTable.org_id, DEMO_ORG.id))
  await db.delete(OrganizationTable).where(eq(OrganizationTable.id, DEMO_ORG.id))
  console.log("  ✓ Limpieza completada")
}

async function seed() {
  // Org
  const existingOrg = await db
    .select()
    .from(OrganizationTable)
    .where(eq(OrganizationTable.id, DEMO_ORG.id))
    .limit(1)

  if (existingOrg.length > 0) {
    console.log("  - Org demo ya existe, saltando")
  } else {
    await db.insert(OrganizationTable).values(DEMO_ORG)
    console.log(`  ✓ Org creada: ${DEMO_ORG.name} (${DEMO_ORG.slug})`)
  }

  // User
  const existingUser = await db
    .select()
    .from(UserTable)
    .where(eq(UserTable.id, DEMO_USER.id))
    .limit(1)

  if (existingUser.length > 0) {
    console.log("  - Usuario demo ya existe, saltando")
  } else {
    const password_hash = await Bun.password.hash(DEMO_USER.password)
    await db.insert(UserTable).values({
      id: DEMO_USER.id,
      org_id: DEMO_USER.org_id,
      email: DEMO_USER.email,
      password_hash,
      role: DEMO_USER.role,
    })
    console.log(`  ✓ Usuario creado: ${DEMO_USER.email}`)
  }

  // Project
  const existingProject = await db
    .select()
    .from(TenantProjectTable)
    .where(eq(TenantProjectTable.id, DEMO_PROJECT.id))
    .limit(1)

  if (existingProject.length > 0) {
    console.log("  - Proyecto demo ya existe, saltando")
  } else {
    await db.insert(TenantProjectTable).values(DEMO_PROJECT)
    console.log(`  ✓ Proyecto creado: ${DEMO_PROJECT.name}`)
  }
}

async function main() {
  console.log(`\nOVD Platform — Seed de demo`)
  console.log(`DATABASE_URL: ${DATABASE_URL.replace(/:([^@]+)@/, ":***@")}\n`)

  try {
    if (RESET) await clean()
    console.log("Creando datos de demo...")
    await seed()

    console.log(`
Seed completado. Credenciales de demo:
  URL:      http://localhost:4096  (o el puerto donde corra bun dev)
  Email:    ${DEMO_USER.email}
  Password: ${DEMO_USER.password}
  Org:      ${DEMO_ORG.slug}

Para obtener un JWT de demo:
  curl -s -X POST http://localhost:4096/tenant/auth/login \\
    -H "Content-Type: application/json" \\
    -d '{"email":"${DEMO_USER.email}","password":"${DEMO_USER.password}"}' | jq .token

Para iniciar un ciclo OVD desde el TUI:
  /ovd  (o Ctrl+K → "OVD: Iniciar nuevo ciclo")
`)
  } finally {
    await sql.end()
  }
}

main().catch((err) => {
  console.error("ERROR:", err)
  process.exit(1)
})
