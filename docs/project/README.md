# Backend module documentation

This directory documents the modules under `app/`: what each part does, the
rules it follows, and how the pieces fit together. It is a guide to
responsibilities and behavior, not a line-by-line walkthrough of the code.

## How the backend fits together

```text
NASA frames ──▶ CV engine (offline) ──▶ PostgreSQL ──▶ FastAPI (read-only) ──▶ Frontend
                app/cv_engine            playlists     app/api/v1             audio
                                         tracks        app/services           synthesis
```

- **CV engine** (`app/cv_engine/`): reads satellite images, converts colors to
  physical values, and summarizes every frame. It runs offline through the
  ingestion scripts, never inside a request.
- **Models and schemas** (`app/models/`, `app/schemas/`): define what is stored
  in PostgreSQL and what the API returns.
- **Services** (`app/services/`): own database access and ingestion logic.
- **API** (`app/api/v1/`): exposes read-only endpoints for playlists and tracks.
- **Core** (`app/core/`): central settings, database session handling, and rate
  limiting.
- **Application entry point** (`app/main.py`): creates the FastAPI app, wires
  middleware and routers, and runs startup and health checks.

## Documentation index

| Document | Covers |
|---|---|
| [main.md](main.md) | FastAPI application, lifespan checks, health endpoints |
| [core-config.md](core-config.md) | Central settings and project paths |
| [core-database.md](core-database.md) | SQLAlchemy engine, sessions, schema creation |
| [core-rate-limit.md](core-rate-limit.md) | Per-IP rate limiting |
| [api.md](api.md) | Versioned router and shared API behavior |
| [endpoints-playlists.md](endpoints-playlists.md) | Playlist endpoints |
| [endpoints-tracks.md](endpoints-tracks.md) | Track endpoints |
| [models.md](models.md) | `Playlist` and `Track` ORM models |
| [schemas.md](schemas.md) | Pydantic request and response schemas |
| [services-playlist.md](services-playlist.md) | Playlist database operations |
| [services-track.md](services-track.md) | Track database operations |
| [services-ingestion.md](services-ingestion.md) | Storing engine results as tracks |
| [cv-engine-overview.md](cv-engine-overview.md) | Engine purpose, exports, and output contract |
| [cv-engine-pipeline.md](cv-engine-pipeline.md) | Frame-to-JSON orchestration |
| [cv-engine-colormap.md](cv-engine-colormap.md) | Color tables and color inversion |
| [cv-engine-profiles.md](cv-engine-profiles.md) | Dataset profiles and the profile registry |
| [cv-engine-summarize.md](cv-engine-summarize.md) | Per-frame features, grids, and regions |
| [cv-engine-regions.md](cv-engine-regions.md) | Named geographic regions |
| [cv-engine-globe.md](cv-engine-globe.md) | Locating the planet in globe frames |
| [cv-engine-video.md](cv-engine-video.md) | Extracting frames from video |
| [cv-engine-exceptions.md](cv-engine-exceptions.md) | Engine exception hierarchy |

## Conventions referenced throughout

- **Read-only public API.** Product routes live under `/api/v1` and only read
  data. Uploads, measurement, and ingestion are offline administrative tasks.
- **Service layer owns data access.** Routers do not issue queries; they call
  functions in `app/services/`.
- **No blocking work on the event loop.** Synchronous database and engine calls
  are run through `run_in_threadpool`.
- **Central configuration.** Every environment variable is declared in
  `app/core/config.py`; modules never read `os.environ` directly.
- **Versioned engine contract.** The engine output uses schema version `2.2`.
  Changing the shape or names of its fields changes the database and frontend
  contract.

For setup commands and the public API summary, see the repository
[README](../../README.md) and [AGENTS.md](../../AGENTS.md).
