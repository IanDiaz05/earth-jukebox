---
name: spotiearth-standards
description: Enforce SpotiEarth architecture and coding standards for the FastAPI backend, including centralized settings, service-layer data access, versioned API routes, async delegation, and clean typed code.
---

# SpotiEarth Architectural Standards

This skill enforces the core architectural and coding standards for the SpotiEarth backend (FastAPI).

## When to Use

* Modifying or creating environment variables.
* Creating new FastAPI routers or endpoints.
* Writing file path resolutions.
* Integrating new modules (e.g., machine learning engines) or services into the backend.
* Designing database queries, ORM models, or Pydantic schemas.

## Core Rules

1.  **Centralized Configuration (`app/core/config.py`)**:

      * ALL environment variables and global configurations MUST live in `app/core/config.py` using `pydantic-settings`.
      * NEVER use `os.getenv()` or `os.environ` directly in business logic, routers, or engines.
      * Sub-modules (like `app/cv_engine/`) must remain agnostic to the `.env` file. Pass configurations as arguments from the API layer.

2.  **No Hardcoded Paths**:

      * NEVER hardcode paths in routers or logic (e.g., `APP_DIR = Path(...)` inside a route).
      * Global paths (like `EPIC_TIMELAPSE_DIR`) belong in `app/core/config.py`.
      * Module-internal paths (like ML model artifacts) should be resolved dynamically relative to their own `__file__` in their respective `config.py` files.

3.  **Data Layer & Service Pattern (`app/services/`)**:

      * Use SQLAlchemy 2.0 ORM models (`Playlist`, `Track`). Database tables are initialized via `Base.metadata.create_all(bind=engine)` inside `init_db()`.
      * Complex JSON structures (`frames`, `source_metadata`, `engine_metadata`) are stored natively in PostgreSQL `JSONB` columns.
      * ALL database operations and business logic MUST live in `app/services/` (`playlist_service.py`, `track_service.py`, `ingestion_service.py`).
      * Routers MUST remain lightweight and delegate DB operations to the service layer using the `get_db` session dependency.

4.  **API Endpoints & Responsibilities**:

      * Product endpoints MUST be versioned under `/api/v1/` (e.g., `/api/v1/playlists`, `/api/v1/tracks/{slug}`).
      * Public API endpoints serve read-heavy queries to the frontend.
      * Ingestion and heavy ML processing are strictly offline administrative tasks managed via CLI scripts (`scripts/ingest_timelapse.py`) utilizing `ingestion_service.py`. Do NOT expose public endpoints for image uploads or synchronous ML execution.

5.  **Asynchronous Delegation**:

      * CPU-bound tasks (like Machine Learning inferencing or heavy mathematical computations) and blocking I/O operations MUST NOT block the FastAPI event loop.
      * Use `run_in_threadpool` from `starlette.concurrency` for synchronous blocking operations where appropriate.

6.  **Clean Code**:

      * Enforce strict Type Hinting everywhere.
      * Write concise docstrings. Do NOT leave long explanatory comments, emojis, or design notes embedded in the code.
