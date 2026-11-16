# `app/api/v1/` — public API layer

**Sources:** `app/api/v1/router.py`,
`app/api/v1/endpoints/playlists.py`, `app/api/v1/endpoints/tracks.py`

The API layer is a thin, read-only interface over the service layer. All product
routes are versioned under `/api/v1`; there are no write endpoints.

## Router composition

`api_v1_router` aggregates the endpoint routers:

| Prefix | Router file | Tag |
|---|---|---|
| `/playlists` | `endpoints/playlists.py` | `Playlists` |
| `/tracks` | `endpoints/tracks.py` | `Tracks` |

`app/main.py` mounts the aggregate router with the `/api/v1` prefix, producing
the public paths `/api/v1/playlists`, `/api/v1/playlists/{slug}`, and
`/api/v1/tracks/{slug}`.

## Shared patterns

Every endpoint:

- Declares a response model so the OpenAPI schema and validation are explicit.
- Receives a database session through the `DbSession` annotation
  (`Annotated[Session, Depends(get_db)]`).
- Applies the configured per-IP rate limit with `@limiter.limit(...)`, which is
  why each route takes the `Request` object.
- Delegates the query to a synchronous service function through
  `run_in_threadpool`, keeping blocking database work off the event loop.
- Returns a Pydantic response model validated from the ORM object.

## Endpoint reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/playlists` | List playlists, optionally filtered by category or featured flag |
| `GET` | `/api/v1/playlists/{slug}` | Return one playlist with lightweight track summaries |
| `GET` | `/api/v1/tracks/{slug}` | Return one track with everything needed to synthesize audio |

Detail pages for each endpoint are in
[endpoints-playlists.md](endpoints-playlists.md) and
[endpoints-tracks.md](endpoints-tracks.md).
