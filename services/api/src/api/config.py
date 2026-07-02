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


settings = Settings()
