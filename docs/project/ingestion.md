# Data ingestion process

**Sources:** `scripts/ingest_playlist.py`, `scripts/ingest_timelapse.py`,
`app/services/ingestion_service.py`, `app/services/playlist_service.py`,
`docs/ingest_plan.md`

Ingestion is the offline step that turns a folder of NASA frames into a playlist
track in PostgreSQL. It is an administrative workflow: the public API only reads
the stored data, and measurement never runs inside a request.

## Overview

```mermaid
flowchart TD
    Input["Frame folder + profile"] --> CLI["scripts/ingest_timelapse.py"]
    CLI -->|measure_timelapse()| Engine["CV engine output<br/>dataset_info + frames"]
    Engine -->|ingest_timelapse_result()| DB["tracks table<br/>engine_metadata + frames as JSONB"]
```

The process uses two command-line tools:

| Tool | Purpose |
|---|---|
| `scripts/ingest_playlist.py` | Create, list, show, update, and delete playlists |
| `scripts/ingest_timelapse.py` | Measure one frame directory and insert it as a track |

Tracks cannot be created without a playlist. The timelapse CLI never creates a
playlist; it verifies that the destination slug exists before writing.

## Prerequisites

- PostgreSQL is running and `DATABASE_URL` is set through the environment or
  `.env`.
- Dependencies from `requirements.txt` are installed.
- Commands run from the repository root so the scripts can import `app`.
- The tables are created automatically by `init_db()` when the CLI starts. There
  are no migrations to run.

A dry run does not connect to the database, so measurement can be validated even
before the destination playlist exists.

## Input requirements

A track is one folder of frames:

```text
frames-root/
  sea-temperature/
    frame_000_2003-01-01.png
    frame_001_2003-02-01.png
    ...
  lightning/
    frame_000.png
    frame_001.png
    ...
  descriptions.md
```

Rules for a track folder:

- It must contain only frames. A legend, logo, or screenshot in the same folder
  is measured as another frame.
- All frames must have the same pixel dimensions and show the same
  visualization.
- Accepted extensions are `.png`, `.jpg`, `.jpeg`, `.webp`, `.tif`, and
  `.tiff`.
- Frames are ordered by the numbers in their filenames. Use zero-padded numbers,
  and include `YYYY-MM-DD` when possible so the engine records per-frame dates.
- Only one track-level description is stored. Per-frame captions must be
  condensed.

## Choosing a profile

Every track must use one of the 15 registered profiles. The profile determines
the color table, units, thresholds, regions, and sonification hints. The
[profile documentation](cv-engine-profiles.md) lists the IDs and their dataset
types.

- Use the description file when it names the dataset.
- Otherwise use visual cues: GEOS frames are flat 2048×1024 maps with a NASA/GMAO
  logo and date stamp; GIBS frames are flat full-field maps; ECCO2 frames have
  sparse colored current strokes on a base map; globes are spherical views, and
  moving-camera globes have black space around the planet.
- If no profile matches, stop. Adding a profile and color table is a code change,
  not an ingestion task.

## Step-by-step workflow

### 1. Preflight

```bash
python scripts/ingest_playlist.py list --limit 100
python -c "from app.cv_engine import PROFILES; print('\n'.join(sorted(PROFILES)))"
```

Confirm that the database responds, existing playlists are visible, and the
profile list is complete.

### 2. Inventory the frames

List the track folders and count the frames in each one. Open the first, middle,
and last frame to confirm the visualization, the order, and that frames from
different datasets are not mixed.

### 3. Build the editorial plan

Before writing, decide for each track:

| Decision | Rule |
|---|---|
| Playlist | Destination slug; it must exist |
| Profile | One of the 15 registered IDs |
| Slug | Globally unique lowercase ASCII kebab-case, max 100 characters |
| Title | Factual title, max 150 characters |
| Description | Plain text, 1–3 sentences |
| Sequence order | Unique order within the playlist, starting at 0 |
| Event date | Optional ISO date, only when known |
| Public frames URL | Optional public base URL, never a local path |

Do not invent dates, locations, causes, or measurements. Use the description file
and the profile metadata as the source of truth. The
[ingestion plan](../ingest_plan.md) records the playlists and tracks currently
planned for the database.

### 4. Dry-run the track

Measure and save the result without touching the database:

```bash
python scripts/ingest_timelapse.py \
  --dir data_ingest_resources/air-temperature \
  --profile geos-temperature \
  --slug geos-temperature-2026-oct-nov \
  --title "Near-Surface Temperature, 14-Day Forecast" \
  --description "Near-surface air temperature forecast..." \
  --playlist-slug weather-timelapses \
  --sequence-order 0 \
  --dry-run \
  --out /tmp/opencode/ingest/geos-temperature-2026-oct-nov.json
```

Inspect the JSON before proceeding:

- `engine_metadata.profile_id` is the intended profile.
- `len(frames)` matches the number of image files.
- `engine_metadata.warnings` does not indicate a wrong color table.
- The first and last frames are the expected ones.
- `source_metadata.frame_count` matches the folder.

A large `unmatched_fraction`, or warnings that most pixels are outside the color
table, usually means the wrong profile or that compressed frames need `--lossy`.

### 5. Create or reuse the playlist

```bash
python scripts/ingest_playlist.py show --slug weather-timelapses
```

If it does not exist, create it:

```bash
python scripts/ingest_playlist.py create \
  --slug weather-timelapses \
  --title "Weather Timelapses" \
  --category weather \
  --description "Weather forecasts and events seen from space."
```

If it exists, reuse it. Do not delete and recreate a playlist just to change its
metadata.

### 6. Ingest the track

Run the same dry-run command without `--dry-run` and `--out`. Each track is
committed independently; if one write fails, earlier tracks remain in the
database.

Ingest tracks sequentially, not concurrently against the same playlist.

### 7. Verify

```bash
python scripts/ingest_playlist.py show --slug weather-timelapses
curl -s "http://localhost:8000/api/v1/playlists/weather-timelapses"
curl -s "http://localhost:8000/api/v1/tracks/geos-temperature-2026-oct-nov"
```

Confirm the track list, IDs, and sequence order.

## Playlist CLI

```bash
# Create (slug, title, and category are required)
python scripts/ingest_playlist.py create \
  --slug earth-timelapses \
  --title "Earth Timelapses" \
  --category timelapse \
  [--description "..."] \
  [--cover-url "https://..."] \
  [--featured]

# List and filter
python scripts/ingest_playlist.py list \
  [--category timelapse] \
  [--featured | --no-featured] \
  [--limit 50] \
  [--offset 0]

# Inspect one playlist and its tracks
python scripts/ingest_playlist.py show --slug earth-timelapses

# Update editorial fields; the slug cannot be changed
python scripts/ingest_playlist.py update \
  --slug earth-timelapses \
  [--title "..."] \
  [--description "..."] \
  [--category "..."] \
  [--cover-url "..."] \
  [--featured | --no-featured]

# Delete a playlist and all of its tracks
python scripts/ingest_playlist.py delete --slug earth-timelapses --yes
```

Deletion cascades to every track in the playlist and requires explicit
confirmation.

## Timelapse CLI

Required arguments: `--dir`, `--profile`, `--title`, `--slug`,
`--playlist-slug`.

| Option | Meaning |
|---|---|
| `--dir` | Frame folder, not the frames root |
| `--profile` | One of the 15 registered profile IDs |
| `--slug` | Unique track slug |
| `--title` | Track title |
| `--playlist-slug` | Existing destination playlist |
| `--description` | Plain-text description |
| `--sequence-order` | Order within the playlist, default `0` |
| `--event-date` | ISO 8601 date or datetime, optional |
| `--frames-url` | Public base URL of the images, stored as `frames_base_url` |
| `--frames-ext` | Public image extension when it differs, stored as `frames_extension` |
| `--lossy` | Raise color tolerance for compressed or video-derived frames |
| `--replace` | Overwrite an existing track with the same slug |
| `--dry-run` | Measure and exit before importing the database layer |
| `--out` | Write the track JSON as it would be ingested |

## What gets stored

The script builds `source_metadata` automatically:

```json
{
  "source": "<profile.source>",
  "profile_id": "<profile.id>",
  "topic": "<profile.topic>",
  "frames_directory": "<folder name>",
  "frame_count": 32,
  "frames_base_url": "<only with --frames-url>",
  "frames_extension": "<only with --frames-ext>"
}
```

It stores only the folder name, never the full local path.

The rest of the track comes from the engine:

| Column | Contents |
|---|---|
| `engine_metadata` | The engine's `dataset_info`: unit, value range, thresholds, feature ranges, trends, regions, hints, warnings |
| `frames` | One entry per frame with full-map features, regional features, top region, and grid |

Measurement data is never written by hand. See
[services-ingestion.md](services-ingestion.md) for the service behavior and
[cv-engine-overview.md](cv-engine-overview.md) for the payload contract.

## Video and compressed sources

The timelapse CLI does not extract frames from video. Extract them first:

```bash
python -c "from pathlib import Path; from app.cv_engine.video import extract_frames; print(extract_frames(Path('video.mp4'), Path('frames-dir'), every=1.0))"
```

Then ingest the extracted folder with `--lossy`. Source PNGs downloaded directly
from NASA do not need it. Do not use `--lossy` for `ecco2-sst`: that profile
already has a wider built-in tolerance, which `--lossy` would reduce.

## Safety rules

- Dry-run every track and review the JSON before writing.
- Create the playlist before its tracks.
- Use only registered profile IDs.
- Do not invent editorial facts.
- Use `--replace` only to update the same track intentionally; it can move the
  track to another playlist.
- Do not delete a playlist without explicit confirmation.
- Keep slugs stable after ingestion; they are permanent identifiers.
- Ingest sequentially and use the CLIs instead of raw SQL.
- Do not edit profiles, color tables, or engine code during ingestion.

## AI-agent skill

A custom skill, `spotiearth-timelapse-ingest`, packages this process for AI
agents. It reads a description file, maps folders to profiles, generates the
editorial metadata, and drives these CLIs to create playlists and insert all
tracks. See [ingestion-agent-skill.md](ingestion-agent-skill.md).
