#!/usr/bin/env python3
"""
OVD Platform — Seed inicial de base de datos
Copyright 2026 Omar Robles

Crea los datos mínimos para iniciar el sistema en desarrollo local:
  - Organización "Omar Robles Dev"
  - Usuario admin: omar@omarrobles.dev / ovd-dev-2026
  - Proyecto de demo: OVD Platform

Uso:
    DATABASE_URL=postgresql://ovd_dev:changeme@localhost:5432/ovd_dev \\
        python3 scripts/seed.py

    # Con --force: reemplaza datos si ya existen
    DATABASE_URL=... python3 scripts/seed.py --force

    # Solo validar (no modificar BD)
    DATABASE_URL=... python3 scripts/seed.py --dry-run

Requisitos:
    pip install psycopg[binary] passlib[argon2]
    O bien: cd src/engine && uv run python3 ../../scripts/seed.py
"""
import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Dependencias opcionales — informar claramente si faltan
# ---------------------------------------------------------------------------
try:
    import psycopg
except ImportError:
    sys.exit("ERROR: psycopg no instalado. Ejecuta: pip install psycopg[binary]")

try:
    from passlib.hash import argon2 as _argon2
except ImportError:
    sys.exit("ERROR: passlib no instalado. Ejecuta: pip install passlib[argon2]")

# ---------------------------------------------------------------------------
# Datos semilla
# ---------------------------------------------------------------------------

SEED_ORG_ID   = "01SEED0000000000000000ORG1"
SEED_USER_ID  = "01SEED0000000000000000USR1"
SEED_PROJ_ID  = "01SEED0000000000000000PRJ1"

SEED_ORG = {
    "id":   SEED_ORG_ID,
    "name": "Omar Robles Dev",
    "plan": "starter",
}

SEED_USER = {
    "id":       SEED_USER_ID,
    "org_id":   SEED_ORG_ID,
    "email":    "omar@omarrobles.dev",
    "password": "ovd-dev-2026",
    "role":     "admin",
}

SEED_PROJECT = {
    "id":          SEED_PROJ_ID,
    "org_id":      SEED_ORG_ID,
    "name":        "OVD Platform",
    "description": "Proyecto de demostración — OVD Engine + Dashboard",
    "directory":   "/srv/ovd-platform",
}

SEED_STACK = {
    "id":         "01SEED0000000000000STACK1",
    "project_id": SEED_PROJ_ID,
    "language":   "Python",
    "framework":  "FastAPI / LangGraph",
    "database":   "PostgreSQL 16 + pgvector",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str)  -> None: print(f"  [seed] {msg}")
def ok(msg: str)   -> None: print(f"  [seed] ✓ {msg}")
def warn(msg: str) -> None: print(f"  [seed] ⚠ {msg}", file=sys.stderr)
def fail(msg: str) -> None: print(f"  [seed] ✗ {msg}", file=sys.stderr); sys.exit(1)


def ulid_placeholder() -> str:
    """Genera un ID único simple (UUID4 sin guiones, 26 chars)."""
    return uuid.uuid4().hex[:26].upper()


# ---------------------------------------------------------------------------
# Operaciones de seed
# ---------------------------------------------------------------------------

def seed_org(conn, force: bool, dry_run: bool) -> bool:
    cur = conn.execute(
        "SELECT id FROM ovd_orgs WHERE id = %s",
        (SEED_ORG["id"],),
    )
    exists = cur.fetchone() is not None

    if exists and not force:
        warn(f"Organización ya existe: {SEED_ORG['name']} (usar --force para reemplazar)")
        return False

    if dry_run:
        log(f"[dry-run] Upsert org: {SEED_ORG['name']}")
        return True

    conn.execute("""
        INSERT INTO ovd_orgs (id, name, plan, active, created_at)
        VALUES (%s, %s, %s, TRUE, %s)
        ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name,
                plan = EXCLUDED.plan
    """, (SEED_ORG["id"], SEED_ORG["name"], SEED_ORG["plan"], datetime.now(timezone.utc)))
    ok(f"Organización: {SEED_ORG['name']} ({SEED_ORG['id']})")
    return True


def seed_user(conn, force: bool, dry_run: bool) -> bool:
    cur = conn.execute(
        "SELECT id FROM ovd_users WHERE id = %s",
        (SEED_USER["id"],),
    )
    exists = cur.fetchone() is not None

    if exists and not force:
        warn(f"Usuario ya existe: {SEED_USER['email']} (usar --force para reemplazar)")
        return False

    if dry_run:
        log(f"[dry-run] Upsert user: {SEED_USER['email']}")
        return True

    pwd_hash = _argon2.hash(SEED_USER["password"])
    conn.execute("""
        INSERT INTO ovd_users (id, org_id, email, password_hash, role, active, created_at)
        VALUES (%s, %s, %s, %s, %s, TRUE, %s)
        ON CONFLICT (id) DO UPDATE
            SET email         = EXCLUDED.email,
                password_hash = EXCLUDED.password_hash,
                role          = EXCLUDED.role
    """, (
        SEED_USER["id"], SEED_USER["org_id"], SEED_USER["email"],
        pwd_hash, SEED_USER["role"], datetime.now(timezone.utc),
    ))
    ok(f"Usuario: {SEED_USER['email']} / {SEED_USER['password']} (rol: {SEED_USER['role']})")
    return True


def seed_project(conn, force: bool, dry_run: bool) -> bool:
    cur = conn.execute(
        "SELECT id FROM ovd_projects WHERE id = %s",
        (SEED_PROJECT["id"],),
    )
    exists = cur.fetchone() is not None

    if exists and not force:
        warn(f"Proyecto ya existe: {SEED_PROJECT['name']} (usar --force para reemplazar)")
        return False

    if dry_run:
        log(f"[dry-run] Upsert project: {SEED_PROJECT['name']}")
        return True

    conn.execute("""
        INSERT INTO ovd_projects (id, org_id, name, description, directory, active, created_at)
        VALUES (%s, %s, %s, %s, %s, TRUE, %s)
        ON CONFLICT (id) DO UPDATE
            SET name        = EXCLUDED.name,
                description = EXCLUDED.description,
                directory   = EXCLUDED.directory
    """, (
        SEED_PROJECT["id"], SEED_PROJECT["org_id"],
        SEED_PROJECT["name"], SEED_PROJECT["description"],
        SEED_PROJECT["directory"], datetime.now(timezone.utc),
    ))
    ok(f"Proyecto: {SEED_PROJECT['name']} ({SEED_PROJECT['id']})")
    return True


def seed_stack(conn, force: bool, dry_run: bool) -> bool:
    cur = conn.execute(
        "SELECT id FROM ovd_stack_profiles WHERE id = %s",
        (SEED_STACK["id"],),
    )
    exists = cur.fetchone() is not None

    if exists and not force:
        return False

    if dry_run:
        log(f"[dry-run] Upsert stack: {SEED_STACK['language']}/{SEED_STACK['framework']}")
        return True

    conn.execute("""
        INSERT INTO ovd_stack_profiles (id, project_id, language, framework, database, active, created_at)
        VALUES (%s, %s, %s, %s, %s, TRUE, %s)
        ON CONFLICT (id) DO UPDATE
            SET language  = EXCLUDED.language,
                framework = EXCLUDED.framework,
                database  = EXCLUDED.database
    """, (
        SEED_STACK["id"], SEED_STACK["project_id"],
        SEED_STACK["language"], SEED_STACK["framework"],
        SEED_STACK["database"], datetime.now(timezone.utc),
    ))
    ok(f"Stack Profile: {SEED_STACK['language']} / {SEED_STACK['framework']}")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="OVD Platform — Seed inicial de base de datos",
    )
    parser.add_argument("--force",   action="store_true", help="Reemplazar datos existentes")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar lo que haría sin ejecutar")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        fail("DATABASE_URL no configurada")

    # psycopg sync (no async) para script CLI
    try:
        with psycopg.connect(database_url) as conn:
            print()
            print("OVD Platform — Seed de datos de desarrollo")
            print("=" * 50)

            changes = 0
            changes += seed_org(conn,     args.force, args.dry_run)
            changes += seed_user(conn,    args.force, args.dry_run)
            changes += seed_project(conn, args.force, args.dry_run)
            changes += seed_stack(conn,   args.force, args.dry_run)

            if not args.dry_run:
                conn.commit()

            print()
            if changes:
                print(f"Seed completado: {changes} registro(s) {'(dry-run)' if args.dry_run else 'escritos'}.")
            else:
                print("Sin cambios. Todos los registros ya existen.")

            print()
            print("Credenciales de acceso al dashboard:")
            print(f"  URL:      http://localhost:5173")
            print(f"  Email:    {SEED_USER['email']}")
            print(f"  Password: {SEED_USER['password']}")
            print()

    except psycopg.OperationalError as e:
        fail(f"No se puede conectar a la BD: {e}")


if __name__ == "__main__":
    main()
