from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    redis_url: str = "redis://redis:6379/0"

    # Shared secret required on every API call via the X-API-Key header.
    api_services_api_key: str = Field(default="", alias="AI_SERVICES_API_KEY")

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
    request_timeout: int = 300

    # CORS: comma-separated list of allowed origins. Empty string disables CORS
    # (i.e. only same-origin / server-to-server calls). "*" is intentionally not
    # the default because it allows any website to call the AI API from a browser.
    cors_origins: str = Field(default="", alias="AI_CORS_ORIGINS")

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
