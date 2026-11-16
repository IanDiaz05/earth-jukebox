# Track endpoints

**Source:** `app/api/v1/endpoints/tracks.py`

This module exposes the detail view for a single track. There is no endpoint
that lists tracks directly; tracks are listed through their playlist.

## `GET /api/v1/tracks/{slug}`

Returns one track by its unique slug using `TrackDetailResponse`.

The response contains everything the frontend needs to synthesize audio on the
client:

- Editorial fields: `slug`, `title`, `description`, `sequence_order`,
  `event_date`.
- `source_metadata`: where the frames come from.
- `engine_metadata`: the dataset information produced by the engine, including
  units, ranges, thresholds, trends, regions, and sonification hints.
- `frames`: one entry per frame with full-map features, regional features, the
  top region, and the exploration grid.

If no track has that slug, the endpoint returns HTTP `404` with
`"Track not found"`.

## Distinct from the playlist detail

The playlist detail returns `TrackSummaryResponse`, which omits
`engine_metadata` and `frames`. Only this endpoint returns the full measurement
payload.

## Example

```bash
curl "http://localhost:8000/api/v1/tracks/geos-temperature-2026-oct-nov"
```
