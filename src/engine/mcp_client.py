"""
OVD Platform — MCP Client Pool
Copyright 2026 Omar Robles

Gestiona conexiones persistentes a servidores MCP externos durante el ciclo de vida
del engine. Expone sus tools como herramientas LangChain-compatibles para bind_tools().

Servidores configurados (Fase A):
  context7 — documentación actualizada de librerías vía npx @upstash/context7-mcp

Uso en api.py lifespan:
    await mcp_pool.start()
    yield
    await mcp_pool.stop()

Uso en graph.py agent_executor:
    tools = make_file_tools(directory) + mcp_pool.get_langchain_tools(agent_name)
"""
from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack
from typing import Any

log = logging.getLogger("ovd.mcp")

# Agentes que reciben tools de context7
_CONTEXT7_AGENTS = {"backend", "frontend", "database", "devops"}


class MCPClientPool:
    """Pool singleton de sesiones MCP. Ciclo de vida gestionado por lifespan."""

    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._sessions: dict[str, Any] = {}       # nombre → ClientSession
        self._lc_tools: dict[str, list] = {}       # nombre → [LangChain tools]
        self.available: bool = False

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Intenta conectar a todos los servidores MCP configurados."""
        await self._stack.__aenter__()
        await self._connect_context7()
        self.available = bool(self._sessions)
        if self.available:
            log.info("MCP pool iniciado: %s", list(self._sessions.keys()))
        else:
            log.warning("MCP pool: ningún servidor disponible — agentes funcionarán sin MCP tools")

    async def stop(self) -> None:
        """Cierra todas las sesiones MCP."""
        try:
            await self._stack.aclose()
        except Exception as exc:
            log.warning("MCP pool stop error: %s", exc)
        self._sessions.clear()
        self._lc_tools.clear()
        self.available = False
        log.info("MCP pool cerrado")

    # ------------------------------------------------------------------
    # Interfaz para graph.py
    # ------------------------------------------------------------------

    def get_langchain_tools(self, agent_name: str) -> list:
        """Retorna lista de LangChain tools para el agente dado."""
        if not self.available:
            return []
        tools: list = []
        if agent_name in _CONTEXT7_AGENTS:
            tools.extend(self._lc_tools.get("context7", []))
        return tools

    # ------------------------------------------------------------------
    # Conexión a context7
    # ------------------------------------------------------------------

    async def _connect_context7(self) -> None:
        """Lanza context7 como subproceso stdio y registra sus tools."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client, StdioServerParameters
        except ImportError:
            log.warning("MCP context7: librería 'mcp' no instalada — ejecutar: uv add mcp")
            return

        # Verificar que npx esté disponible
        npx_path = _find_npx()
        if not npx_path:
            log.warning("MCP context7: 'npx' no encontrado en PATH — instalar Node.js")
            return

        params = StdioServerParameters(
            command=npx_path,
            args=["-y", "@upstash/context7-mcp@latest"],
            env={**os.environ},
        )

        try:
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session: ClientSession = await self._stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self._sessions["context7"] = session

            result = await session.list_tools()
            self._lc_tools["context7"] = _build_langchain_tools(session, result.tools)
            log.info(
                "MCP context7: conectado — %d tools disponibles: %s",
                len(result.tools),
                [t.name for t in result.tools],
            )
        except Exception as exc:
            log.warning("MCP context7: no disponible (%s) — agentes funcionarán sin context7", exc)


# ------------------------------------------------------------------
# Singleton global
# ------------------------------------------------------------------

pool = MCPClientPool()


# ------------------------------------------------------------------
# Helpers internos
# ------------------------------------------------------------------

def _find_npx() -> str | None:
    """Busca npx en PATH."""
    import shutil
    return shutil.which("npx")


def _build_langchain_tools(session: Any, tool_defs: list) -> list:
    """Convierte definiciones MCP a LangChain StructuredTool."""
    from tools.mcp_tools import make_mcp_tool
    lc_tools = []
    for td in tool_defs:
        try:
            lc_tools.append(make_mcp_tool(session, td))
        except Exception as exc:
            log.warning("MCP tool %s: no convertido (%s)", td.name, exc)
    return lc_tools
