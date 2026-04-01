"""
OVD Platform — Oracle MCP Server
Copyright 2026 Omar Robles

Servidor MCP stdio que expone herramientas Oracle multi-sede.
Cada tool valida credenciales, ejecuta en el pool correcto,
y reporta trazas a OpenTelemetry.

Uso:
    python server.py           # modo stdio (MCP standard)
    python server.py --health  # health check y salir
"""
from __future__ import annotations
import asyncio
import os
import sys
import json
import atexit
from typing import Literal, Annotated
from dotenv import load_dotenv

load_dotenv(".env.local", override=False)

import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult, ListToolsResult

from connections import get_pool, close_all, Sede
from compat import validate as validate_compat

# ---------------------------------------------------------------------------
# OpenTelemetry (opcional — solo si OTEL_ENABLED=true)
# ---------------------------------------------------------------------------

_tracer = None

def _init_otel():
    global _tracer
    if os.environ.get("OTEL_ENABLED", "false").lower() != "true":
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider = TracerProvider()
        exporter = OTLPSpanExporter(
            endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318") + "/v1/traces"
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("mcp-oracle-ovd")
    except Exception as e:
        print(f"OTEL init warning: {e}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

app = Server("oracle-ovd")

SEDES: list[Sede] = ["CAS", "CAT", "CAV"]
SEDE_VERSIONS = {"CAS": "Oracle 12c", "CAT": "Oracle 19c", "CAV": "Oracle 19c"}


@app.list_tools()
async def list_tools() -> ListToolsResult:
    return [
        Tool(
            name="query_oracle",
            description=(
                "Ejecuta una query SQL de solo lectura en la sede Oracle especificada. "
                "CAS = Casa Matriz (Oracle 12c), CAT = Catedral (19c), CAV = Cavour (19c). "
                "Solo SELECT — no ejecuta DDL/DML sin confirmacion explicita."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "Query SQL a ejecutar (SELECT recomendado)"},
                    "sede": {"type": "string", "enum": SEDES, "description": "Sede Oracle destino"},
                    "max_rows": {"type": "integer", "default": 100, "description": "Maximo de filas a retornar"},
                },
                "required": ["sql", "sede"],
            },
        ),
        Tool(
            name="validate_sql_compat",
            description=(
                "Valida si una query SQL es compatible con la version Oracle de la sede objetivo. "
                "Util antes de ejecutar en produccion o migrar queries entre sedes. "
                "Retorna valid:bool, issues[] y warnings[]."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL a validar"},
                    "target_sede": {"type": "string", "enum": SEDES, "description": "Sede objetivo"},
                },
                "required": ["sql", "target_sede"],
            },
        ),
        Tool(
            name="describe_schema",
            description=(
                "Lista tablas y columnas que coincidan con el patron en la sede especificada. "
                "Util para explorar el schema antes de escribir queries."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "table_pattern": {
                        "type": "string",
                        "description": "Patron SQL LIKE para filtrar tablas (ej: 'PAC%' para tablas de pacientes)",
                        "default": "%",
                    },
                    "sede": {"type": "string", "enum": SEDES, "description": "Sede Oracle a inspeccionar"},
                    "include_columns": {
                        "type": "boolean",
                        "default": True,
                        "description": "Incluir detalle de columnas",
                    },
                },
                "required": ["sede"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    span = None
    if _tracer:
        span = _tracer.start_span(f"oracle.{name}")

    try:
        if name == "query_oracle":
            return await _query_oracle(**arguments)
        elif name == "validate_sql_compat":
            return await _validate_sql_compat(**arguments)
        elif name == "describe_schema":
            return await _describe_schema(**arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Tool desconocida: {name}")],
                isError=True,
            )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )
    finally:
        if span:
            span.end()


async def _query_oracle(sql: str, sede: str, max_rows: int = 100) -> CallToolResult:
    sede = sede.upper()
    if sede not in SEDES:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Sede invalida: {sede}")],
            isError=True,
        )

    # Advertencia de seguridad para DDL/DML
    sql_upper = sql.strip().upper()
    dangerous = any(sql_upper.startswith(k) for k in ("DROP", "TRUNCATE", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"))
    if dangerous:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=(
                    f"ADVERTENCIA: La query contiene una operacion de modificacion de datos ({sql_upper.split()[0]}). "
                    "Este MCP esta configurado para consultas de solo lectura en modo desarrollo. "
                    "Para ejecutar DDL/DML en produccion, coordinar con el DBA del equipo."
                )
            )],
            isError=True,
        )

    pool = get_pool(sede)  # type: ignore

    def _run_sync():
        with pool.acquire() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                cols = [col[0] for col in cursor.description] if cursor.description else []
                rows = cursor.fetchmany(max_rows)
                return cols, rows

    cols, rows = await asyncio.get_event_loop().run_in_executor(None, _run_sync)

    result = {
        "sede": sede,
        "version": SEDE_VERSIONS[sede],
        "columns": cols,
        "rows": [dict(zip(cols, row)) for row in rows],
        "row_count": len(rows),
        "truncated": len(rows) == max_rows,
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(result, default=str, ensure_ascii=False, indent=2))]
    )


async def _validate_sql_compat(sql: str, target_sede: str) -> CallToolResult:
    result = validate_compat(sql, target_sede)
    output = {
        "valid": result.valid,
        "target_sede": target_sede.upper(),
        "target_version": result.target_version,
        "issues": result.issues,
        "warnings": result.warnings,
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(output, ensure_ascii=False, indent=2))]
    )


async def _describe_schema(
    sede: str,
    table_pattern: str = "%",
    include_columns: bool = True,
) -> CallToolResult:
    sede = sede.upper()
    if sede not in SEDES:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Sede invalida: {sede}")],
            isError=True,
        )

    pool = get_pool(sede)  # type: ignore

    def _run_sync():
        with pool.acquire() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name, num_rows, last_analyzed
                    FROM user_tables
                    WHERE table_name LIKE :pattern
                    ORDER BY table_name
                    """,
                    {"pattern": table_pattern.upper()},
                )
                tables = [
                    {"table": r[0], "num_rows": r[1], "last_analyzed": str(r[2])}
                    for r in cursor.fetchall()
                ]

                if include_columns and tables:
                    for tbl in tables:
                        cursor.execute(
                            """
                            SELECT column_name, data_type, data_length,
                                   nullable, data_default
                            FROM user_tab_columns
                            WHERE table_name = :tname
                            ORDER BY column_id
                            """,
                            {"tname": tbl["table"]},
                        )
                        tbl["columns"] = [
                            {
                                "name": r[0],
                                "type": r[1],
                                "length": r[2],
                                "nullable": r[3] == "Y",
                                "default": r[4],
                            }
                            for r in cursor.fetchall()
                        ]
                return tables

    tables = await asyncio.get_event_loop().run_in_executor(None, _run_sync)
    result = {
        "sede": sede,
        "version": SEDE_VERSIONS[sede],
        "pattern": table_pattern,
        "tables": tables,
        "table_count": len(tables),
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(result, default=str, ensure_ascii=False, indent=2))]
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--health" in sys.argv:
        # Health check rapido: verificar que el servidor inicia
        print(json.dumps({"status": "ok", "server": "oracle-ovd"}))
        sys.exit(0)

    _init_otel()
    atexit.register(close_all)

    asyncio.run(mcp.server.stdio.stdio_server(app))
