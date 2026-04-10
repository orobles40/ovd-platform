"""
OVD Platform — API REST pública v1 (S12.B)
Copyright 2026 Omar Robles

Endpoints protegidos (Bearer JWT) para el panel de administración:

  GET  /api/v1/orgs/{org_id}/projects             — listar proyectos
  POST /api/v1/orgs/{org_id}/projects             — crear proyecto
  GET  /api/v1/orgs/{org_id}/projects/{project_id} — detalle proyecto + profile
  PUT  /api/v1/orgs/{org_id}/projects/{project_id} — actualizar proyecto
  DELETE /api/v1/orgs/{org_id}/projects/{project_id} — desactivar proyecto

  GET  /api/v1/orgs/{org_id}/cycles               — historial de ciclos (paginado)
  GET  /api/v1/orgs/{org_id}/cycles/{cycle_id}    — detalle ciclo (JSON completo)

  GET  /api/v1/orgs/{org_id}/stats                — métricas agregadas del org

  PUT  /api/v1/orgs/{org_id}/projects/{project_id}/profile — guardar stack profile
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from auth import AccessTokenPayload
from routers.auth_router import inject_current_user

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

router = APIRouter(prefix="/api/v1", tags=["api-v1"])


# ---------------------------------------------------------------------------
# Guard: el usuario solo puede acceder a su propio org_id
# ---------------------------------------------------------------------------

def _assert_org_access(current_user: AccessTokenPayload, org_id: str) -> None:
    if current_user.org_id != org_id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta organización")


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    directory: str


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    directory: str | None = None
    active: bool | None = None


class StackProfileUpsert(BaseModel):
    language: str = ""
    framework: str = ""
    db_engine: str = ""
    runtime: str = ""
    additional_stack: list[str] = []
    legacy_stack: str = ""
    external_integrations: str = ""
    qa_tools: str = ""
    ci_cd: str = ""
    constraints: str = ""
    code_style: str = ""
    project_description: str = ""
    team_size: str = ""


# ---------------------------------------------------------------------------
# Proyectos
# ---------------------------------------------------------------------------

@router.get("/orgs/{org_id}/projects")
async def list_projects(
    org_id: str,
    include_inactive: bool = Query(False),
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    _assert_org_access(current_user, org_id)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        rows = await conn.execute(
            """
            SELECT p.id, p.name, p.description, p.directory, p.active, p.time_created,
                   pp.language, pp.framework, pp.db_engine
            FROM ovd_projects p
            LEFT JOIN ovd_project_profiles pp ON pp.project_id = p.id AND pp.active = true
            WHERE p.org_id = %s
              AND (%s OR p.active = true)
            ORDER BY p.time_created DESC
            """,
            (org_id, include_inactive),
        )
        records = await rows.fetchall()

    return [
        {
            "id":          r[0],
            "name":        r[1],
            "description": r[2],
            "directory":   r[3],
            "active":      r[4],
            "created_at":  r[5].isoformat() if r[5] else None,
            "stack": {
                "language":  r[6],
                "framework": r[7],
                "db_engine": r[8],
            },
        }
        for r in records
    ]


@router.post("/orgs/{org_id}/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    org_id: str,
    body: ProjectCreate,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    _assert_org_access(current_user, org_id)

    project_id = str(uuid.uuid4()).replace("-", "").upper()[:26]
    now = datetime.now(timezone.utc)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        await conn.execute(
            """
            INSERT INTO ovd_projects (id, org_id, name, description, directory, active, time_created, time_updated)
            VALUES (%s, %s, %s, %s, %s, true, %s, %s)
            """,
            (project_id, org_id, body.name, body.description, body.directory, now, now),
        )
        await conn.commit()

    return {"id": project_id, "name": body.name, "org_id": org_id}


@router.get("/orgs/{org_id}/projects/{project_id}")
async def get_project(
    org_id: str,
    project_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    _assert_org_access(current_user, org_id)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        rows = await conn.execute(
            """
            SELECT p.id, p.name, p.description, p.directory, p.active, p.time_created,
                   pp.id, pp.language, pp.framework, pp.db_engine, pp.runtime,
                   pp.additional_stack, pp.legacy_stack, pp.external_integrations,
                   pp.qa_tools, pp.ci_cd, pp.constraints, pp.code_style,
                   pp.project_description, pp.team_size
            FROM ovd_projects p
            LEFT JOIN ovd_project_profiles pp ON pp.project_id = p.id AND pp.active = true
            WHERE p.id = %s AND p.org_id = %s
            """,
            (project_id, org_id),
        )
        r = await rows.fetchone()

    if not r:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    profile = None
    if r[6]:
        profile = {
            "id":                    r[6],
            "language":              r[7],
            "framework":             r[8],
            "db_engine":             r[9],
            "runtime":               r[10],
            "additional_stack":      r[11] or [],
            "legacy_stack":          r[12],
            "external_integrations": r[13],
            "qa_tools":              r[14],
            "ci_cd":                 r[15],
            "constraints":           r[16],
            "code_style":            r[17],
            "project_description":   r[18],
            "team_size":             r[19],
        }

    return {
        "id":          r[0],
        "name":        r[1],
        "description": r[2],
        "directory":   r[3],
        "active":      r[4],
        "created_at":  r[5].isoformat() if r[5] else None,
        "profile":     profile,
    }


@router.put("/orgs/{org_id}/projects/{project_id}")
async def update_project(
    org_id: str,
    project_id: str,
    body: ProjectUpdate,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    _assert_org_access(current_user, org_id)

    # SEC: allowlist explícita de columnas actualizables — previene SQL injection
    # por interpolación de nombres de columna (HIGH-01)
    _ALLOWED_PROJECT_COLUMNS = {"name", "description", "directory", "active"}
    updates = {
        k: v for k, v in body.model_dump().items()
        if v is not None and k in _ALLOWED_PROJECT_COLUMNS
    }
    if not updates:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")

    updates["time_updated"] = datetime.now(timezone.utc)
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [project_id, org_id]

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        result = await conn.execute(
            f"UPDATE ovd_projects SET {set_clause} WHERE id = %s AND org_id = %s",
            values,
        )
        await conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    return {"updated": True}


@router.delete("/orgs/{org_id}/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_project(
    org_id: str,
    project_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    _assert_org_access(current_user, org_id)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        result = await conn.execute(
            "UPDATE ovd_projects SET active = false, time_updated = %s WHERE id = %s AND org_id = %s",
            (datetime.now(timezone.utc), project_id, org_id),
        )
        await conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")


# ---------------------------------------------------------------------------
# Stack Profile
# ---------------------------------------------------------------------------

@router.put("/orgs/{org_id}/projects/{project_id}/profile", status_code=status.HTTP_200_OK)
async def upsert_stack_profile(
    org_id: str,
    project_id: str,
    body: StackProfileUpsert,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """Crea o actualiza el stack profile activo del proyecto."""
    _assert_org_access(current_user, org_id)

    now = datetime.now(timezone.utc)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        # Verificar que el proyecto pertenece al org
        row = await conn.execute(
            "SELECT id FROM ovd_projects WHERE id = %s AND org_id = %s", (project_id, org_id)
        )
        if not await row.fetchone():
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")

        # Desactivar profiles existentes
        await conn.execute(
            "UPDATE ovd_project_profiles SET active = false WHERE project_id = %s AND org_id = %s",
            (project_id, org_id),
        )

        # Insertar nuevo profile activo
        profile_id = str(uuid.uuid4()).replace("-", "").upper()[:26]
        additional_stack_json = json.dumps(body.additional_stack)

        await conn.execute(
            """
            INSERT INTO ovd_project_profiles
              (id, org_id, project_id, language, framework, db_engine, runtime,
               additional_stack, legacy_stack, external_integrations, qa_tools,
               ci_cd, constraints, code_style, project_description, team_size,
               active, time_created, time_updated)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,%s)
            """,
            (
                profile_id, org_id, project_id,
                body.language, body.framework, body.db_engine, body.runtime,
                additional_stack_json, body.legacy_stack, body.external_integrations,
                body.qa_tools, body.ci_cd, body.constraints, body.code_style,
                body.project_description, body.team_size,
                now, now,
            ),
        )
        await conn.commit()

    return {"id": profile_id, "project_id": project_id}


# ---------------------------------------------------------------------------
# Ciclos
# ---------------------------------------------------------------------------

@router.get("/orgs/{org_id}/cycles")
async def list_cycles(
    org_id: str,
    project_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    min_qa_score: int | None = Query(None),
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    _assert_org_access(current_user, org_id)

    conditions = ["cl.org_id = %s"]
    params: list[Any] = [org_id]

    if project_id:
        conditions.append("cl.project_id = %s")
        params.append(project_id)
    if min_qa_score is not None:
        conditions.append("cl.qa_score >= %s")
        params.append(min_qa_score)

    where = " AND ".join(conditions)
    params += [limit, offset]

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        rows = await conn.execute(
            f"""
            SELECT cl.id, cl.project_id, p.name as project_name,
                   cl.session_id, cl.feature_request,
                   cl.qa_score, cl.complexity, cl.fr_type,
                   cl.tokens_total, cl.estimated_cost_usd,
                   cl.time_created
            FROM ovd_cycle_logs cl
            LEFT JOIN ovd_projects p ON p.id = cl.project_id
            WHERE {where}
            ORDER BY cl.time_created DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        records = await rows.fetchall()

        # Total para paginación (params sin limit/offset)
        count_row = await conn.execute(
            f"SELECT COUNT(*) FROM ovd_cycle_logs cl WHERE {where}",
            params[:-2],
        )
        total = (await count_row.fetchone())[0]

    return {
        "total":  total,
        "limit":  limit,
        "offset": offset,
        "items": [
            {
                "id":             r[0],
                "project_id":     r[1],
                "project_name":   r[2],
                "session_id":     r[3],
                "feature_request": r[4][:120] + "..." if r[4] and len(r[4]) > 120 else r[4],
                "qa_score":       r[5],
                "complexity":     r[6],
                "fr_type":        r[7],
                "tokens_total":   r[8],
                "cost_usd":       float(r[9]) if r[9] else 0.0,
                "created_at":     r[10].isoformat() if r[10] else None,
            }
            for r in records
        ],
    }


@router.get("/orgs/{org_id}/cycles/{cycle_id}")
async def get_cycle(
    org_id: str,
    cycle_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    _assert_org_access(current_user, org_id)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        row = await conn.execute(
            """
            SELECT cl.id, cl.project_id, p.name,
                   cl.session_id, cl.thread_id, cl.feature_request,
                   cl.fr_analysis_json, cl.sdd_json, cl.agent_results_json, cl.qa_result_json,
                   cl.qa_score, cl.complexity, cl.fr_type, cl.oracle_involved,
                   cl.tokens_input, cl.tokens_output, cl.tokens_total,
                   cl.tokens_by_agent_json, cl.estimated_cost_usd, cl.time_created
            FROM ovd_cycle_logs cl
            LEFT JOIN ovd_projects p ON p.id = cl.project_id
            WHERE cl.id = %s AND cl.org_id = %s
            """,
            (cycle_id, org_id),
        )
        r = await row.fetchone()

    if not r:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    def _parse(s: str) -> Any:
        try:
            return json.loads(s) if s else {}
        except Exception:
            return {}

    return {
        "id":              r[0],
        "project_id":      r[1],
        "project_name":    r[2],
        "session_id":      r[3],
        "thread_id":       r[4],
        "feature_request": r[5],
        "fr_analysis":     _parse(r[6]),
        "sdd":             _parse(r[7]),
        "agent_results":   _parse(r[8]),
        "qa_result":       _parse(r[9]),
        "qa_score":        r[10],
        "complexity":      r[11],
        "fr_type":         r[12],
        "oracle_involved": r[13],
        "tokens": {
            "input":    r[14],
            "output":   r[15],
            "total":    r[16],
            "by_agent": _parse(r[17]),
        },
        "cost_usd":   float(r[18]) if r[18] else 0.0,
        "created_at": r[19].isoformat() if r[19] else None,
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/orgs/{org_id}/stats")
async def get_stats(
    org_id: str,
    days: int = Query(30, le=365),
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    _assert_org_access(current_user, org_id)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        row = await conn.execute(
            """
            SELECT
                COUNT(*)                          AS total_cycles,
                COALESCE(AVG(qa_score), 0)        AS avg_qa_score,
                COALESCE(SUM(tokens_total), 0)    AS total_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) AS total_cost_usd,
                COUNT(*) FILTER (WHERE qa_score >= 80) AS high_quality_cycles,
                COUNT(DISTINCT project_id)        AS active_projects
            FROM ovd_cycle_logs
            WHERE org_id = %s
              AND time_created >= NOW() - (%s * INTERVAL '1 day')
            """,
            (org_id, days),
        )
        r = await row.fetchone()

        # Distribución por tipo de FR
        fr_rows = await conn.execute(
            """
            SELECT fr_type, COUNT(*) as cnt
            FROM ovd_cycle_logs
            WHERE org_id = %s AND time_created >= NOW() - (%s * INTERVAL '1 day')
              AND fr_type IS NOT NULL
            GROUP BY fr_type ORDER BY cnt DESC
            """,
            (org_id, days),
        )
        fr_types = await fr_rows.fetchall()

        # Ciclos por día (últimos 14 días)
        daily_rows = await conn.execute(
            """
            SELECT DATE(time_created) as day, COUNT(*) as cnt
            FROM ovd_cycle_logs
            WHERE org_id = %s AND time_created >= NOW() - INTERVAL '14 days'
            GROUP BY day ORDER BY day
            """,
            (org_id,),
        )
        daily = await daily_rows.fetchall()

    return {
        "period_days":        days,
        "total_cycles":       r[0],
        "avg_qa_score":       round(float(r[1]), 1),
        "total_tokens":       int(r[2]),
        "total_cost_usd":     round(float(r[3]), 4),
        "high_quality_cycles": r[4],
        "active_projects":    r[5],
        "fr_type_distribution": {row[0]: row[1] for row in fr_types},
        "daily_cycles": [
            {"date": str(row[0]), "count": row[1]}
            for row in daily
        ],
    }
