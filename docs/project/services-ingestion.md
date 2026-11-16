# Ingestion service

**Source:** `app/services/ingestion_service.py`

This module bridges the offline measurement engine and the database. It takes
the engine's JSON result and stores it as a track in a playlist.

## `ingest_timelapse_result(...)`

```python
ingest_timelapse_result(
    db,
    playlist_id,
    track_data,
    pipeline_result,
    replace=False,
) -> Track
```

**Inputs:**

| Argument | Meaning |
|---|---|
| `db` | Active SQLAlchemy session |
| `playlist_id` | Destination playlist |
| `track_data` | `TrackIngestData` or a dictionary with title, slug, description, order, event date, and source metadata |
| `pipeline_result` | Engine output containing `dataset_info` and `frames` |
| `replace` | Whether an existing slug may be overwritten |

**What it does:**

1. Validates `track_data` into `TrackIngestData`.
2. Builds a `TrackCreate` that combines the editorial fields with
   `pipeline_result["dataset_info"]` as `engine_metadata` and
   `pipeline_result["frames"]` as `frames`.
3. Looks up the slug.
   - If it does not exist, creates a new track.
   - If it exists and `replace=False`, raises `TrackAlreadyExistsError`.
   - If it exists and `replace=True`, replaces the content while keeping the ID
     and slug.

**Errors:** Pydantic validation errors for bad editorial data,
`TrackAlreadyExistsError` for an existing slug without replacement, and
`SQLAlchemyError` if the write fails (the underlying service rolls back first).

## `TrackAlreadyExistsError`

A domain exception raised when a slug collision happens without an explicit
replacement request. It lets the CLI report the conflict without exposing a raw
database error.

## Audio hints

The module does not add audio information separately: the engine's
`dataset_info["hints"]` already carries the sonification hints defined by the
visualization profile.

## Used by

- `scripts/ingest_timelapse.py`
- `app/services/__init__.py` re-exports `ingest_timelapse_result`
