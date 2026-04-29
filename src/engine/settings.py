"""
OVD Platform — Configuración centralizada
Copyright 2026 Omar Robles

Fuente única de verdad para todas las variables de entorno del engine.
Usa pydantic-settings para validación de tipos en startup.

Uso:
    from settings import get_settings
    s = get_settings()
    db_url = s.database_url

Todos los campos tienen defaults para no bloquear tests unitarios.
Los campos requeridos en producción están marcados con comentario [REQUIRED].
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class OVDSettings(BaseSettings):
    # env_file=None intencional: load_dotenv() en main.py ya carga .env al proceso.
    # Así los tests no ven valores de .env (preserva comportamiento anterior de os.environ.get).
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
    )

    # ── Base de datos ──────────────────────────────────────────────────────────
    database_url: str = ""  # [REQUIRED en producción]

    # ── Auth y seguridad ───────────────────────────────────────────────────────
    jwt_secret: str = ""  # [REQUIRED en producción] — env: JWT_SECRET
    ovd_engine_secret: str = ""  # [REQUIRED en producción] — env: OVD_ENGINE_SECRET
    ovd_access_token_ttl_hours: int = 1
    ovd_refresh_token_ttl_days: int = 7

    # ── Servidor ───────────────────────────────────────────────────────────────
    port: int = 8001
    log_level: str = "info"
    node_env: str = "production"
    ovd_cors_origins: str = "*"

    # ── LLM — modelos y proveedores ────────────────────────────────────────────
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ovd_model: str = "qwen2.5-coder:7b"
    ovd_model_claude: str = "claude-sonnet-4-6"
    ovd_model_openai: str = "gpt-4o-mini"
    ovd_model_analyzer: str = ""  # fallback a ovd_model si vacío
    ovd_model_sdd: str = ""  # fallback a ovd_model si vacío
    ovd_model_qa: str = ""  # fallback a ovd_model si vacío
    ovd_vision_model: str = "qwen2.5vl:7b"
    ovd_vision_enabled: bool = True
    ovd_agent_provider: str = ""
    ovd_agent_model: str = ""

    # ── Ollama ─────────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ovd_vision_ollama_url: str = ""  # fallback a ollama_base_url si vacío

    # ── Timeouts (segundos) ────────────────────────────────────────────────────
    ovd_llm_timeout_secs: float = 300.0
    ovd_node_timeout_secs: float = 120.0
    ovd_agents_timeout_secs: float = 120.0
    ovd_analyze_timeout_secs: float = 300.0
    ovd_sdd_timeout_secs: float = 600.0
    ovd_research_timeout_secs: float = 180.0
    ovd_tests_timeout_secs: float = 300.0
    ovd_docs_timeout_secs: float = 600.0
    ovd_qa_timeout_secs: float = 1200.0
    ovd_security_timeout_secs: float = 1800.0
    ovd_sse_stream_timeout_secs: float = 900.0
    ovd_heartbeat_timeout_secs: int = 0
    ovd_stale_session_minutes: int = 30
    ovd_watcher_interval_secs: int = 60

    # ── Ciclo y calidad ────────────────────────────────────────────────────────
    ovd_max_retries: int = 3
    ovd_max_context_tokens: int = 28000
    ovd_cycle_token_budget: int = 0
    ovd_qa_min_score: int = 70
    ovd_security_min_score: int = 0
    ovd_security_scan_enabled: bool = False

    # ── RAG ────────────────────────────────────────────────────────────────────
    ovd_rag_enabled: bool = True
    ovd_rag_embedding_provider: str = "ollama"
    ovd_embed_model: str = "nomic-embed-text"
    ovd_rag_top_k: int = 5
    ovd_rag_min_score: float = 0.65

    # ── Integración externa ────────────────────────────────────────────────────
    ovd_bridge_url: str = "http://localhost:3000"
    nats_url: str = ""
    nats_creds_file: str = ""
    tavily_api_key: str = ""
    ovd_searxng_url: str = ""
    ovd_web_search_provider: str = "duckduckgo"
    ovd_web_max_results: int = 5
    ovd_web_max_queries: int = 4
    ovd_web_cache_days: int = 7

    # ── Nightly researcher ─────────────────────────────────────────────────────
    ovd_nightly_enabled: bool = True
    ovd_nightly_hour: int = 2
    ovd_nightly_max_orgs: int = 10
    ovd_nightly_max_queries: int = 3

    # ── Infisical (secrets manager) ────────────────────────────────────────────
    infisical_url: str = "http://localhost:8080"
    infisical_token: str = ""
    infisical_project_id: str = ""
    infisical_timeout_secs: float = 5.0

    # ── Observabilidad ─────────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = ""
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""

    # ── Misc ───────────────────────────────────────────────────────────────────
    ovd_finetune_dir: str = "/tmp/ovd-finetune"
    ovd_cb_fail_threshold: int = 5
    ovd_cb_recovery_secs: float = 30.0


@lru_cache
def get_settings() -> OVDSettings:
    """Devuelve la instancia singleton de configuración. Se instancia una sola vez."""
    return OVDSettings()
