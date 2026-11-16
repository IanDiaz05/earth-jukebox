# Pydantic schemas

**Sources:** `app/schemas/playlist.py`, `app/schemas/track.py`,
`app/schemas/__init__.py`

The schemas validate ingestion payloads and shape API responses. Response
schemas that read ORM objects use `from_attributes=True`.

## Playlist schemas

| Schema | Purpose |
|---|---|
| `PlaylistBase` | Shared editorial fields: slug, title, description, category, cover URL, featured flag |
| `PlaylistCreate` | Creation payload; the same fields as the base |
| `PlaylistUpdate` | Partial update payload; every field is optional and omitted fields are left unchanged |
| `PlaylistSummaryResponse` | Summary returned by the list endpoint: base fields plus `id`, `created_at`, and `updated_at` |
| `PlaylistDetailResponse` | Summary plus `tracks`, a list of `TrackSummaryResponse` |

Field limits mirror the database: slug 100 characters, title 150, category 50,
cover URL 255.

## Track schemas

| Schema | Purpose |
|---|---|
| `TrackBase` | All track fields, including `source_metadata`, `engine_metadata`, and `frames` |
| `TrackCreate` | Creation payload for a track; adds `playlist_id` |
| `TrackIngestData` | Editorial data supplied to ingestion: title, slug, description, order, event date, and source metadata |
| `TrackUpdate` | Partial update payload; all fields optional |
| `TrackSummaryResponse` | Lightweight representation for playlist listings; includes source metadata but omits `engine_metadata` and `frames` |
| `TrackDetailResponse` | Full representation for playback; adds `engine_metadata` and `frames` |

`TrackIngestData` intentionally excludes `engine_metadata` and `frames`: those
come from the measurement engine, not from the editor.

## Response size strategy

The list endpoints and playlist detail stay small by returning summaries. The
track detail endpoint returns the full payload, including the per-frame
measurements the frontend needs to generate audio.
