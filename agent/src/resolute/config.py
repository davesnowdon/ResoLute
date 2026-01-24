"""Application configuration using Pydantic settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Gemini
    google_api_key: str = Field(default="", description="Google API key for Gemini")
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model to use")

    # Opik
    opik_api_key: str = Field(default="", description="Opik API key for tracing")
    opik_workspace: str = Field(default="resolute", description="Opik workspace name")
    opik_project_name: str = Field(default="resolute", description="Opik project name")

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./resolute.db",
        description="Database connection URL",
    )

    @property
    def has_google_api_key(self) -> bool:
        """Check if Google API key is configured."""
        return bool(self.google_api_key)

    @property
    def has_opik_api_key(self) -> bool:
        """Check if Opik API key is configured."""
        return bool(self.opik_api_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
