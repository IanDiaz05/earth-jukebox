# `app/core/config.py` — central configuration

**Source:** `app/core/config.py`

This module is the single source of truth for environment variables, global
settings, and absolute project paths. Other modules import `settings` and the
path constants instead of reading the environment directly.

## Project paths

| Constant | Value | Purpose |
|---|---|---|
| `BASE_DIR` | Repository root | Resolves paths independent of the current working directory |
| `APP_DIR` | `BASE_DIR / "app"` | Root of the application package |
| `ENV_FILE` | `BASE_DIR / ".env"` | Environment file loaded by pydantic-settings |

## `Settings`

`Settings` extends `BaseSettings` and loads values from the `.env` file and the
process environment. Names are case-sensitive, unknown variables are ignored,
and values come from the environment first.

| Setting | Default | Purpose |
|---|---|---|
| `PROJECT_NAME` | `"SpotiEarth API"` | API title and service name |
| `VERSION` | `"0.1.0"` | API version reported in docs and responses |
| `ALLOWED_ORIGINS` | `["*"]` | CORS origins; restrict in production |
| `DEFAULT_RATE_LIMIT` | `"60/minute"` | Per-IP limit for the API and endpoints |
| `ENABLE_DOCS` | `true` | Enables `/docs`, `/redoc`, and the OpenAPI schema |
| `POSTGRES_USER` | `None` | Database user for the Docker Compose service |
| `POSTGRES_PASSWORD` | `None` | Database password for the Compose service |
| `POSTGRES_DB` | `None` | Database name for the Compose service |
| `DATABASE_URL` | required | SQLAlchemy DSN used to connect to PostgreSQL |

`DATABASE_URL` has no fallback. The API and the ingestion scripts cannot start
without it, which prevents an accidental connection to an insecure default.

## Exported singleton

At import time the module creates `settings = Settings()`. Importing any module
that depends on configuration therefore validates the environment immediately.
