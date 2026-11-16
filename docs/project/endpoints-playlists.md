# Playlist endpoints

**Source:** `app/api/v1/endpoints/playlists.py`

These endpoints list playlists and return a single playlist with its tracks.
They only read data.

## `GET /api/v1/playlists`

Lists playlists, without measurements, using `PlaylistSummaryResponse`.

**Query parameters:**

| Parameter | Type | Behavior |
|---|---|---|
| `category` | string, optional | Exact category filter; omitted means no filter |
| `is_featured` | boolean, optional | Featured filter; omitted means no filter |

The service returns playlists ordered chronologically (`created_at`, then `id`)
and eagerly loads their tracks. Because the response model is the summary
schema, tracks are not included in the response. The service accepts `limit` and
`offset`, but this endpoint does not currently expose them, so the defaults
(`50` and `0`) apply.

## `GET /api/v1/playlists/{slug}`

Returns one playlist by its unique slug, using `PlaylistDetailResponse`.

- The response contains the playlist fields plus a `tracks` list of
  `TrackSummaryResponse` objects: lightweight track data without
  `engine_metadata` or `frames`.
- Tracks are ordered by `sequence_order` through the ORM relationship.
- If no playlist has that slug, the endpoint returns HTTP `404` with
  `"Playlist not found"`.

## Example

```bash
curl "http://localhost:8000/api/v1/playlists?category=weather&is_featured=true"
curl "http://localhost:8000/api/v1/playlists/weather-timelapses"
```
