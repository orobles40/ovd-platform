"""
OVD Platform — MCP NATS
Copyright 2026 Omar Robles

Servidor MCP (stdio) que permite publicar y suscribirse a eventos
en el bus NATS de Omar Robles.

Subjects de OVD:
  ovd.{org_id}.session.started      — nueva sesion OVD iniciada
  ovd.{org_id}.session.approved     — SDD aprobado por el arquitecto
  ovd.{org_id}.session.done         — ciclo completado con entregables
  ovd.{org_id}.session.escalated    — sesion escalada
  ovd.{org_id}.session.error        — error no recuperable

Tools:
  nats_publish    — publica un mensaje en un subject NATS
  nats_request    — envia request y espera respuesta (req-reply)
  nats_history    — obtiene mensajes recientes de un stream JetStream
"""
import asyncio
import json
import os
from typing import Any

import nats
from nats.errors import ConnectionClosedError, TimeoutError as NatsTimeout
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# Conexion NATS
# ---------------------------------------------------------------------------

NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
NATS_CREDS = os.environ.get("NATS_CREDS_FILE")  # archivo .creds para auth

_nc: nats.NATS | None = None
_js: Any = None  # JetStream context


async def get_connection() -> nats.NATS:
    global _nc
    if _nc and _nc.is_connected:
        return _nc
    kwargs: dict = {"servers": [NATS_URL]}
    if NATS_CREDS:
        kwargs["credentials"] = NATS_CREDS
    _nc = await nats.connect(**kwargs)
    return _nc


async def get_jetstream() -> Any:
    global _js
    nc = await get_connection()
    if _js is None:
        _js = nc.jetstream()
    return _js


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("ovd-nats")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="nats_publish",
            description=(
                "Publica un mensaje JSON en un subject NATS. "
                "Util para notificar eventos de ciclos OVD a otros servicios. "
                "Subject debe seguir el formato: ovd.{org_id}.session.{evento}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Subject NATS, ej: ovd.alemana.session.done",
                    },
                    "payload": {
                        "type": "object",
                        "description": "Payload JSON a publicar",
                    },
                    "headers": {
                        "type": "object",
                        "description": "Headers NATS opcionales (key-value string)",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["subject", "payload"],
            },
        ),
        Tool(
            name="nats_request",
            description=(
                "Envia un request NATS y espera respuesta (patron req-reply). "
                "Timeout de 5 segundos por defecto."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Subject del servicio a consultar",
                    },
                    "payload": {
                        "type": "object",
                        "description": "Payload JSON de la peticion",
                    },
                    "timeout_secs": {
                        "type": "number",
                        "description": "Timeout en segundos (default: 5)",
                    },
                },
                "required": ["subject", "payload"],
            },
        ),
        Tool(
            name="nats_history",
            description=(
                "Obtiene los ultimos mensajes de un stream JetStream. "
                "Util para ver el historial de eventos de un ciclo OVD."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "stream": {
                        "type": "string",
                        "description": "Nombre del stream JetStream",
                    },
                    "subject_filter": {
                        "type": "string",
                        "description": "Filtro de subject (puede contener wildcards)",
                    },
                    "last_n": {
                        "type": "integer",
                        "description": "Cuantos mensajes recientes obtener (max 50)",
                        "default": 10,
                    },
                },
                "required": ["stream"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "nats_publish":
        return await _publish(arguments)
    if name == "nats_request":
        return await _request(arguments)
    if name == "nats_history":
        return await _history(arguments)
    raise ValueError(f"Tool desconocida: {name}")


async def _publish(args: dict) -> list[TextContent]:
    subject = args["subject"]
    payload = args["payload"]
    headers_raw: dict = args.get("headers", {})

    # Validacion basica de subject OVD
    if not subject.startswith("ovd."):
        return [TextContent(
            type="text",
            text=json.dumps({"ok": False, "error": "Solo se permiten subjects que empiecen con 'ovd.'"}),
        )]

    try:
        nc = await get_connection()
        data = json.dumps(payload).encode()

        headers = None
        if headers_raw:
            import nats.aio.msg
            headers = {k: v for k, v in headers_raw.items()}

        await nc.publish(subject, data, headers=headers)
        return [TextContent(
            type="text",
            text=json.dumps({"ok": True, "subject": subject, "bytes": len(data)}),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"ok": False, "error": str(e)}),
        )]


async def _request(args: dict) -> list[TextContent]:
    subject = args["subject"]
    payload = args["payload"]
    timeout = float(args.get("timeout_secs", 5))

    try:
        nc = await get_connection()
        data = json.dumps(payload).encode()
        msg = await nc.request(subject, data, timeout=timeout)
        response = json.loads(msg.data.decode())
        return [TextContent(
            type="text",
            text=json.dumps({"ok": True, "subject": subject, "response": response}),
        )]
    except NatsTimeout:
        return [TextContent(
            type="text",
            text=json.dumps({"ok": False, "error": f"Timeout ({timeout}s) esperando respuesta de {subject}"}),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"ok": False, "error": str(e)}),
        )]


async def _history(args: dict) -> list[TextContent]:
    stream_name = args["stream"]
    subject_filter = args.get("subject_filter")
    last_n = min(int(args.get("last_n", 10)), 50)

    try:
        js = await get_jetstream()
        # Obtener el stream
        stream = await js.find_stream_name_by_subject(subject_filter or f"{stream_name}.>")
        # Consumir los ultimos N mensajes
        msgs = []
        sub = await js.subscribe(
            subject_filter or f"{stream_name}.>",
            config=nats.js.api.ConsumerConfig(
                deliver_policy=nats.js.api.DeliverPolicy.LAST_N,
                opt_start_seq=None,
                num_replicas=None,
                max_deliver=last_n,
            ),
        )
        try:
            for _ in range(last_n):
                try:
                    msg = await asyncio.wait_for(sub.next_msg(), timeout=1.0)
                    msgs.append({
                        "subject": msg.subject,
                        "data": json.loads(msg.data.decode()),
                        "headers": dict(msg.headers) if msg.headers else {},
                    })
                    await msg.ack()
                except asyncio.TimeoutError:
                    break
        finally:
            await sub.unsubscribe()

        return [TextContent(
            type="text",
            text=json.dumps({"ok": True, "stream": stream_name, "messages": msgs}),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"ok": False, "error": str(e)}),
        )]


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
