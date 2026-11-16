# Playlist service

**Source:** `app/services/playlist_service.py`

This module owns all playlist database operations. The functions are
synchronous and blocking; the API calls them through `run_in_threadpool`.

## Functions

| Function | What it does |
|---|---|
| `create_playlist(db, data)` | Inserts a playlist from a `PlaylistCreate`, commits, and refreshes the instance |
| `get_playlist_by_id(db, playlist_id)` | Returns a playlist by primary key, or `None` |
| `get_playlist_by_slug(db, slug)` | Returns a playlist by unique slug with its tracks eagerly loaded, or `None` |
| `list_playlists(db, category, is_featured, limit, offset)` | Lists playlists ordered chronologically, with optional filters |
| `count_playlists(db)` | Returns the total number of playlists |
| `update_playlist(db, playlist, data)` | Applies a partial `PlaylistUpdate`, commits, and refreshes |
| `delete_playlist(db, playlist)` | Deletes a playlist; the cascade removes its tracks |

## Behavior details

- **Eager loading.** Both `get_playlist_by_slug` and `list_playlists` use
  `selectinload(Playlist.tracks)`, so reading a playlist's tracks does not
  trigger extra queries while building the response.
- **Ordering.** Lists are ordered by `created_at` and then `id`, giving a stable
  chronological order. A playlist's tracks are ordered by `sequence_order`
  through the model relationship.
- **Filters.** `category` matches exactly; `is_featured` matches the boolean.
  `None` means "no filter", not "false".
- **Pagination.** `list_playlists` supports `limit` (default `50`) and `offset`
  (default `0`); the public list endpoint currently uses the defaults.
- **Atomic writes.** Every write commits inside a `try` block and rolls back
  before re-raising a `SQLAlchemyError`, leaving the session usable.
- **Partial updates.** `update_playlist` uses `model_dump(exclude_unset=True)`,
  so only fields present in the payload are changed.

## Used by

- `app/api/v1/endpoints/playlists.py`
- `scripts/ingest_playlist.py`
