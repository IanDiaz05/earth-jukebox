# `app/main.py` — application entry point

**Source:** `app/main.py`

This module creates the FastAPI application, connects middleware and routers,
and defines the service-level health endpoints. Uvicorn loads the `app` object
from here.

## Responsibilities

- Build the `FastAPI` instance with the project name, version, and optional
  Swagger/ReDoc/OpenAPI routes.
- Register rate limiting, CORS, and the `/api/v1` router.
- Run startup checks for the engine profiles and the database schema.
- Expose `/` and `/health`.

## Startup (`lifespan`)

When the application starts, the lifespan handler:

1. **Checks engine profiles.** `_usable_profiles()` walks the registered
   profiles in `PROFILES`. A profile is considered usable if it uses an image
   legend (validated later while processing) or if its color table can be loaded
   with `load_lut`. The resulting list is stored in `app.state.ml_profiles` so
   health checks can report engine status without reloading tables.
2. **Prepares the database schema.** `init_db()` creates any missing tables. If
   this fails with a SQLAlchemy error, the failure is logged and the application
   still starts; the health endpoint then reports the connection problem.

The engine needs no model warm-up because it only reads color tables.

## Application setup

- **Docs routes** are enabled only when `settings.ENABLE_DOCS` is true. When
  disabled, `/docs`, `/redoc`, and `/openapi.json` are not registered.
- **Rate limiting** uses the shared limiter from `app/core/rate_limit.py`.
  `SlowAPIMiddleware` applies the default limit, and the exception handler
  returns the standard rate-limit response.
- **CORS** allows the origins in `settings.ALLOWED_ORIGINS` (all origins by
  default) with credentials, all methods, and all headers.
- **Routers** mount `api_v1_router` under `/api/v1`.

## Endpoints defined here

### `GET /`

A welcome endpoint. It returns:

| Field | Meaning |
|---|---|
| `service` | Configured project name |
| `version` | Configured API version |
| `status` | Always `"ok"` |
| `docs` | `"/docs"` when docs are enabled, otherwise `null` |

### `GET /health`

A readiness/health check for orchestrators and the devcontainer. It runs a
`SELECT 1` query in a thread pool and reports:

| Field | Meaning |
|---|---|
| `status` | `"healthy"` or `"unhealthy"` |
| `database` | `"connected"` or `"disconnected"` |
| `cv_engine` | `"ready"` if at least one profile is usable, otherwise `"unavailable"` |

It returns HTTP `200` when the database responds and HTTP `503` when the query
fails. Engine status comes from the startup check stored in `app.state`.

## Notes

- Database errors in the health check are logged, not raised.
- The health endpoint does not run the measurement engine; it only reports the
  profile check performed at startup.
