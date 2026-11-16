# Track service

**Source:** `app/services/track_service.py`

This module owns track database operations. Like the playlist service, its
functions are synchronous and blocking and are called from the API through
`run_in_threadpool`.

## Functions

| Function | What it does |
|---|---|
| `create_track(db, data)` | Inserts a track from a `TrackCreate`, commits, and refreshes it |
| `replace_track(db, track, data)` | Overwrites an existing track's content while preserving its ID and slug |
| `get_track_by_id(db, track_id)` | Returns a track by primary key, or `None` |
| `get_track_by_slug(db, slug)` | Returns a track by unique slug, or `None` |
| `list_tracks_by_playlist(db, playlist_id)` | Lists a playlist's tracks ordered by `sequence_order` and `id` |

## Behavior details

- **Full measurement payload.** `create_track` copies `source_metadata`,
  `engine_metadata`, and `frames` into their JSONB columns.
- **Re-measuring without changing URLs.** `replace_track` is used when a
  timelapse is measured again. It updates every content field except `slug`
  (ignored from the payload) and `id`, so the frontend URL stays valid.
- **Ordering.** `list_tracks_by_playlist` sorts by `sequence_order`, then `id`
  as a tie-breaker.
- **Atomic writes.** Writes commit inside a `try` block and roll back before
  re-raising `SQLAlchemyError`.
- **Lookups.** Slug lookups use `scalar_one_or_none()`, so an unexpected
  duplicate slug raises rather than silently choosing a row.

## Used by

- `app/api/v1/endpoints/tracks.py`
- `app/services/ingestion_service.py`
