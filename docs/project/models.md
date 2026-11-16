# ORM models

**Sources:** `app/models/playlist.py`, `app/models/track.py`,
`app/models/__init__.py`

The models define the two PostgreSQL tables. The package initializer imports
both classes so that `Base.metadata` knows about every table when `init_db()`
runs.

## `Playlist` — table `playlists`

A playlist groups ordered tracks and carries the editorial metadata shown in
the interface.

| Column | Type | Rules |
|---|---|---|
| `id` | integer | Primary key, auto-increment |
| `slug` | string(100) | Required, unique, indexed |
| `title` | string(150) | Required |
| `description` | text | Optional |
| `category` | string(50) | Required, indexed |
| `cover_url` | string(255) | Optional |
| `is_featured` | boolean | Required, defaults to `false` |
| `created_at` | timestamptz | Set by the database on insert |
| `updated_at` | timestamptz | Set on insert and refreshed on update |

**Relationship:** `tracks` is a one-to-many relationship to `Track`, ordered by
`sequence_order`. Deleting a playlist cascades to its tracks both in the ORM
(`all, delete-orphan`) and in the database (`ON DELETE CASCADE`).

## `Track` — table `tracks`

A track is one timelapse inside a playlist. Editorial metadata is stored in
normal columns and the engine output is stored in JSONB.

| Column | Type | Rules |
|---|---|---|
| `id` | integer | Primary key, auto-increment |
| `playlist_id` | integer | Required foreign key to `playlists.id`, cascades on delete |
| `slug` | string(100) | Required, unique, indexed |
| `title` | string(150) | Required |
| `description` | text | Optional |
| `sequence_order` | integer | Required, defaults to `0` |
| `event_date` | timestamptz | Optional |
| `source_metadata` | JSONB | Required; provenance and public image location |
| `engine_metadata` | JSONB | Required; engine dataset information |
| `frames` | JSONB array | Required; per-frame measurements |
| `created_at` | timestamptz | Set by the database on insert |

**Relationship:** `playlist` is the reverse side of the playlist's `tracks`
relationship.

## JSONB payloads

Keeping the measurement payloads in JSONB lets the engine contract evolve
without a column per feature:

- `source_metadata` describes the frames and their public URLs.
- `engine_metadata` mirrors the engine's `dataset_info`.
- `frames` mirrors the engine's `frames` array.

The shape of these payloads is defined by the engine schema version `2.2`; see
[cv-engine-overview.md](cv-engine-overview.md).
