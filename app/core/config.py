"""Central configuration for SpotiEarth.

All sensitive configuration is loaded from environment variables or the
`.env` file. Credentials, hosts, usernames, and passwords are never hardcoded.
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute project paths, independent of the current working directory.
BASE_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BASE_DIR / "app"
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "SpotiEarth API"
    VERSION: str = "0.1.0"

    # CORS — allow all in development; restrict in production.
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Global API rate limit.
    DEFAULT_RATE_LIMIT: str = "60/minute"

    # --- PostgreSQL ---
    # Loaded from the environment / `.env`; no sensitive default values.
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None

    # Full SQLAlchemy DSN. Required to avoid falling back to an insecure
    # configuration if the environment variable is missing.
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection DSN for SQLAlchemy.",
    )


settings = Settings()
