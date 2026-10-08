from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # API Security
    API_KEY: str = "dev-supportflow-api-key-change-me"
    WEBHOOK_SECRET: str = "dev-supportflow-hmac-secret-change-me"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/supportflow"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_EMBEDDING_DIM: int = 768

    # HubSpot
    HUBSPOT_ACCESS_TOKEN: str = ""

    # Slack
    SLACK_WEBHOOK_URL: str = ""

    # Gmail
    GMAIL_USER: str = ""

    # n8n
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook"

    # Dashboard
    DASHBOARD_PASSWORD: str = "admin"

    # Path to escalation config
    ESCALATION_CONFIG_PATH: str = "api/config/escalation.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
