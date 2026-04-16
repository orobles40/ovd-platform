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

import io
import json
import os
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import AccessTokenPayload
from routers.auth_router import inject_current_user
import pending_store

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


# ---------------------------------------------------------------------------
# Aprobaciones pendientes (web dashboard — panel Approval.tsx)
# ---------------------------------------------------------------------------

@router.get("/orgs/{org_id}/approvals/pending")
async def list_pending_approvals(
    org_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """
    Retorna las sesiones con aprobación de SDD pendiente para un org.
    Alimentado por el almacén en memoria pending_store (se pobla cuando
    el stream SSE detecta un interrupt de request_approval).
    """
    _assert_org_access(current_user, org_id)

    items = pending_store.list_by_org(org_id)

    # Enriquecer con project_name si hay project_id
    project_ids = {i["project_id"] for i in items if i.get("project_id")}
    project_names: dict[str, str] = {}
    if project_ids and _DATABASE_URL:
        try:
            async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
                placeholders = ",".join(["%s"] * len(project_ids))
                rows = await conn.execute(
                    f"SELECT id, name FROM ovd_projects WHERE id IN ({placeholders})",
                    list(project_ids),
                )
                for row in await rows.fetchall():
                    project_names[row[0]] = row[1]
        except Exception:
            pass

    from datetime import datetime, timezone
    return [
        {
            "thread_id":      item["thread_id"],
            "session_id":     item["session_id"],
            "project_name":   project_names.get(item.get("project_id", ""), None),
            "feature_request": item["feature_request"],
            "sdd_summary":    item["sdd_summary"],
            "sdd":            item.get("sdd", {}),
            "created_at":     datetime.fromtimestamp(item["stored_at"], tz=timezone.utc).isoformat(),
            "revision_count": item.get("revision_count", 0),
        }
        for item in items
    ]


# ---------------------------------------------------------------------------
# Telemetría (S17.C) — métricas históricas para el panel de observabilidad
# ---------------------------------------------------------------------------

@router.get("/orgs/{org_id}/telemetry")
async def get_telemetry(
    org_id: str,
    days: int = Query(30, le=90),
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """
    S17.C — Datos de telemetría histórica para el dashboard de observabilidad.
    Retorna:
      - daily_qa: QA promedio diario + conteo de ciclos
      - daily_cost: costo diario acumulado
      - daily_tokens: tokens input/output diarios
      - agent_tokens: desglose de tokens por agente (suma de tokens_by_agent_json)
      - complexity_dist: distribución de ciclos por complejidad
      - security_dist: distribución por severity (none/low/medium/high)
    """
    _assert_org_access(current_user, org_id)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        # Trend diario: QA, costo, tokens
        daily_rows = await conn.execute(
            """
            SELECT
                DATE(time_created)              AS day,
                COUNT(*)                        AS cycle_count,
                COALESCE(AVG(qa_score), 0)      AS avg_qa,
                COALESCE(SUM(estimated_cost_usd), 0) AS cost_usd,
                COALESCE(SUM(tokens_input), 0)  AS tokens_in,
                COALESCE(SUM(tokens_output), 0) AS tokens_out
            FROM ovd_cycle_logs
            WHERE org_id = %s
              AND time_created >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY day
            ORDER BY day
            """,
            (org_id, days),
        )
        daily = await daily_rows.fetchall()

        # Tokens por agente: expandir tokens_by_agent_json (JSONB)
        agent_rows = await conn.execute(
            """
            SELECT
                agent_key,
                SUM((agent_val->>'input')::int)  AS tokens_in,
                SUM((agent_val->>'output')::int) AS tokens_out,
                COUNT(*)                         AS cycle_count
            FROM ovd_cycle_logs,
                 jsonb_each(tokens_by_agent_json) AS kv(agent_key, agent_val)
            WHERE org_id = %s
              AND time_created >= NOW() - (%s * INTERVAL '1 day')
              AND tokens_by_agent_json IS NOT NULL
              AND tokens_by_agent_json != 'null'::jsonb
            GROUP BY agent_key
            ORDER BY tokens_in + tokens_out DESC
            """,
            (org_id, days),
        )
        agents = await agent_rows.fetchall()

        # Distribución de complejidad
        complexity_rows = await conn.execute(
            """
            SELECT complexity, COUNT(*) AS cnt
            FROM ovd_cycle_logs
            WHERE org_id = %s
              AND time_created >= NOW() - (%s * INTERVAL '1 day')
              AND complexity IS NOT NULL
            GROUP BY complexity
            """,
            (org_id, days),
        )
        complexity = await complexity_rows.fetchall()

        # QA promedio período actual vs período anterior (para delta)
        delta_row = await conn.execute(
            """
            SELECT
                COALESCE(AVG(qa_score) FILTER (WHERE time_created >= NOW() - (%s * INTERVAL '1 day')), 0)         AS qa_current,
                COALESCE(AVG(qa_score) FILTER (WHERE time_created <  NOW() - (%s * INTERVAL '1 day')
                                                AND time_created >= NOW() - (%s * INTERVAL '1 day')), 0) AS qa_prev
            FROM ovd_cycle_logs
            WHERE org_id = %s
            """,
            (days, days, days * 2, org_id),
        )
        delta = await delta_row.fetchone()

    return {
        "period_days": days,
        "daily": [
            {
                "date":        str(r[0]),
                "cycle_count": r[1],
                "avg_qa":      round(float(r[2]), 1),
                "cost_usd":    round(float(r[3]), 5),
                "tokens_in":   int(r[4]),
                "tokens_out":  int(r[5]),
            }
            for r in daily
        ],
        "agent_tokens": [
            {
                "agent":       r[0],
                "tokens_in":   int(r[1]) if r[1] else 0,
                "tokens_out":  int(r[2]) if r[2] else 0,
                "cycle_count": int(r[3]),
            }
            for r in agents
        ],
        "complexity_dist": {r[0]: r[1] for r in complexity},
        "qa_delta": {
            "current": round(float(delta[0]), 1),
            "previous": round(float(delta[1]), 1),
            "diff": round(float(delta[0]) - float(delta[1]), 1),
        },
    }


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# PP-04 — Workspace Portability: export / import
# ---------------------------------------------------------------------------

_EXPORT_FORMAT_VERSION = "1.0"
_EXPORT_MAX_CYCLES     = 500


@router.get("/orgs/{org_id}/projects/{project_id}/export")
async def export_project(
    org_id: str,
    project_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """
    PP-04 — Exporta un proyecto como ZIP con:
      manifest.json  — metadatos del export
      project.json   — configuración del proyecto
      profile.json   — stack profile (si existe)
      cycles.jsonl   — hasta 500 ciclos más recientes (solo campos ligeros)
    """
    _assert_org_access(current_user, org_id)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        # Proyecto
        p_row = await conn.execute(
            """
            SELECT id, name, description, directory, active, time_created
            FROM ovd_projects WHERE id = %s AND org_id = %s
            """,
            (project_id, org_id),
        )
        p = await p_row.fetchone()
        if not p:
            raise HTTPException(404, detail="Proyecto no encontrado")

        project_data = {
            "id": p[0], "name": p[1], "description": p[2],
            "directory": p[3], "active": p[4],
            "created_at": p[5].isoformat() if p[5] else None,
        }

        # Stack profile
        prof_row = await conn.execute(
            """
            SELECT language, framework, db_engine, runtime, additional_stack,
                   legacy_stack, external_integrations, qa_tools, ci_cd,
                   constraints, code_style, project_description, team_size
            FROM ovd_project_profiles
            WHERE project_id = %s AND active = true
            ORDER BY time_created DESC LIMIT 1
            """,
            (project_id,),
        )
        prof = await prof_row.fetchone()
        profile_data = None
        if prof:
            profile_data = {
                "language": prof[0], "framework": prof[1], "db_engine": prof[2],
                "runtime": prof[3], "additional_stack": prof[4] or [],
                "legacy_stack": prof[5], "external_integrations": prof[6],
                "qa_tools": prof[7], "ci_cd": prof[8], "constraints": prof[9],
                "code_style": prof[10], "project_description": prof[11],
                "team_size": prof[12],
            }

        # Ciclos (campos ligeros — sin agent_results_json ni sdd_json)
        cyc_rows = await conn.execute(
            """
            SELECT id, session_id, feature_request, qa_score, complexity,
                   fr_type, tokens_total, estimated_cost_usd, time_created
            FROM ovd_cycle_logs
            WHERE project_id = %s AND org_id = %s
            ORDER BY time_created DESC
            LIMIT %s
            """,
            (project_id, org_id, _EXPORT_MAX_CYCLES),
        )
        cycles = await cyc_rows.fetchall()

    # Construir ZIP en memoria
    buf = io.BytesIO()
    now_str = datetime.now(timezone.utc).isoformat()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "format_version": _EXPORT_FORMAT_VERSION,
            "exported_at":    now_str,
            "org_id":         org_id,
            "project_id":     project_id,
            "project_name":   project_data["name"],
            "cycles_exported": len(cycles),
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("project.json",  json.dumps(project_data, ensure_ascii=False, indent=2))

        if profile_data:
            zf.writestr("profile.json", json.dumps(profile_data, ensure_ascii=False, indent=2))

        if cycles:
            lines = []
            for c in cycles:
                lines.append(json.dumps({
                    "id":              c[0],
                    "session_id":      c[1],
                    "feature_request": c[2],
                    "qa_score":        c[3],
                    "complexity":      c[4],
                    "fr_type":         c[5],
                    "tokens_total":    c[6],
                    "cost_usd":        float(c[7]) if c[7] else 0.0,
                    "created_at":      c[8].isoformat() if c[8] else None,
                }, ensure_ascii=False))
            zf.writestr("cycles.jsonl", "\n".join(lines))

    buf.seek(0)
    safe_name = project_data["name"].replace(" ", "_")[:32]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"ovd-export-{safe_name}-{ts}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/orgs/{org_id}/projects/import", status_code=status.HTTP_201_CREATED)
async def import_project(
    org_id: str,
    file: UploadFile = File(...),
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """
    PP-04 — Importa un proyecto desde un ZIP exportado por OVD.
    Restaura project.json y profile.json. Los ciclos (cycles.jsonl) se incluyen
    en el export como referencia pero no se reimportan (son registros históricos).
    Siempre crea un nuevo proyecto (nuevo ID) para evitar conflictos.
    """
    _assert_org_access(current_user, org_id)

    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, detail="Solo se aceptan archivos .zip")

    content = await file.read()
    try:
        buf = io.BytesIO(content)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            if "manifest.json" not in names or "project.json" not in names:
                raise HTTPException(400, detail="ZIP inválido: faltan manifest.json o project.json")

            manifest = json.loads(zf.read("manifest.json"))
            if manifest.get("format_version") != _EXPORT_FORMAT_VERSION:
                raise HTTPException(400, detail=f"Versión de export no soportada: {manifest.get('format_version')}")

            project = json.loads(zf.read("project.json"))
            profile = json.loads(zf.read("profile.json")) if "profile.json" in names else None

    except zipfile.BadZipFile:
        raise HTTPException(400, detail="Archivo ZIP corrupto o inválido")

    new_project_id = str(uuid.uuid4()).replace("-", "").upper()[:26]
    now = datetime.now(timezone.utc)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        await conn.execute(
            """
            INSERT INTO ovd_projects (id, org_id, name, description, directory, active, time_created, time_updated)
            VALUES (%s, %s, %s, %s, %s, true, %s, %s)
            """,
            (
                new_project_id, org_id,
                project.get("name", "Proyecto importado"),
                project.get("description", ""),
                project.get("directory", ""),
                now, now,
            ),
        )

        if profile:
            profile_id = str(uuid.uuid4()).replace("-", "").upper()[:26]
            additional = json.dumps(profile.get("additional_stack") or [])
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
                    profile_id, org_id, new_project_id,
                    profile.get("language"), profile.get("framework"), profile.get("db_engine"),
                    profile.get("runtime"), additional, profile.get("legacy_stack"),
                    profile.get("external_integrations"), profile.get("qa_tools"),
                    profile.get("ci_cd"), profile.get("constraints"), profile.get("code_style"),
                    profile.get("project_description"), profile.get("team_size"),
                    now, now,
                ),
            )

        await conn.commit()

    return {
        "id":            new_project_id,
        "name":          project.get("name"),
        "cycles_in_zip": manifest.get("cycles_exported", 0),
        "profile":       profile is not None,
    }


# PP-05 + PP-02 — Sesiones activas y colgadas para el Org Chart / Heartbeat
@router.get("/orgs/{org_id}/sessions/stale")
async def list_stale_sessions_endpoint(
    org_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """PP-02 — Lista sesiones detectadas como colgadas (elapsed > umbral)."""
    _assert_org_access(current_user, org_id)
    import sys, pathlib
    engine_dir = pathlib.Path(__file__).parent.parent
    if str(engine_dir) not in sys.path:
        sys.path.insert(0, str(engine_dir))
    from task_checkout import list_stale_sessions  # type: ignore
    return list_stale_sessions(org_id=org_id)


@router.get("/orgs/{org_id}/sessions/active")
async def list_active_sessions(
    org_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """PP-05 — Lista sesiones activas (en streaming) para el Org Chart."""
    _assert_org_access(current_user, org_id)
    import sys
    import pathlib
    engine_dir = pathlib.Path(__file__).parent.parent
    if str(engine_dir) not in sys.path:
        sys.path.insert(0, str(engine_dir))
    from task_checkout import list_active_sessions  # type: ignore
    return list_active_sessions(org_id=org_id)


# S17.A — Admin: gestión de usuarios del org
# ---------------------------------------------------------------------------

class UserRoleUpdate(BaseModel):
    role:   str | None = None    # admin | developer | viewer
    active: bool | None = None


@router.get("/orgs/{org_id}/users")
async def list_org_users(
    org_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """S17.A — Lista usuarios del org. Solo accesible con role=admin."""
    _assert_org_access(current_user, org_id)
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins pueden ver usuarios")

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        rows = await conn.execute(
            "SELECT id, email, role, active, created_at FROM ovd_users WHERE org_id = %s ORDER BY created_at",
            (org_id,),
        )
        users = await rows.fetchall()

    return [
        {
            "id":         r[0],
            "email":      r[1],
            "role":       r[2],
            "active":     r[3],
            "created_at": r[4].isoformat() if r[4] else None,
        }
        for r in users
    ]


@router.patch("/orgs/{org_id}/users/{user_id}", status_code=status.HTTP_200_OK)
async def update_org_user(
    org_id: str,
    user_id: str,
    body: UserRoleUpdate,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """S17.A — Cambia role o activa/desactiva un usuario. Solo admin."""
    _assert_org_access(current_user, org_id)
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins pueden modificar usuarios")
    if body.role and body.role not in ("admin", "developer", "viewer"):
        raise HTTPException(status_code=400, detail="role debe ser admin|developer|viewer")

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        if body.role is not None and body.active is not None:
            await conn.execute(
                "UPDATE ovd_users SET role=%s, active=%s WHERE id=%s AND org_id=%s",
                (body.role, body.active, user_id, org_id),
            )
        elif body.role is not None:
            await conn.execute(
                "UPDATE ovd_users SET role=%s WHERE id=%s AND org_id=%s",
                (body.role, user_id, org_id),
            )
        elif body.active is not None:
            await conn.execute(
                "UPDATE ovd_users SET active=%s WHERE id=%s AND org_id=%s",
                (body.active, user_id, org_id),
            )
        await conn.commit()

    return {"ok": True}


# ---------------------------------------------------------------------------
# S17.D — Knowledge Bootstrap UI
# ---------------------------------------------------------------------------

class KnowledgeIndexRequest(BaseModel):
    project_id: str
    source_path: str
    doc_type: str = "doc"   # codebase|doc|schema|contract|ticket|delivery


@router.get("/orgs/{org_id}/knowledge/status")
async def get_knowledge_status(
    org_id: str,
    project_id: str | None = Query(None),
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """S17.D — Estadísticas de chunks RAG indexados para el org/proyecto."""
    _assert_org_access(current_user, org_id)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        if project_id:
            collection_name = f"ovd_project_{project_id}"
            row = await conn.execute(
                """
                SELECT COUNT(e.id)
                FROM langchain_pg_collection c
                JOIN langchain_pg_embedding e ON e.collection_id = c.uuid
                WHERE c.name = %s
                """,
                (collection_name,),
            )
        else:
            row = await conn.execute(
                """
                SELECT COUNT(e.id)
                FROM langchain_pg_collection c
                JOIN langchain_pg_embedding e ON e.collection_id = c.uuid
                WHERE c.name LIKE 'ovd_project_%%'
                """,
            )
        total = (await row.fetchone())[0]

        # Desglose por proyecto/colección
        breakdown_rows = await conn.execute(
            """
            SELECT c.name, COUNT(e.id) AS chunks
            FROM langchain_pg_collection c
            JOIN langchain_pg_embedding e ON e.collection_id = c.uuid
            WHERE c.name LIKE 'ovd_project_%%'
            GROUP BY c.name
            ORDER BY chunks DESC
            """,
        )
        breakdown = await breakdown_rows.fetchall()

    return {
        "total_chunks": int(total),
        "by_project": [
            {"collection": r[0], "chunks": int(r[1])}
            for r in breakdown
        ],
    }


@router.post("/orgs/{org_id}/knowledge/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_knowledge_index(
    org_id: str,
    body: KnowledgeIndexRequest,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """S17.D — Lanza el bootstrap RAG en background para una ruta dada."""
    _assert_org_access(current_user, org_id)

    import asyncio
    import sys
    import pathlib

    knowledge_dir = pathlib.Path(__file__).parent.parent.parent.parent / "knowledge"
    if str(knowledge_dir) not in sys.path:
        sys.path.insert(0, str(knowledge_dir))

    try:
        from knowledge import bootstrap  # type: ignore
    except ImportError:
        knowledge_dir2 = pathlib.Path(__file__).parent.parent.parent / "knowledge"
        if str(knowledge_dir2) not in sys.path:
            sys.path.insert(0, str(knowledge_dir2))
        import importlib
        bootstrap = importlib.import_module("knowledge.bootstrap")

    async def _run():
        result = await bootstrap.run(
            org_id=org_id,
            project_id=body.project_id,
            source_path=body.source_path,
            doc_type=body.doc_type,
        )
        import logging
        logging.getLogger("ovd.api").info("knowledge.index done: %s", result.summary())

    asyncio.create_task(_run())

    return {"status": "indexing_started", "project_id": body.project_id, "source_path": body.source_path}


# ---------------------------------------------------------------------------
# S17.B — Model Dashboard: estado del dataset de fine-tuning
# ---------------------------------------------------------------------------

@router.get("/orgs/{org_id}/model/status")
async def get_model_status(
    org_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """S17.B — Estadísticas del dataset para fine-tuning del modelo propio."""
    _assert_org_access(current_user, org_id)

    M1_GOAL = 500  # ciclos de calidad para hito M1

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        totals_row = await conn.execute(
            """
            SELECT
                COUNT(*)                                          AS total_cycles,
                COUNT(*) FILTER (WHERE qa_score >= 70)           AS training_ready,
                COUNT(*) FILTER (WHERE qa_score >= 80)           AS high_quality,
                COALESCE(AVG(qa_score), 0)                       AS avg_qa
            FROM ovd_cycle_logs
            WHERE org_id = %s
            """,
            (org_id,),
        )
        totals = await totals_row.fetchone()

        by_project_rows = await conn.execute(
            """
            SELECT
                p.name,
                COUNT(c.id)                                       AS total,
                COUNT(c.id) FILTER (WHERE c.qa_score >= 70)      AS training_ready
            FROM ovd_cycle_logs c
            LEFT JOIN ovd_projects p ON p.id = c.project_id
            WHERE c.org_id = %s
            GROUP BY p.name
            ORDER BY training_ready DESC
            LIMIT 10
            """,
            (org_id,),
        )
        by_project = await by_project_rows.fetchall()

    training_ready = int(totals[1]) if totals[1] else 0
    return {
        "total_cycles":    int(totals[0]) if totals[0] else 0,
        "training_ready":  training_ready,
        "high_quality":    int(totals[2]) if totals[2] else 0,
        "avg_qa_score":    round(float(totals[3]), 1),
        "m1_goal":         M1_GOAL,
        "m1_progress_pct": round(min(training_ready / M1_GOAL * 100, 100), 1),
        "by_project": [
            {"project": r[0] or "Sin nombre", "total": int(r[1]), "training_ready": int(r[2])}
            for r in by_project
        ],
    }


# ---------------------------------------------------------------------------
# S11.H — Fuentes curadas por workspace
# ---------------------------------------------------------------------------

class WebSourceCreate(BaseModel):
    url:   str
    label: str = ""


@router.get("/orgs/{org_id}/projects/{project_id}/web-sources")
async def list_web_sources(
    org_id: str,
    project_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """S11.H — Lista URLs curadas activas del proyecto."""
    _assert_org_access(current_user, org_id)
    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        rows = await conn.execute(
            """
            SELECT id, url, label, created_at
            FROM ovd_web_sources
            WHERE org_id = %s AND project_id = %s AND active = TRUE
            ORDER BY created_at
            """,
            (org_id, project_id),
        )
        records = await rows.fetchall()
    return [
        {"id": r[0], "url": r[1], "label": r[2], "created_at": r[3].isoformat() if r[3] else None}
        for r in records
    ]


@router.post("/orgs/{org_id}/projects/{project_id}/web-sources", status_code=status.HTTP_201_CREATED)
async def add_web_source(
    org_id: str,
    project_id: str,
    body: WebSourceCreate,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """S11.H — Agrega una URL curada al proyecto."""
    _assert_org_access(current_user, org_id)
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="La URL debe comenzar con http:// o https://")

    new_id = str(uuid.uuid4())
    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        try:
            await conn.execute(
                """
                INSERT INTO ovd_web_sources (id, org_id, project_id, url, label)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (new_id, org_id, project_id, body.url.strip(), body.label.strip()),
            )
            await conn.commit()
        except Exception as exc:
            if "idx_ovd_web_sources_uniq" in str(exc):
                raise HTTPException(status_code=409, detail="Esa URL ya existe en este proyecto")
            raise

    return {"id": new_id, "url": body.url.strip(), "label": body.label.strip()}


@router.delete("/orgs/{org_id}/projects/{project_id}/web-sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_web_source(
    org_id: str,
    project_id: str,
    source_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """S11.H — Desactiva una URL curada (soft delete)."""
    _assert_org_access(current_user, org_id)
    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        result = await conn.execute(
            "UPDATE ovd_web_sources SET active = FALSE WHERE id = %s AND org_id = %s AND project_id = %s",
            (source_id, org_id, project_id),
        )
        await conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Fuente no encontrada")


# ---------------------------------------------------------------------------
# Admin: Skills externos (ui-ux-pro-max + superpowers)
# ---------------------------------------------------------------------------

# Estado del último job de actualización (en memoria; se reinicia con el proceso)
_skills_job: dict = {"status": "idle", "output": "", "updated_at": None}

_VALID_TARGETS = {"ui-ux", "superpowers", "all"}


class SkillsUpdateRequest(BaseModel):
    target: str = "all"   # ui-ux | superpowers | all


@router.post("/orgs/{org_id}/admin/skills/update", status_code=status.HTTP_202_ACCEPTED)
async def update_skills(
    org_id: str,
    body: SkillsUpdateRequest,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """Ejecuta update-skills.sh en background. Solo admin."""
    _assert_org_access(current_user, org_id)
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins pueden actualizar skills")
    if body.target not in _VALID_TARGETS:
        raise HTTPException(status_code=400, detail=f"target debe ser: {', '.join(sorted(_VALID_TARGETS))}")

    if _skills_job["status"] == "running":
        raise HTTPException(status_code=409, detail="Ya hay una actualización en curso")

    import asyncio
    import pathlib

    script_path = pathlib.Path(__file__).parent.parent.parent.parent / "scripts" / "update-skills.sh"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Script no encontrado: {script_path}")

    _skills_job["status"] = "running"
    _skills_job["output"] = ""
    _skills_job["updated_at"] = datetime.now(timezone.utc).isoformat()

    async def _run():
        env = {"TARGET": body.target, "PATH": os.environ.get("PATH", "")}
        proc = await asyncio.create_subprocess_exec(
            "bash", str(script_path),
            env={**os.environ, **env},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        _skills_job["status"] = "done" if proc.returncode == 0 else "error"
        _skills_job["output"] = output
        _skills_job["updated_at"] = datetime.now(timezone.utc).isoformat()

    asyncio.create_task(_run())

    return {"status": "accepted", "target": body.target}


@router.get("/orgs/{org_id}/admin/skills/status")
async def get_skills_status(
    org_id: str,
    current_user: AccessTokenPayload = Depends(inject_current_user),
):
    """Retorna el estado del último job de actualización de skills. Solo admin."""
    _assert_org_access(current_user, org_id)
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins pueden ver el estado de skills")

    return {
        "status":     _skills_job["status"],
        "output":     _skills_job["output"],
        "updated_at": _skills_job["updated_at"],
    }
