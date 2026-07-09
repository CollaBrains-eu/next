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

    paperless_url: str = "http://paperless:8000"
    paperless_admin_user: str = "admin"
    paperless_admin_password: str = "changeme"

    ollama_url: str = "http://ollama:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    chat_model: str = "qwen3:8b"

    chunk_size: int = 800
    chunk_overlap: int = 100

    ai_rate_limit_per_minute: int = 30
    ai_max_context_chunks: int = 5
    auto_extract_tasks_on_ready: bool = True
    auto_extract_entities_on_ready: bool = True
    auto_extract_vehicles_on_ready: bool = True
    auto_classify_on_ready: bool = True
    auto_extract_facts_on_ready: bool = True
    rdw_app_token: str = ""

    signal_cli_url: str = ""
    signal_phone_number: str = ""


settings = Settings()
