"""
OVD Platform — Context Resolver (Sprint 8 — GAP-A3, Sprint 9 — GAP-A4)
Copyright 2026 Omar Robles

Construye un AgentContext tipado antes de que el request llegue al route handler.

Problema que resuelve:
    Antes de S8, la lógica de resolución de contexto (cargar project profile,
    construir prompt context) estaba embebida en el route handler como texto libre.
    El Engine recibía project_context: str — imposible de consultar programáticamente.

    Antes de S9, las credenciales de workspaces estaban en .env.local.
    Ahora se recuperan en runtime desde Infisical via SecretsAdapter.

Solución:
    1. El Bridge envía el profile serializado como JSON en project_context (campo existente).
    2. ContextResolver parsea ese JSON y construye un AgentContext estructurado.
    3. Si el profile incluye db_engine + db_version pero no db_restrictions, el resolver
       genera las restricciones automáticamente desde la tabla RESTRICTION_RULES.
    4. El model_routing se resuelve aplicando la regla: legacy_stack → claude, auto → ollama.
    5. Si el profile tiene secret_ref, se recuperan las credenciales desde Infisical (S9).
       Las credenciales se inyectan en AgentContext.workspace_credentials (NO en el prompt).

Uso desde api.py:
    from context_resolver import ContextResolver, AgentContext

    ctx: AgentContext = await ContextResolver.resolve_async(body)
    # ctx.restrictions inyectadas en system prompts de todos los agentes
    # ctx.model_routing pasado a model_router.py
    # ctx.workspace_credentials usadas por agentes MCP (Oracle, etc.)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from secrets_adapter import SecretsAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

ModelRouting = Literal["auto", "ollama", "claude", "openai"]


@dataclass
class StackRegistry:
    """Perfil tecnológico estructurado del workspace."""
    language: str = ""
    framework: str = ""
    db_engine: str = ""
    db_version: str = ""
    runtime: str = ""
    additional_stack: list[str] = field(default_factory=list)
    legacy_stack: str = ""
    model_routing: ModelRouting = "auto"
    db_restrictions: list[str] = field(default_factory=list)
    constraints: str = ""
    code_style: str = ""
    project_description: str = ""
    secret_ref: str = ""             # Sprint 9: identificador en Infisical


@dataclass
class AgentContext:
    """Contexto tipado que se inyecta en todos los nodos del grafo."""
    org_id: str
    project_id: str
    stack: StackRegistry
    model_routing: ModelRouting      # routing efectivo (resuelto, no el campo raw)
    restrictions: list[str]          # restricciones activas para inyectar en prompts
    rag_context: str                 # contexto semántico pre-recuperado del RAG
    language: str = "es"
    # Sprint 9 — GAP-A4: credenciales del workspace desde Infisical
    # NUNCA incluir en to_prompt_block() ni en logs
    workspace_credentials: dict[str, str] = field(default_factory=dict)
    secret_ref: str = ""             # identificador usado para recuperar los secrets

    def to_prompt_block(self) -> str:
        """
        Genera el bloque de contexto para inyectar en system prompts.
        Reemplaza el campo project_context: str de sprint anteriores.
        """
        lines: list[str] = []

        if self.stack.project_description:
            lines.append(f"# Proyecto\n{self.stack.project_description}")

        # Stack tecnológico
        stack_parts: list[str] = []
        if self.stack.language:
            stack_parts.append(f"Lenguaje: {self.stack.language}")
        if self.stack.framework:
            stack_parts.append(f"Framework: {self.stack.framework}")
        if self.stack.runtime:
            stack_parts.append(f"Runtime: {self.stack.runtime}")
        if self.stack.db_engine:
            db_str = self.stack.db_engine
            if self.stack.db_version:
                db_str += f" {self.stack.db_version}"
            stack_parts.append(f"Base de datos: {db_str}")
        if self.stack.additional_stack:
            stack_parts.append(f"Stack adicional: {', '.join(self.stack.additional_stack)}")
        if self.stack.legacy_stack:
            stack_parts.append(f"Sistema legacy: {self.stack.legacy_stack}")

        if stack_parts:
            lines.append("# Stack tecnológico\n" + "\n".join(stack_parts))

        # Restricciones activas — bloque crítico para agentes SQL/code
        if self.restrictions:
            restriction_text = "\n".join(f"- {r}" for r in self.restrictions)
            lines.append(
                f"# Restricciones del stack (OBLIGATORIO respetar)\n{restriction_text}"
            )

        # Convenciones
        if self.stack.code_style:
            lines.append(f"# Estilo de código\n{self.stack.code_style}")
        if self.stack.constraints:
            lines.append(f"# Restricciones del proyecto\n{self.stack.constraints}")

        # Contexto RAG
        if self.rag_context:
            lines.append(f"# Contexto relevante (RAG)\n{self.rag_context}")

        return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Tabla de restricciones por motor + versión
# Fuente: documentación oficial de cada BD.
# Extendible: agregar nuevas entradas sin cambiar la lógica.
# ---------------------------------------------------------------------------

RESTRICTION_RULES: dict[tuple[str, str], list[str]] = {
    ("oracle", "11g"):  [
        "no_json_functions",
        "no_lateral_join",
        "no_fetch_first",
        "no_listagg_overflow",
        "no_with_function",
        "no_result_cache",
        "no_pivot",
        "no_pattern_matching",
        "use_rownum_instead_of_fetch",
    ],
    ("oracle", "11.2"): [
        "no_json_functions",
        "no_lateral_join",
        "no_fetch_first",
        "no_listagg_overflow",
        "no_with_function",
        "no_result_cache",
        "no_pivot",
        "use_rownum_instead_of_fetch",
    ],
    ("oracle", "12c"):  [
        "no_json_functions",      # JSON_TABLE, JSON_VALUE no disponibles
        "no_lateral_join",        # LATERAL keyword no disponible en 12c estándar
        "no_fetch_first",         # FETCH FIRST ... ROWS solo en 12c R1+, evitar por compatibilidad
        "no_listagg_overflow",    # LISTAGG ON OVERFLOW solo en 12c R2+
        "no_with_function",       # WITH FUNCTION solo en 18c+
    ],
    ("oracle", "12.2"): [
        "no_json_table_extended", # JSON_TABLE disponible pero sin sintaxis extendida
        "no_with_function",
    ],
    ("oracle", "19c"):  [],  # 19c: sin restricciones relevantes
    ("oracle", "21c"):  [],
    ("mysql", "5.6"):   [
        "no_window_functions",
        "no_cte",
        "no_json_table",
        "no_lateral_join",
        "no_check_constraint",
    ],
    ("mysql", "5.7"):   [
        "no_window_functions",
        "no_cte",
        "no_json_table",
    ],
    ("mysql", "8.0"):   [],  # 8.0: soporte completo
    ("postgresql", "9.6"): [
        "no_generated_columns",
        "no_merge_statement",
    ],
    ("postgresql", "12"): [
        "no_merge_statement",
    ],
    ("postgresql", "14"): [],
    ("postgresql", "15"): [],
    ("postgresql", "16"): [],
    ("sqlserver", "2008"): [
        "no_string_agg",
        "no_try_parse",
        "no_iif",
        "no_offset_fetch",
        "no_json_functions",
    ],
    ("sqlserver", "2012"): [
        "no_string_agg",
        "no_json_functions",
    ],
    ("sqlserver", "2016"): [
        "no_string_agg",  # STRING_AGG solo en 2017+
    ],
    ("sqlserver", "2017"): [],
    ("sqlserver", "2019"): [],
}

# Palabras clave que indican stack legacy (activan model_routing = claude)
_LEGACY_INDICATORS = {
    "oracle", "cobol", "rpg", "fortran", "struts", "ejb", "java ee", "jboss",
    "weblogic", "websphere", "sybase", "db2", "informix", "progress openedge",
    "vb6", "delphi", "foxpro",
}


# ---------------------------------------------------------------------------
# Lógica de resolución
# ---------------------------------------------------------------------------

def _normalize_db_key(db_engine: str, db_version: str) -> tuple[str, str]:
    """Normaliza (db_engine, db_version) al formato de RESTRICTION_RULES."""
    engine = db_engine.lower().strip()
    # Alias conocidos
    engine = engine.replace("postgres", "postgresql").replace("mssql", "sqlserver").replace("sql server", "sqlserver")
    version = db_version.lower().strip()
    return engine, version


def _infer_restrictions(db_engine: str, db_version: str) -> list[str]:
    """Busca restricciones desde RESTRICTION_RULES. Si no hay match exacto, busca prefijo."""
    key = _normalize_db_key(db_engine, db_version)
    if key in RESTRICTION_RULES:
        return RESTRICTION_RULES[key]
    # Fallback: buscar por engine sin versión específica (tomar la más restrictiva conocida)
    engine = key[0]
    candidates = [(k, v) for k, v in RESTRICTION_RULES.items() if k[0] == engine]
    if candidates:
        # Ordenar por cantidad de restricciones desc — usar el más restrictivo como fallback seguro
        candidates.sort(key=lambda x: len(x[1]), reverse=True)
        logger.warning(
            "No hay restricciones exactas para %s %s — usando fallback %s %s",
            db_engine, db_version, candidates[0][0][0], candidates[0][0][1],
        )
        return candidates[0][1]
    return []


def _resolve_model_routing(stack: StackRegistry) -> ModelRouting:
    """
    Resuelve la estrategia de modelo efectiva.

    Regla (en orden de precedencia):
    1. Si model_routing != 'auto': usar el valor explícito
    2. Si legacy_stack definido o db_engine es legacy: claude
    3. Si db_restrictions no vacías (stack con restricciones complejas): claude
    4. Si not: ollama
    """
    if stack.model_routing != "auto":
        return stack.model_routing

    # Detectar indicadores de stack legacy
    legacy_text = f"{stack.legacy_stack} {stack.db_engine} {stack.language}".lower()
    if any(indicator in legacy_text for indicator in _LEGACY_INDICATORS):
        return "claude"

    # Si hay restricciones activas → stack complejo → Claude
    if stack.db_restrictions:
        return "claude"

    return "ollama"


class ContextResolver:
    """
    Construye un AgentContext tipado desde los datos del request.

    El Bridge envía project_context como JSON serializado del profile.
    Si el JSON no parsea (compatibilidad con Sprints anteriores que enviaban
    texto libre), el resolver construye un contexto mínimo desde el texto.

    Sprint 9: resolve_async() recupera credenciales desde Infisical si
    el profile tiene secret_ref. Use resolve_async() en producción.
    resolve() (síncrono) sigue disponible para casos sin secrets.
    """

    @staticmethod
    def resolve(
        org_id: str,
        project_id: str,
        project_context: str,
        rag_context: str = "",
        language: str = "es",
        secret_ref: str = "",
    ) -> AgentContext:
        """
        Versión síncrona. No resuelve secrets (usa workspace_credentials={}).
        Válida para workspaces sin credenciales externas.
        Para workspaces con secret_ref, usar resolve_async().
        """
        stack = ContextResolver._parse_stack(project_context, secret_ref)

        restrictions = stack.db_restrictions
        if not restrictions and stack.db_engine:
            restrictions = _infer_restrictions(stack.db_engine, stack.db_version)
            stack.db_restrictions = restrictions

        effective_routing = _resolve_model_routing(stack)

        return AgentContext(
            org_id=org_id,
            project_id=project_id,
            stack=stack,
            model_routing=effective_routing,
            restrictions=restrictions,
            rag_context=rag_context,
            language=language,
            workspace_credentials={},
            secret_ref=secret_ref or stack.secret_ref,
        )

    @staticmethod
    async def resolve_async(
        org_id: str,
        project_id: str,
        project_context: str,
        rag_context: str = "",
        language: str = "es",
        secret_ref: str = "",
        secrets_adapter: "SecretsAdapter | None" = None,
    ) -> AgentContext:
        """
        Versión async (Sprint 9). Resuelve el AgentContext Y recupera credenciales
        del workspace desde Infisical si hay secret_ref configurado.

        Las credenciales se almacenan en ctx.workspace_credentials y NUNCA
        aparecen en logs, prompts ni en el estado del grafo visible al usuario.

        Args:
            secrets_adapter: inyectable para tests. Si None, usa get_adapter().
        """
        # Resolver el contexto base (síncrono)
        ctx = ContextResolver.resolve(
            org_id=org_id,
            project_id=project_id,
            project_context=project_context,
            rag_context=rag_context,
            language=language,
            secret_ref=secret_ref,
        )

        # Resolver secrets si hay secret_ref
        effective_secret_ref = secret_ref or ctx.secret_ref
        if effective_secret_ref:
            if secrets_adapter is None:
                from secrets_adapter import get_adapter
                secrets_adapter = get_adapter()

            credentials = await secrets_adapter.get_secrets(effective_secret_ref)
            ctx.workspace_credentials = credentials
            ctx.secret_ref = effective_secret_ref

            if credentials:
                log.info(
                    "context_resolver: %d credenciales recuperadas para workspace '%s' (secret_ref=%s)",
                    len(credentials), project_id, effective_secret_ref,
                )
            else:
                log.warning(
                    "context_resolver: secret_ref='%s' configurado pero no se recuperaron credenciales — "
                    "verificar Infisical (docker compose --profile infisical up -d)",
                    effective_secret_ref,
                )

        return ctx

    @staticmethod
    def _parse_stack(project_context: str, secret_ref_override: str = "") -> StackRegistry:
        """
        Parsea project_context como JSON estructurado.
        Fallback: si no es JSON válido, crea un StackRegistry mínimo con
        project_description = el texto libre (retrocompatibilidad S1-S7).
        """
        if not project_context:
            return StackRegistry(secret_ref=secret_ref_override)

        try:
            data = json.loads(project_context)
        except (json.JSONDecodeError, ValueError):
            # Retrocompatibilidad: el Bridge enviaba texto libre antes de S8
            logger.debug("project_context no es JSON válido — usando como texto libre (retrocompat)")
            return StackRegistry(
                project_description=project_context,
                secret_ref=secret_ref_override,
            )

        restrictions_raw = data.get("db_restrictions", [])
        # db_restrictions puede llegar como lista de strings o como JSON string
        if isinstance(restrictions_raw, str):
            try:
                restrictions_raw = json.loads(restrictions_raw)
            except (json.JSONDecodeError, ValueError):
                restrictions_raw = []

        additional_raw = data.get("additional_stack", [])
        if isinstance(additional_raw, str):
            try:
                additional_raw = json.loads(additional_raw)
            except (json.JSONDecodeError, ValueError):
                additional_raw = [additional_raw] if additional_raw else []

        routing_raw = data.get("model_routing", "auto")
        if routing_raw not in ("auto", "ollama", "claude", "openai"):
            routing_raw = "auto"

        # secret_ref: puede venir del JSON (Bridge lo serializa) o del override explícito
        secret_ref = secret_ref_override or data.get("secret_ref", "")

        return StackRegistry(
            language=data.get("language", ""),
            framework=data.get("framework", ""),
            db_engine=data.get("db_engine", ""),
            db_version=data.get("db_version", ""),
            runtime=data.get("runtime", ""),
            additional_stack=additional_raw,
            legacy_stack=data.get("legacy_stack", ""),
            model_routing=routing_raw,
            db_restrictions=restrictions_raw,
            constraints=data.get("constraints", ""),
            code_style=data.get("code_style", ""),
            project_description=data.get("project_description", ""),
            secret_ref=secret_ref,
        )
