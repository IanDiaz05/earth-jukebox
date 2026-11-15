---
name: spotiearth-timelapse-ingest
description: Insert NASA timelapse frame folders into SpotiEarth playlists and tracks with the ingest CLIs; generate slugs, titles, descriptions, categories, and playback order from a markdown or text description file.
---

# SpotiEarth Timelapse Ingestion

Use the two offline administrative CLIs to turn a directory of frame folders into
playlists and tracks in PostgreSQL:

- `scripts/ingest_playlist.py` — create, list, show, update, and delete playlists.
- `scripts/ingest_timelapse.py` — measure one frame directory with the CV engine
  and insert one track into an existing playlist.

The agent's job is to read the supplied description file, identify each timelapse,
choose the correct engine profile, generate editorial metadata, and insert all
tracks without inventing facts or overwriting existing data.

## When to Use

Use this skill when:

- The user provides a directory of frame folders and a `.md` or `.txt` file with
  one description per timelapse.
- The user asks to add, remeasure, or fix timelapse tracks.
- The user asks to create or manage the playlists that group those tracks.
- The user asks for slugs, titles, descriptions, categories, or playback order for
  timelapses.

Do not use this skill for public image uploads or synchronous ML endpoints. The
project deliberately keeps ingestion offline and administrative.

## Input Contract

### Frames root

The input is normally a directory whose immediate children are track folders:

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

Rules:

- One immediate child folder containing images is one track.
- If the supplied root contains image files directly, treat the root itself as a
  single track and do not also treat its subfolders as tracks unless the user says
  so.
- Do not recurse into deeper levels unless the user explicitly maps those folders
  as separate tracks.
- A track folder must contain only frames. An image such as a color bar, logo, or
  screenshot in the same folder will be measured as another frame. Move it out.
- All frames in one track must have the same pixel dimensions and belong to the
  same visualization.
- Accepted extensions: `.png`, `.jpg`, `.jpeg`, `.webp`, `.tif`, `.tiff`.
- Frames are ordered numerically by the digits in their filenames. Use zero-padded
  frame numbers and, when possible, put `YYYY-MM-DD` in the filename so the engine
  can record per-frame dates.

### Description file

The description file describes tracks, not individual frames. It may be Markdown
or plain text. A recommended structure is shown at the end of this skill, but prose
is acceptable.

Only one description is stored per track. If the file has a caption for every
frame, condense those captions into one track-level description; per-frame editorial
text is not part of the track schema.

The agent must:

1. Read the whole file, not only the first paragraph.
2. Match each description to a track folder by folder name, slug, heading, title,
   or an explicit `folder:`/`directory:` field.
3. Extract any supplied factual metadata: title, description, category, event date,
   sequence order, source, public frames URL, and public frames extension.
4. Use the description file as the source of truth for editorial facts. Do not
   invent locations, dates, causes, or measurements that are not present there or
   in the engine profile.
5. If a description cannot be matched unambiguously, ask the user instead of
   guessing. If the file is a one-to-one ordered list and the order is obvious,
   state the assumption in the final report.

If no description file exists, the agent may generate a conservative description
from the profile metadata and the frame count/date range, but it must flag those
descriptions as generated.

### Output contract

For every track, the agent must decide:

- `--dir`: absolute or repo-relative path to the track folder.
- `--profile`: one of the 15 supported profile IDs.
- `--slug`: globally unique, lowercase ASCII kebab-case.
- `--title`: editorial title, max 150 characters.
- `--description`: factual plain-text description.
- `--playlist-slug`: destination playlist, which must already exist.
- `--sequence-order`: unique order within the playlist, starting at 0.
- `--event-date`: optional ISO date, only when known.
- `--frames-url`: optional public base URL, never a local path.
- `--frames-ext`: optional public extension if it differs from the measured frames.
- `--lossy`: only for compressed/video-derived frames, with the exception noted
  below.
- `--replace`: only when intentionally updating an existing track.

## Non-Negotiable Rules

1. **Dry-run every track before writing to the database.** Use `--dry-run --out`
   and inspect the JSON. Do not ingest a track whose measurement failed or whose
   warnings indicate the wrong profile.
2. **A playlist must exist before a track is ingested.** `ingest_timelapse.py` never
   creates playlists.
3. **Never invent a profile ID.** Use only the 15 IDs in the profile catalog.
4. **Never invent editorial facts.** If the description file does not say it, do not
   add it.
5. **Never use `--replace` blindly.** It overwrites the track's editorial fields and
   measurements, and it can move the track to another playlist.
6. **Never delete a playlist without explicit confirmation.** Deletion cascades to
   all of its tracks. There is no track-delete CLI.
7. **Slugs are permanent identifiers.** Do not change a slug after ingestion unless
   the user explicitly asks to replace the resource.
8. **Keep descriptions plain text.** No Markdown, bullets, links, emojis, or line
   breaks inside the `--description` value.
9. **Default editorial language is English.** Use another language when the
   description file is written in that language and the user has not asked for
   English, or when the user explicitly requests it. Slugs and categories are always
   English lowercase ASCII.
10. **Run batch ingestion sequentially.** Do not run concurrent writers against the
    same playlist.
11. **Use the CLIs for ingestion.** Do not insert, update, or delete playlists/tracks
    with raw SQL unless the user explicitly requests a database operation outside
    these tools.
12. **Never edit engine code, profiles, or color tables during ingestion.** A new
    visualization is a code change, not an ingestion task.

## Workflow

### 1. Preflight

Run from the repository root so the scripts can import `app`:

```bash
python scripts/ingest_playlist.py list --limit 100
python -c "from app.cv_engine import PROFILES; print('\n'.join(sorted(PROFILES)))"
```

Confirm:

- PostgreSQL is running and `DATABASE_URL` is set (via `.env` or the environment).
- The Python environment has `requirements.txt` installed.
- Existing playlists are visible.
- The profile list matches the catalog below.
- The ingestion commands call `init_db()` and create the tables if they are missing;
  `--dry-run` skips the database entirely. There are no migrations to run.

`--dry-run` does not connect to the database, so measurement can be validated even
before the playlist exists.

### 2. Inventory the input

List immediate track folders and count their frames:

```bash
find "$INPUT_ROOT" -mindepth 1 -maxdepth 1 -type d | sort
find "$TRACK_DIR" -maxdepth 1 -type f \
  \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \
     -o -iname '*.webp' -o -iname '*.tif' -o -iname '*.tiff' \) | wc -l
```

Open the first, middle, and last frame of each track to confirm the visualization,
the frame order, and that the frames are not mixed. Do not rely only on folder names.

### 3. Read and map descriptions

Build a table before writing anything:

| Folder | Profile | Slug | Title | Category | Order | Event date |
|---|---|---|---|---|---|---|
| `sea-temperature` | `sst-anomaly` | `sst-anomaly-2003-2026` | Sea Surface Temperature Anomalies 2003-2026 | `climate` | 0 | — |

If a folder has no description, either generate a conservative one and mark it, or
ask the user. If two descriptions match the same folder, stop and ask.

### 4. Choose the profile

Use the description file when it names the dataset. Otherwise use the visual cues
and filename hints in the profile catalog. If two profiles are plausible, compare
the layout:

- Flat 2048x1024 map with a NASA/GMAO logo and a date stamp: GEOS family.
- Flat global map with full-field color and no GEOS logo: GIBS family
  (`imerg-precipitation`, `sst-anomaly`, `ndvi-vegetation`).
- Black background with sparse colored current strokes: `ecco2-sst`.
- Square globe with a fixed camera: `globe-co2`.
- Globe with black space and a moving camera: `globe-lightning` or
  `globe-ocean-temperature`.

If the visualization has no supported profile, do not improvise. Stop, report which
folders were skipped, and say that a profile and color table must be added under
`app/cv_engine/`.

### 5. Generate editorial metadata

Apply the standards below. Prefer a supplied title/description after normalizing
Markdown and whitespace. Otherwise derive them from the profile and the known scope.
Check hard limits before calling the CLI:

- Track title ≤ 150 characters; target ≤ 70.
- Track slug ≤ 100 characters; target ≤ 60.
- Playlist title ≤ 150 characters.
- Playlist slug ≤ 100 characters.
- Category ≤ 50 characters.
- Cover URL ≤ 255 characters.

### 6. Dry-run every track

Use a temporary output directory such as `/tmp/opencode/ingest/`:

```bash
python scripts/ingest_timelapse.py \
  --dir "$TRACK_DIR" \
  --profile "$PROFILE" \
  --slug "$TRACK_SLUG" \
  --title "$TRACK_TITLE" \
  --description "$TRACK_DESCRIPTION" \
  --playlist-slug "$PLAYLIST_SLUG" \
  --sequence-order "$ORDER" \
  [--event-date "$EVENT_DATE"] \
  [--frames-url "$FRAMES_URL"] \
  [--frames-ext "$FRAMES_EXT"] \
  [--lossy] \
  --dry-run \
  --out "/tmp/opencode/ingest/$TRACK_SLUG.json"
```

The bracketed arguments are placeholders: remove the brackets and the option
entirely when the value is unknown or not needed.

Inspect the JSON:

```bash
python - "/tmp/opencode/ingest/$TRACK_SLUG.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
info = payload["engine_metadata"]
print("profile:", info["profile_id"])
print("unit:", info["unit"], "range:", info["value_range"])
print("frames:", len(payload["frames"]), "expected:", payload["source_metadata"]["frame_count"])
print("warnings:", info["warnings"])
PY
```

Proceed only when:

- `profile_id` is the intended profile.
- `len(frames)` equals the number of image files in the folder.
- No warning indicates a profile/color-table mismatch.
- The first and last frame are the expected ones.

Warnings such as `Region ... has insufficient data: skipped` are not fatal; record
them. A large `unmatched_fraction` or warnings that most pixels are outside the
table usually mean the wrong profile or that `--lossy` is needed.

### 7. Create or reuse playlists

Check before creating:

```bash
python scripts/ingest_playlist.py show --slug "$PLAYLIST_SLUG"
```

If it does not exist, create it:

```bash
python scripts/ingest_playlist.py create \
  --slug "$PLAYLIST_SLUG" \
  --title "$PLAYLIST_TITLE" \
  --category "$CATEGORY" \
  --description "$PLAYLIST_DESCRIPTION"
```

If it exists with the same intent, reuse it. Update only the fields the user asked
to change. Do not delete and recreate a playlist merely to change its title,
description, category, or featured flag.

### 8. Ingest tracks

Run the same command without `--dry-run`:

```bash
python scripts/ingest_timelapse.py \
  --dir "$TRACK_DIR" \
  --profile "$PROFILE" \
  --slug "$TRACK_SLUG" \
  --title "$TRACK_TITLE" \
  --description "$TRACK_DESCRIPTION" \
  --playlist-slug "$PLAYLIST_SLUG" \
  --sequence-order "$ORDER"
```

Each track is committed independently. If one write fails, earlier tracks remain
inserted; fix and rerun only the failed track, using `--replace` only if its slug was
already written.

For many tracks, build a plan in `/tmp/opencode/ingest/plan.json` and invoke the CLI
with a list-form subprocess rather than interpolating titles and descriptions into a
shell string. This avoids quoting bugs with apostrophes, accents, and long text:

```python
import subprocess

command = [
    "python", "scripts/ingest_timelapse.py",
    "--dir", track_dir,
    "--profile", profile,
    "--slug", slug,
    "--title", title,
    "--description", description,
    "--playlist-slug", playlist_slug,
    "--sequence-order", str(order),
]
if event_date:
    command += ["--event-date", event_date]
if frames_url:
    command += ["--frames-url", frames_url]
if frames_ext:
    command += ["--frames-ext", frames_ext]
if lossy:
    command.append("--lossy")
subprocess.run(command, check=True)
```

### 9. Verify

```bash
python scripts/ingest_playlist.py show --slug "$PLAYLIST_SLUG"
```

Confirm the track list, IDs, and `sequence_order`. If the API is running:

```bash
curl -s "http://localhost:8000/api/v1/playlists/$PLAYLIST_SLUG"
curl -s "http://localhost:8000/api/v1/tracks/$TRACK_SLUG"
```

### 10. Report

Return a concise report:

- Playlist slug, ID, title, category, and track count.
- Each track's slug, ID, profile, frame count, and sequence order.
- Any engine warnings.
- Any skipped folders and the reason.
- Any generated descriptions or assumptions.

## Editorial Standards

### Slugs

Format: lowercase ASCII kebab-case matching `[a-z0-9]+(-[a-z0-9]+)*`.

The database does not enforce that pattern, so validate it yourself before calling
the CLI.

- Use the profile ID or the visualization variable as the base.
- Add a scope to distinguish tracks: date range, year, forecast window, region, or
  source. Examples: `sst-anomaly-2003-2026`, `geos-temperature-14-day`,
  `globe-co2-2020`, `globe-lightning-2017-2023`.
- Transliterate accents and replace symbols: `CO₂` → `co2`, `PM2.5` → `pm25`,
  `NOx` → `nox`, `O₃` → `o3`.
- No underscores, spaces, uppercase, leading/trailing hyphens, or double hyphens.
- Track slugs are globally unique across all playlists, not unique per playlist.
  Before choosing one, inspect the playlists that could contain it with `show`; if
  you cannot rule out a collision, use a more specific slug.
- Playlist slugs are also globally unique.
- If a slug already exists for different content, choose a more specific slug rather
  than a numeric suffix. Use `-2` only as a last resort.

Playlist slug patterns:

| Playlist scope | Slug | Title | Category |
|---|---|---|---|
| Mixed collection | `earth-timelapses` | Earth Timelapses | `timelapse` |
| Weather | `weather-timelapses` | Weather Timelapses | `weather` |
| Water | `water-timelapses` | Water Timelapses | `water` |
| Oceans | `oceans-timelapses` | Ocean Timelapses | `oceans` |
| Air quality | `air-quality-timelapses` | Air Quality Timelapses | `air-quality` |
| Agriculture | `agriculture-timelapses` | Agriculture Timelapses | `agriculture` |
| Climate | `climate-timelapses` | Climate Timelapses | `climate` |

### Titles

- Pattern: `<what the visualization shows> <scope>`.
- Use Title Case, no trailing period, no quotes, no Markdown.
- Include a date range or region only when known.
- Do not copy technical parentheticals such as `(GHRSST MUR25)` unless they are
  needed to distinguish two tracks.
- Do not copy the engine's `label` or `hints.words`: they are Spanish frontend
  hints, not editorial titles.
- Do not put “Timelapse” in every track title; the playlist already provides that
  context.
- Titles must be unique within a playlist. Distinguish them with scope.

Examples:

| Profile | Example title |
|---|---|
| `sst-anomaly` | Sea Surface Temperature Anomalies 2003-2026 |
| `imerg-precipitation` | Global Precipitation Rate 2020 |
| `ndvi-vegetation` | Global Vegetation Index 2024 |
| `geos-temperature` | Near-Surface Temperature, 14-Day Forecast |
| `geos-wind` | Near-Surface Wind Speed, 14-Day Forecast |
| `geos-precipitation` | Global Precipitation Forecast |
| `geos-humidity` | Near-Surface Humidity Forecast |
| `geos-pm25` | Fine Particulate Matter PM2.5 |
| `geos-o3` | Near-Surface Ozone |
| `geos-co` | Carbon Monoxide and Smoke |
| `geos-nox` | Nitrogen Oxides |
| `ecco2-sst` | Ocean Currents and Sea Temperature |
| `globe-co2` | Atmospheric Carbon Dioxide |
| `globe-lightning` | Lightning Over Earth 2017-2023 |
| `globe-ocean-temperature` | Ocean Currents Temperature |

### Descriptions

Write 1–3 sentences, normally 120–320 characters:

1. What the visualization shows, including variable, unit, region, and time span.
2. What changes or what to notice.
3. Source/context only when it adds useful information.

Rules:

- Use present tense and plain, factual language.
- Preserve units from the profile. Do not claim physical units for relative-index
  profiles.
- Do not invent causes, impacts, dates, or locations.
- Do not copy credits, instructions, or boilerplate from the description file.
- Replace line breaks with spaces. Remove Markdown.
- If the source description is long, summarize faithfully; do not paste it whole.
- If the source description is vague, add only profile metadata and flag it as
  generated.

Example for `sst-anomaly`:

> Global sea surface temperature anomalies from NASA's GHRSST MUR25 dataset, shown
> across two decades of observations. Blue areas are cooler than average and red
> areas are warmer, revealing where ocean heat has shifted over time.

### Categories

The `category` field belongs to the playlist, not the track. It is a free string in
the database, but use the canonical values below so the public API filters work
consistently. Categories are lowercase kebab-case and max 50 characters.

| Engine topic | Category | Profiles |
|---|---|---|
| Weather | `weather` | `geos-temperature`, `geos-wind`, `globe-lightning` |
| Water resources | `water` | `imerg-precipitation`, `geos-precipitation`, `geos-humidity` |
| Ocean warming | `climate` | `sst-anomaly` |
| Carbon dioxide | `climate` | `globe-co2` |
| Ocean currents | `oceans` | `ecco2-sst`, `globe-ocean-temperature` |
| Air quality | `air-quality` | `geos-pm25`, `geos-o3`, `geos-co`, `geos-nox` |
| Agriculture | `agriculture` | `ndvi-vegetation` |

Default grouping:

- If the user supplies a playlist slug, use it.
- If every track maps to one category, create `<category>-timelapses` with that
  category.
- If the input mixes categories and the user did not ask to split, create
  `earth-timelapses` with category `timelapse`.
- If the user asks to split by category, create one playlist per category and assign
  each track to the matching playlist.

### Sequence order and event date

- Preserve the order given in the description file.
- If no order is given, sort track folders naturally by name and assign contiguous
  integers starting at 0 within each playlist.
- When appending to an existing playlist, start after the current maximum order.
- `--event-date` is optional and must be ISO 8601 (`YYYY-MM-DD` or a full ISO
  datetime). Use the event date supplied in the description file or the latest frame
  date when that is the intended reference. If unknown, omit it. Never use the
  ingestion date.

### Playlist metadata

- Playlist title: short collection name, e.g. “Earth Timelapses” or “Weather
  Timelapses”.
- Playlist description: 1–2 sentences about the collection, not a copy of one
  track's description.
- `--cover-url`: only a public image URL supplied by the user. Never a local path.
- `--featured`: leave false unless the user explicitly asks to feature the playlist.
- Playlist slugs cannot be changed with the update command. If the slug is wrong,
  confirm with the user before creating/deleting anything.

## Profile Catalog

Use only these IDs. The `--profile` argument is case-sensitive.

| Profile ID | Choose it when | Category | Example slug base |
|---|---|---|---|
| `imerg-precipitation` | GPM IMERG global rain-rate map; flat map, full-field rain colors, no NASA/GMAO logo | `water` | `imerg-precipitation` |
| `sst-anomaly` | GHRSST MUR25 sea surface temperature anomalies; flat ocean map, blue-white-red diverging scale | `climate` | `sst-anomaly` |
| `ndvi-vegetation` | MODIS Terra NDVI monthly; flat land map, green vegetation, ocean has no data | `agriculture` | `ndvi-vegetation` |
| `geos-temperature` | GEOS-FP near-surface temperature; 2048x1024 flat map, NASA/GMAO logo and date/time stamp | `weather` | `geos-temperature` |
| `geos-wind` | GEOS-FP near-surface wind speed; same GEOS-FP layout as temperature | `weather` | `geos-wind` |
| `geos-precipitation` | GEOS-FP precipitation and clouds; same GEOS-FP layout | `water` | `geos-precipitation` |
| `geos-humidity` | GEOS-FP near-surface specific humidity; same GEOS-FP layout | `water` | `geos-humidity` |
| `geos-pm25` | GEOS-CF PM2.5 particulate matter; 2048x1024 flat map with logo/date | `air-quality` | `geos-pm25` |
| `geos-o3` | GEOS-CF near-surface ozone; same GEOS-CF layout | `air-quality` | `geos-o3` |
| `geos-co` | GEOS-CF carbon monoxide; same GEOS-CF layout | `air-quality` | `geos-co` |
| `geos-nox` | GEOS-CF nitrogen oxides; same GEOS-CF layout | `air-quality` | `geos-nox` |
| `ecco2-sst` | ECCO2 global currents colored by sea surface temperature; background map with sparse colored current strokes | `oceans` | `ecco2-sst` |
| `globe-co2` | SVS 5115 volumetric atmospheric CO₂; square globe, fixed camera, orange-brown haze | `climate` | `globe-co2` |
| `globe-lightning` | SVS 5011 lightning from the ISS; globe with black space, moving camera, yellow flashes | `weather` | `globe-lightning` |
| `globe-ocean-temperature` | SVS 5425 Perpetual Ocean 2 temperature version; globe with black space, moving camera, colored currents | `oceans` | `globe-ocean-temperature` |

Unsupported visualizations:

- Perpetual Ocean “beauty” frames: color encodes depth, not a measured variable.
- Perpetual Ocean salinity: the gray middle of the bar matches land, ice, and
  clouds.
- Any other visualization without a supported color table.

Skip these and report that a new `DatasetProfile` and color table are required in
`app/cv_engine/`. Adding a profile is a code change, not an ingestion task.

### Color tables (colormaps)

Every profile measures pixels against its `colormap_file`, an official XML color
table stored in `app/cv_engine/colormaps/`. The agent never passes a color table on
the command line and never edits one while ingesting.

Lookup order, implemented by `load_lut()` in `app/cv_engine/pipeline.py`:

1. `app/cv_engine/colormaps/<profile.colormap_file>`.
2. If that file is missing, `<parent of --dir>/<profile.colormap_file>`.

The fallback lets a table travel with a downloaded dataset, but the filename must
match the profile exactly (for example `GPM_Precipitation_Rate.xml` for
`imerg-precipitation`); a table under any other name is ignored. If a profile
declares a `legend` instead of a `colormap_file`, the legend drawn in the frames is
used and no XML is read.

To build a new table, use `scripts/colorbar_to_xml.py` (flat maps) or
`scripts/haze_ramp_to_xml.py` (globes). Registering the profile in `PROFILES` remains
out of scope for this skill.

### Description accuracy notes

- `globe-co2` and `globe-lightning` use a relative 0–1 index, not ppm or a count.
  Do not describe them as physical concentrations or flash counts.
- `ecco2-sst` measures only the colored current strokes; data coverage is sparse.
  Do not imply full-map temperature coverage.
- Globes have no geographic regions in the engine output; positions are relative to
  the visible planet. Do not promise per-continent breakdowns.
- Moving-camera globes measure only the visible part of the planet.
- GEOS profiles mask the logo and date/time boxes. Do not describe those as data.

## CLI Reference

### `scripts/ingest_playlist.py`

```bash
# Create (all three required)
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

# Update editorial fields (slug cannot be changed)
python scripts/ingest_playlist.py update \
  --slug earth-timelapses \
  [--title "..."] \
  [--description "..."] \
  [--category "..."] \
  [--cover-url "..."] \
  [--featured | --no-featured]

# Delete a playlist AND all of its tracks (explicit confirmation required)
python scripts/ingest_playlist.py delete --slug earth-timelapses --yes
```

### `scripts/ingest_timelapse.py`

Required arguments: `--dir`, `--profile`, `--title`, `--slug`, `--playlist-slug`.

```bash
python scripts/ingest_timelapse.py \
  --dir frames/sea-temperature \
  --profile sst-anomaly \
  --slug sst-anomaly-2003-2026 \
  --title "Sea Surface Temperature Anomalies 2003-2026" \
  --description "Global sea surface temperature anomalies from NASA's GHRSST MUR25 dataset..." \
  --playlist-slug earth-timelapses \
  --sequence-order 0 \
  [--event-date 2026-01-01] \
  [--frames-url "https://cdn.example.com/timelapses/sea-temperature"] \
  [--frames-ext webp] \
  [--replace] \
  [--lossy] \
  [--dry-run] \
  [--out /tmp/opencode/ingest/sst-anomaly-2003-2026.json]
```

Option notes:

- `--dir`: path to the frame folder, not the frames root.
- `--profile`: one of the 15 IDs above.
- `--playlist-slug`: required; the playlist must exist for actual ingestion.
  `--dry-run` does not check it, so you can validate measurements before creating
  the playlist.
- `--description`: optional in the CLI, but always provide one in this workflow.
- `--sequence-order`: default `0`; duplicate orders are ordered by track ID.
- `--event-date`: parsed with `datetime.fromisoformat`; quote it.
- `--frames-url`: public base URL only; trailing slash is stripped and it is stored
  as `frames_base_url` in `source_metadata`.
- `--frames-ext`: public extension if different, e.g. `webp`; stored as
  `frames_extension`.
- `--replace`: overwrites an existing track with the same slug, preserving its ID and
  slug; it also moves the track if `--playlist-slug` differs.
- `--lossy`: raises the CIELAB color tolerance to ΔE 18 for compressed or
  video-derived frames. Omit it for source PNGs downloaded directly from SVS/GIBS. Do
  not use it for `ecco2-sst`, whose built-in tolerance is already 30 and would be
  reduced to 18.
- `--dry-run`: measures and prints warnings, then exits before importing the database
  layer. It does not create or check the playlist.
- `--out`: writes the editorial data, `engine_metadata`, and `frames` as JSON. Use it
  with `--dry-run` for review.

There is no CLI to update or delete a single track. Use `--replace` to rewrite a
track after confirming it is the same resource. Deleting one track requires direct
database work or a new API endpoint, with explicit user approval; do not delete its
playlist just to remove one track.

### What the engine stores automatically

`source_metadata` is built by the script, not passed on the command line:

```json
{
  "source": "<profile.source>",
  "profile_id": "<profile.id>",
  "topic": "<profile.topic>",
  "frames_directory": "<basename of --dir>",
  "frame_count": 32,
  "frames_base_url": "<only when --frames-url is passed>",
  "frames_extension": "<only when --frames-ext is passed>"
}
```

The last two keys are omitted when their options are not passed.

`engine_metadata` is `dataset_info` from the CV engine, including `schema_version`
(currently `2.2`), `profile_id`, `topic`, `kind`, `projection`, `unit`,
`value_range`, `thresholds`, `hints`, `frames_count`, `feature_stats`, `trends`,
`regions`, and `warnings`.

`frames` is the per-frame list with `frame_index`, `frame_id`, `date` (when the
filename contains `YYYY-MM-DD`), `features`, `regions`, `top_region` (when regions
exist), and `grid`.

The engine, not the agent, produces all measurement data. Never hand-write
`engine_metadata` or `frames`.

## Video and screenshot sources

The CLI does not extract frames from video. Extract them first, then ingest with
`--lossy`:

```bash
python -c "from pathlib import Path; from app.cv_engine.video import extract_frames; print(extract_frames(Path('<video.mp4>'), Path('<frames-dir>'), every=1.0))"
```

`every` is the number of seconds between extracted frames; `limit` (optional) caps
the count. Extracted frames are compressed, so they normally need `--lossy`.

## Error Handling

| Message or symptom | Cause | Action |
|---|---|---|
| `No playlists found.` | Empty database | Create a playlist first. |
| `Playlist not found: <slug>` | Wrong or missing playlist slug | Create it or correct `--playlist-slug`. |
| `A playlist with slug '<slug>' already exists.` | Duplicate playlist slug | Use `show` and reuse it, or choose another slug. |
| `Ya existe una pista con el slug '<slug>'.` | Duplicate track slug | Choose a new slug, or use `--replace` only if it is the same track. |
| `Engine error: No images in <dir>` | Empty folder or wrong extensions | Check the frames and accepted extensions. |
| `Engine error: <file> is (h, w), different from the first frame` | Mixed frame sizes | Resize or separate the frames; do not ingest. |
| `Engine error: Could not read image: <file>` | Corrupt/unsupported file | Remove or replace it. |
| `Engine error: ... color table ...` | Profile/colormap mismatch or a missing XML | Recheck the profile; confirm `app/cv_engine/colormaps/` or the parent of `--dir` holds the exact `colormap_file` name. Do not force it. |
| `Database error: ...` | PostgreSQL down or bad `DATABASE_URL` | Start the database and check `.env`. |
| `Error: directory does not exist` | Wrong `--dir` | Use the track folder path. |
| `Error: path is not a directory` | Passed a file | Pass the containing folder. |
| `Deletion requires --yes.` | Safety guard | Confirm with the user before adding `--yes`. |
| `No fields to update.` | Empty update command | Provide at least one field. |
| Large `unmatched_fraction` or “pixels outside the table” warning | Wrong profile or compressed frames | Try the correct profile, then `--lossy` for compressed frames (not for `ecco2-sst`). |
| `Region ... has insufficient data: skipped` | Region has no usable pixels in at least one frame | Not fatal; record the warning. |

## Safety Checklist

Before writing:

- [ ] Every track folder has a supported profile.
- [ ] Every track folder contains only frames of one visualization and one size.
- [ ] The profile's color table resolves to a packaged XML or an exact-name XML beside
      the dataset, and no colormap was edited.
- [ ] Every track has a unique, valid slug.
- [ ] Every title is unique within its playlist and ≤ 150 characters.
- [ ] Every description is plain text, factual, and 1–3 sentences.
- [ ] Every playlist slug exists or is about to be created.
- [ ] Sequence orders are unique and contiguous within each playlist.
- [ ] `--event-date` is known and ISO-formatted, or omitted.
- [ ] `--frames-url` is public, or omitted.
- [ ] `--frames-ext` is used only when the public extension differs.
- [ ] `--lossy` is used only for compressed frames, not for `ecco2-sst`.
- [ ] Every track passed `--dry-run`.
- [ ] No `--replace` or playlist deletion is used without confirmation.

## Recommended Description File Template

```markdown
# Timelapse descriptions

## sea-temperature

- folder: sea-temperature
- title: Sea Surface Temperature Anomalies 2003-2026
- category: climate
- event_date: 2026-01-01
- sequence_order: 0
- source: NASA GIBS GHRSST MUR25
- frames_url: https://cdn.example.com/timelapses/sea-temperature
- frames_ext: webp
- description: >
    Global sea surface temperature anomalies from NASA's GHRSST MUR25 dataset,
    shown across two decades of observations. Blue areas are cooler than average
    and red areas are warmer, revealing where ocean heat has shifted over time.

## lightning

- folder: lightning
- title: Lightning Over Earth 2017-2023
- category: weather
- sequence_order: 1
- description: >
    Lightning events detected from the International Space Station between 2017
    and 2023. Yellow flashes trace storms as the camera moves around the planet.
```

Only `folder` and `description` are strictly necessary if the agent generates the
rest. A free-form prose file with one heading per folder is also acceptable.
