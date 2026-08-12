from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://odoo:odoo_secret@db:5432/nexus_erp"
    redis_url: str = "redis://redis:6379/0"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    allowed_schemas: str = "public"
    request_timeout: int = 60

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
