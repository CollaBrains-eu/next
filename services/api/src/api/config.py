from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://collabrains:changeme@localhost:5432/collabrains"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-only-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    ldap_url: str = "ldap://localhost:389"
    ldap_base_dn: str = "dc=collabrains,dc=eu"
    ldap_bind_dn_template: str = "uid={username},ou=people,dc=collabrains,dc=eu"
    ldap_admin_group_dn: str = "cn=collabrains-admins,ou=groups,dc=collabrains,dc=eu"
    ldap_admin_password: str = "changeme"

    paperless_url: str = "http://paperless:8000"
    paperless_admin_user: str = "admin"
    paperless_admin_password: str = "changeme"

    ollama_url: str = "http://ollama:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    # qwen3:8b is the verified-correct default for this deployment despite its
    # size (5.7GB/377% CPU observed live on this 4-vCPU/8GB CPU-only host -- see
    # docs/deployment/ai-optimization.md). A 2026-07-22 investigation
    # (project_collabrains_signal_quality_issue memory) already found smaller
    # models (qwen2.5:3b-instruct) produce garbled/hallucinated output and wrong-
    # language replies specifically in manager_agent's multi-round tool-calling
    # path; this session live-tested qwen2.5-coder:1.5b and found it worse still
    # (never actually issues a real tool call, just prints fake JSON as text, and
    # produced incoherent output on a Dutch-language prompt). Do not downsize this
    # again without live-testing manager_agent tool-calling and a non-English
    # prompt specifically, not just a trivial greeting -- both failure modes are
    # invisible on a simple "say hello" smoke test.
    chat_model: str = "qwen3:8b"
    reasoning_model: str = "deepseek-r1:1.5b"
    chat_num_predict: int = 512
    reasoning_num_predict: int = 1024
    # qwen3:8b on this 4-vCPU CPU-only host live-timed a correct-but-slow response at ~120s+ for a
    # longer answer (see docs/deployment/ai-optimization.md) -- the old 120s httpx timeout turned
    # that into a ReadTimeout/500 instead of just being slow. 240s gives real headroom without being
    # unbounded.
    ollama_timeout_seconds: float = 240.0

    chunk_size: int = 800
    chunk_overlap: int = 100

    ai_rate_limit_per_minute: int = 30
    ai_max_context_chunks: int = 5
    auto_extract_tasks_on_ready: bool = True
    auto_extract_entities_on_ready: bool = True
    auto_extract_vehicles_on_ready: bool = True
    auto_classify_on_ready: bool = True
    auto_extract_facts_on_ready: bool = True
    auto_extract_metafields_on_ready: bool = True
    rdw_app_token: str = ""

    signal_cli_url: str = ""
    signal_phone_number: str = ""

    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "CollaBrains"
    webauthn_origin: str = "http://localhost:5173"

    internal_api_secret: str = ""
    codeberg_api_token: str = ""
    codeberg_repo: str = ""

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@collabrains.eu"

    app_base_url: str = "https://collabrains.eu"
    # Browser CORS only matters for cross-origin callers -- production traffic
    # goes through Caddy same-origin (see infra/caddy/Caddyfile) and never hits
    # this check. The one real cross-origin case is the local Vite dev server
    # talking to a locally-run API on a different port. Comma-separated so an
    # operator can add a real second origin without a code change if a
    # legitimate cross-origin browser client ever exists (ADR 0066 P1: this
    # was hardcoded with no way to override before).
    cors_allowed_origins: str = "http://localhost:5173"

    # Empty by default -- Sentry stays fully off (sentry_sdk.init is never
    # called) in local dev/CI/test where no DSN is configured. See ADR 0072.
    sentry_dsn: str = ""
    sentry_environment: str = "development"


settings = Settings()
