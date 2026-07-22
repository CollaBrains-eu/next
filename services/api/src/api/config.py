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
    # qwen2.5-coder:1.5b replaces qwen3:8b (5.7GB/377% CPU observed live on this
    # 4-vCPU/8GB CPU-only host -- see docs/deployment/ai-optimization.md). It's a
    # code-specialized model, not an ideal semantic fit for legal/document chat --
    # qwen2.5:3b-instruct (already pulled) is the documented fallback if answer
    # quality on /chat or /legal/draft regresses.
    chat_model: str = "qwen2.5-coder:1.5b"
    reasoning_model: str = "deepseek-r1:1.5b"
    chat_num_predict: int = 512
    reasoning_num_predict: int = 1024

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


settings = Settings()
