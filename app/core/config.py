from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables / .env file."""
    APP_NAME: str = "Executive AI Voice Agent"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./executive_agent.db"

    # AI & Speech
    GEMINI_API_KEY: str = ""
    DEFAULT_VOICE: str = "en-US-AriaNeural"
    VOICE_RATE: str = "+0%"
    VOICE_PITCH: str = "+0Hz"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


settings = get_settings()
