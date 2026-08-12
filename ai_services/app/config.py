from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://odoo:odoo_secret@db:5432/nexus_erp"
    redis_url: str = "redis://redis:6379/0"

    ai_provider: str = "auto"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_base_url: str | None = None

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    allowed_schemas: str = "public"
    request_timeout: int = 60

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
