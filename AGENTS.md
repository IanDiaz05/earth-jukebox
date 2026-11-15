# AGENTS.md

Shared instructions for AI coding agents in this repository. Read this file
before changing code, then load the skill that matches the task.

## What this project is

SpotiEarth Backend is a FastAPI service that stores and serves satellite
timelapse playlists and tracks. Tracks are produced offline by a computer-vision
engine that decodes NASA color scales into per-frame measurements; the public
API only reads precomputed data. PostgreSQL stores `source_metadata`,
`engine_metadata`, and `frames` as JSONB.

- Runtime: Python 3.13 in the devcontainer.
- API: FastAPI, Pydantic v2, slowapi rate limiting.
- Data: SQLAlchemy 2.0 ORM, PostgreSQL. Tables are created with
  `Base.metadata.create_all()`; there are no migrations.
- Engine: NumPy, OpenCV, Pillow. No neural networks.
- Tests: standard library `unittest`.

## Repository map

| Path | Contents |
|---|---|
| `app/main.py` | FastAPI app, CORS, rate limit, health checks, lifespan |
| `app/core/` | Central settings, database engine/session, rate limiter |
| `app/api/v1/` | Versioned public read endpoints (`/api/v1/playlists`, `/api/v1/tracks`) |
| `app/services/` | Synchronous business logic and database operations |
| `app/models/` | SQLAlchemy ORM models (`Playlist`, `Track`) |
| `app/schemas/` | Pydantic request/response schemas |
| `app/cv_engine/` | Color-table engine, profiles, regions, globes, video frames |
| `scripts/` | Offline administrative CLIs for playlists, tracks, and color tables |
| `tests/` | `unittest` suite for the CV engine |
| `docs/` | Dataset sources and long-form reference material |
| `.agents/skills/` | Canonical project skills (source of truth) |
| `.claude/skills/`, `.cursor/skills/` | Copies of the skills for Claude Code and Cursor |

## Setup and commands

Run commands from the repository root so `scripts/` can import `app`.

```bash
# First-time setup
cp .env.example .env          # set DATABASE_URL for your environment
pip install -r requirements.txt

# Development API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tests (no database required)
python -m unittest discover -s tests -v

# Engine and ingestion help
python scripts/ingest_playlist.py --help
python scripts/ingest_timelapse.py --help
```

In the devcontainer, PostgreSQL is the `db` service and `DATABASE_URL` is already
set. On the host, point `DATABASE_URL` at a running PostgreSQL instance.

`settings.DATABASE_URL` is required at import time, so the API and scripts cannot
start without it. Never commit `.env`, generated frames, or downloaded imagery.

## Architecture rules

These rules are mandatory. The full rationale is in
`.agents/skills/spotiearth-standards/SKILL.md`.

1. **Central configuration.** Every environment variable and global setting
   lives in `app/core/config.py` using `pydantic-settings`. Do not call
   `os.getenv()` or read `os.environ` in routers, services, or engines. Engines
   receive configuration as arguments from the API or CLI layer.
2. **No hardcoded paths.** Use `BASE_DIR` / `APP_DIR` from `app.core.config`.
   Module-owned artifacts resolve relative to their own `__file__`.
3. **Service layer owns data access.** Put database queries and business logic
   in `app/services/`. Routers stay thin and use the `get_db` session dependency.
   Keep complex structures (`frames`, `source_metadata`, `engine_metadata`) in
   JSONB columns.
4. **Versioned public API.** Product endpoints live under `/api/v1/`. They serve
   read-heavy frontend queries. Image uploads and synchronous CV/ML execution
   are offline administrative tasks, not public endpoints.
5. **Never block the event loop.** CPU-bound engine work and blocking database
   calls run through `run_in_threadpool` (or synchronous service functions
   invoked from async routes with `run_in_threadpool`).
6. **Clean typed code.** Add type hints and concise docstrings to every public
   function. Do not leave long explanatory comments, design notes, or emojis in
   source files. Use English for code, docstrings, comments, and commit messages.

When adding a visualization, add its color table under
`app/cv_engine/colormaps/`, define a `DatasetProfile` in
`app/cv_engine/profiles.py`, and register it in `PROFILES`. Do not bypass the
profile registry from routers or scripts.

The engine output contract is versioned (`schema_version` 2.2). Changing field
names or shapes changes the database contract and the frontend; bump the schema
version, update the README, and add tests.

## Project skills

Skills are on-demand instructions. Read the matching `SKILL.md` before starting
work, not after making changes. `.agents/skills/` is canonical; sync edits to the
Claude and Cursor copies.

| Skill | Use when |
|---|---|
| `spotiearth-standards` | Changing configuration, routers, services, models, schemas, paths, or engine/API integration |
| `spotiearth-timelapse-ingest` | Ingesting frame folders, creating or editing playlists/tracks, or generating slugs, titles, descriptions, categories, and playback order |

Skill locations:

- Generic agents: `.agents/skills/<skill>/SKILL.md`
- Claude Code: `.claude/skills/<skill>/SKILL.md`
- Cursor: `.cursor/skills/<skill>/SKILL.md` (Cursor also reads `.agents/skills/`)

## Ingestion guardrails

Timelapse ingestion is an offline, destructive-capable workflow. Follow the full
skill; these rules are non-negotiable:

- Use `scripts/ingest_playlist.py` and `scripts/ingest_timelapse.py`; do not write
  playlists or tracks with raw SQL unless the user explicitly asks for it.
- A playlist must exist before a track is ingested.
- Dry-run every track with `--dry-run --out` and inspect the JSON before writing.
- Use only the 15 profile IDs registered in `app/cv_engine.PROFILES`. Do not
  improvise a profile for an unsupported visualization.
- Never invent titles, descriptions, dates, locations, units, or measurements.
- Never use `--replace` or delete a playlist without explicit confirmation.
- Ingest tracks sequentially, never concurrently against the same playlist.
- Pass editorial text as plain text; slugs are lowercase ASCII kebab-case.

## Working agreements

- Read the surrounding code before editing and match its patterns.
- Keep changes scoped to the request; do not reformat or refactor unrelated files.
- Preserve public behavior unless the task explicitly changes it.
- Add or update tests for engine, schema, and service changes. The suite must pass
  before you report completion.
- Do not commit secrets, `.env`, `frames/`, caches, or generated output.
- Keep `AGENTS.md`, the skills, and the Claude/Cursor copies in sync when you
  change project conventions.
