"""
OVD Platform — MCP → LangChain tool adapter
Copyright 2026 Omar Robles

Convierte definiciones de tools MCP (con JSON Schema) en LangChain StructuredTool,
para que bind_tools() las acepte igual que las file tools existentes.

Soporte de tipos JSON Schema → Python:
  string  → str
  integer → int
  number  → float
  boolean → bool
  array   → list
  (otros) → str  (fallback seguro)
"""
from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.tools import StructuredTool
from pydantic import create_model, Field


# ---------------------------------------------------------------------------
# Conversión de tipos JSON Schema → Python
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[str, type] = {
    "string":  str,
    "integer": int,
    "number":  float,
    "boolean": bool,
    "array":   list,
    "object":  dict,
}


def _json_type_to_python(json_type: str | None) -> type:
    return _TYPE_MAP.get(json_type or "string", str)


def _build_pydantic_model(tool_name: str, input_schema: dict) -> type:
    """
    Construye un modelo Pydantic dinámico desde un JSON Schema simple.
    Solo soporta el nivel `properties` (sin $ref, sin allOf, etc.) —
    suficiente para las tools de context7.
    """
    properties: dict = input_schema.get("properties") or {}
    required: set[str] = set(input_schema.get("required") or [])

    fields: dict[str, Any] = {}
    for prop_name, prop_def in properties.items():
        py_type = _json_type_to_python(prop_def.get("type"))
        description = prop_def.get("description", "")
        if prop_name in required:
            fields[prop_name] = (py_type, Field(..., description=description))
        else:
            fields[prop_name] = (Optional[py_type], Field(None, description=description))

    # Si el schema no tiene propiedades definidas, crear modelo vacío
    if not fields:
        fields["input"] = (str, Field(..., description="Argumento de la herramienta"))

    safe_name = tool_name.replace("-", "_").replace(".", "_")
    return create_model(f"MCPInput_{safe_name}", **fields)


# ---------------------------------------------------------------------------
# Fábrica principal
# ---------------------------------------------------------------------------

def make_mcp_tool(session: Any, tool_def: Any) -> StructuredTool:
    """
    Crea un LangChain StructuredTool que delega en session.call_tool().

    Parámetros:
        session   — ClientSession MCP activa
        tool_def  — objeto Tool retornado por session.list_tools()
    """
    tool_name = tool_def.name
    tool_desc = getattr(tool_def, "description", "") or f"Tool MCP: {tool_name}"
    input_schema: dict = {}

    raw_schema = getattr(tool_def, "inputSchema", None)
    if raw_schema is not None:
        if isinstance(raw_schema, dict):
            input_schema = raw_schema
        else:
            # Puede venir como objeto Pydantic con model_dump()
            try:
                input_schema = raw_schema.model_dump()
            except AttributeError:
                input_schema = {}

    pydantic_model = _build_pydantic_model(tool_name, input_schema)

    async def _call(**kwargs: Any) -> str:
        """Invoca la tool MCP y retorna el texto de la respuesta."""
        try:
            result = await session.call_tool(tool_name, arguments=kwargs)
            # result.content es lista de bloques (TextContent, ImageContent, etc.)
            parts: list[str] = []
            for block in (result.content or []):
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                else:
                    parts.append(str(block))
            return "\n".join(parts) if parts else "(sin respuesta)"
        except Exception as exc:
            return f"[MCP error en {tool_name}]: {exc}"

    return StructuredTool(
        name=tool_name,
        description=tool_desc,
        args_schema=pydantic_model,
        coroutine=_call,
        handle_tool_error=True,
    )
