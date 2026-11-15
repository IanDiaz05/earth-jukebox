# SpotiEarth ingest plan

Implementation plan for ingesting all supported timelapses from
`data_ingest_resources/` into PostgreSQL via `scripts/ingest_playlist.py` and
`scripts/ingest_timelapse.py`.

Source of truth for factual metadata: `data_ingest_resources/DATASETS.md` and
`data_ingest_resources/README.md`. Frame images were not inspected; folder names
and dataset docs are assumed correctly labeled.

**Status:** plan only — no CLI ingestion has been run yet.

**Editorial language:** English (API/product convention). `DATASETS.md` is
Spanish; switch track titles/descriptions to Spanish on request. Slugs and
categories stay English lowercase ASCII.

---

## Summary

| Item | Count |
|---|---|
| Playlists to create | 6 |
| Tracks to ingest | 15 |
| Folders skipped (no profile) | 2 |
| Non-track directories ignored | 1 (`colormaps/`) |

Grouping rule: same folder-name prefix shares a playlist when the category
matches (`air-quality-*`, `ocean-tour-*`). Remaining folders are grouped by
engine category from the timelapse-ingest skill.

---

## Preflight (before any write)

```bash
python scripts/ingest_playlist.py list --limit 100
python -c "from app.cv_engine import PROFILES; print('\n'.join(sorted(PROFILES)))"
```

Confirm `DATABASE_URL` is set and PostgreSQL is up. Dry-runs do not need the DB.

Suggested dry-run output dir: `/tmp/opencode/ingest/`.

---

## Playlists to create

Create these six playlists first (empty), then ingest tracks into them.

### 1. `air-quality-timelapses`

| Field | Value |
|---|---|
| **slug** | `air-quality-timelapses` |
| **title** | Air Quality Timelapses |
| **category** | `air-quality` |
| **description** | Near-surface air composition from NASA GEOS-CF model estimates over about two weeks in late 2026. Tracks cover fine particles, ozone, carbon monoxide, and nitrogen oxides. |
| **featured** | false |
| **cover-url** | omit |

### 2. `weather-timelapses`

| Field | Value |
|---|---|
| **slug** | `weather-timelapses` |
| **title** | Weather Timelapses |
| **category** | `weather` |
| **description** | Near-surface weather fields from NASA GEOS-FP forecasts and lightning observed from the International Space Station. |
| **featured** | false |
| **cover-url** | omit |

### 3. `water-timelapses`

| Field | Value |
|---|---|
| **slug** | `water-timelapses` |
| **title** | Water Timelapses |
| **category** | `water` |
| **description** | Global precipitation and near-surface humidity, combining NASA GPM IMERG daily rain rates with GEOS-FP forecast fields. |
| **featured** | false |
| **cover-url** | omit |

### 4. `climate-timelapses`

| Field | Value |
|---|---|
| **slug** | `climate-timelapses` |
| **title** | Climate Timelapses |
| **category** | `climate` |
| **description** | Multi-year climate signals: sea surface temperature anomalies and a volumetric view of atmospheric carbon dioxide. |
| **featured** | false |
| **cover-url** | omit |

### 5. `oceans-timelapses`

| Field | Value |
|---|---|
| **slug** | `oceans-timelapses` |
| **title** | Ocean Timelapses |
| **category** | `oceans` |
| **description** | Ocean surface currents colored by water temperature, from a flat ECCO2 map and a globe fly-through of western boundary currents. |
| **featured** | false |
| **cover-url** | omit |

### 6. `agriculture-timelapses`

| Field | Value |
|---|---|
| **slug** | `agriculture-timelapses` |
| **title** | Agriculture Timelapses |
| **category** | `agriculture` |
| **description** | Global land vegetation greenness from MODIS Terra NDVI monthly composites. |
| **featured** | false |
| **cover-url** | omit |

---

## Track → playlist mapping

| Folder | Playlist | Profile | Frames | `--lossy` |
|---|---|---|---|---|
| `air-quality-carbon-monoxide` | `air-quality-timelapses` | `geos-co` | 32 | no |
| `air-quality-nitrogen-oxides` | `air-quality-timelapses` | `geos-nox` | 32 | no |
| `air-quality-ozone` | `air-quality-timelapses` | `geos-o3` | 32 | no |
| `air-quality-pm25` | `air-quality-timelapses` | `geos-pm25` | 32 | no |
| `air-temperature` | `weather-timelapses` | `geos-temperature` | 32 | no |
| `wind-speed` | `weather-timelapses` | `geos-wind` | 32 | no |
| `lightning-globe` | `weather-timelapses` | `globe-lightning` | 32 | **yes** (video extract) |
| `precipitation` | `water-timelapses` | `imerg-precipitation` | 24 | no |
| `precipitation-clouds` | `water-timelapses` | `geos-precipitation` | 32 | no |
| `humidity` | `water-timelapses` | `geos-humidity` | 32 | **yes** (video extract) |
| `sea-temperature` | `climate-timelapses` | `sst-anomaly` | 24 | no |
| `co2-globe` | `climate-timelapses` | `globe-co2` | 32 | no |
| `surface-currents-temperature` | `oceans-timelapses` | `ecco2-sst` | 16 | **no** (never for this profile) |
| `ocean-tour-temperature` | `oceans-timelapses` | `globe-ocean-temperature` | 32 | **yes** (video extract) |
| `vegetation` | `agriculture-timelapses` | `ndvi-vegetation` | 12 | no |

### Skipped folders (no supported profile)

| Folder | Reason |
|---|---|
| `ocean-tour-salinity` | Gray mid-scale conflicts with land/ice/clouds; no profile |
| `ocean-tour-depth` | Beauty version; color encodes depth, not a single measurable variable |

Adding profiles for these is a code change under `app/cv_engine/`, not an ingest task.

### Ignored paths

- `colormaps/` — color tables, not a track
- `.git/` — not data
- Nested `data/` copies under `precipitation/`, `sea-temperature/`, and
  `vegetation/` — duplicate frames of the parent folder; ingest the **parent**
  folder so `--dir` points at one image set only
- Empty `co2-globe/data/` — ignore; frames live in `co2-globe/`

---

## Playlist 1 — Air Quality Timelapses

**Playlist:** `air-quality-timelapses` · **category:** `air-quality`

Shared GEOS-CF context (from DATASETS.md): model estimates (not satellite photos),
period ~29 Oct 2026 05:00 EDT to 13 Nov 2026 15:00 EST, 32 frames ~every 12 hours,
2048×1024 flat maps.

| order | folder | slug | title | event-date |
|---|---|---|---|---|
| 0 | `air-quality-carbon-monoxide` | `geos-co-2026-oct-nov` | Carbon Monoxide and Smoke | `2026-11-13` |
| 1 | `air-quality-nitrogen-oxides` | `geos-nox-2026-oct-nov` | Nitrogen Oxides | `2026-11-13` |
| 2 | `air-quality-ozone` | `geos-o3-2026-oct-nov` | Near-Surface Ozone | `2026-11-13` |
| 3 | `air-quality-pm25` | `geos-pm25-2026-oct-nov` | Fine Particulate Matter PM2.5 | `2026-11-13` |

### Track details

#### `geos-co-2026-oct-nov`

- **dir:** `data_ingest_resources/air-quality-carbon-monoxide`
- **profile:** `geos-co`
- **description:** Near-surface carbon monoxide from NASA GEOS-CF model estimates over about two weeks from late October to mid-November 2026. Values are approximate readings from the official color bar, in parts per billion by volume, highlighting combustion plumes from fires, traffic, and industry.

#### `geos-nox-2026-oct-nov`

- **dir:** `data_ingest_resources/air-quality-nitrogen-oxides`
- **profile:** `geos-nox`
- **description:** Near-surface nitrogen oxides (NO and NO2) from NASA GEOS-CF model estimates over about two weeks from late October to mid-November 2026. Concentrations are approximate logarithmic readings from the color bar and concentrate over traffic and industrial source regions.

#### `geos-o3-2026-oct-nov`

- **dir:** `data_ingest_resources/air-quality-ozone`
- **profile:** `geos-o3`
- **description:** Near-surface ozone from NASA GEOS-CF model estimates over about two weeks from late October to mid-November 2026. This is ground-level ozone pollution, not stratospheric ozone, shown as approximate parts per billion by volume.

#### `geos-pm25-2026-oct-nov`

- **dir:** `data_ingest_resources/air-quality-pm25`
- **profile:** `geos-pm25`
- **description:** Near-surface fine particulate matter (PM2.5) from NASA GEOS-CF model estimates over about two weeks from late October to mid-November 2026. Dust, smoke, and pollution appear as localized hotspots while most of the planet, especially the oceans, remains clean.

---

## Playlist 2 — Weather Timelapses

**Playlist:** `weather-timelapses` · **category:** `weather`

| order | folder | slug | title | event-date |
|---|---|---|---|---|
| 0 | `air-temperature` | `geos-temperature-2026-oct-nov` | Near-Surface Temperature, 14-Day Forecast | `2026-11-13` |
| 1 | `lightning-globe` | `globe-lightning-2017-2023` | Lightning Over Earth 2017-2023 | omit |
| 2 | `wind-speed` | `geos-wind-2026-oct-nov` | Near-Surface Wind Speed, 14-Day Forecast | `2026-11-13` |

### Track details

#### `geos-temperature-2026-oct-nov`

- **dir:** `data_ingest_resources/air-temperature`
- **profile:** `geos-temperature`
- **description:** Near-surface air temperature from NASA GEOS-FP model estimates spanning about two weeks from late October to mid-November 2026. The approximate scale runs from about -40 C to 40 C across a global flat map.

#### `globe-lightning-2017-2023`

- **dir:** `data_ingest_resources/lightning-globe`
- **profile:** `globe-lightning`
- **lossy:** yes (frames extracted from video; see `manifest.json`)
- **description:** Lightning flashes detected by the LIS sensor aboard the International Space Station from January 2017 to July 2023, shown as a relative brightness index on a moving-camera globe. Coverage and intensity depend on what the camera frames as well as storm activity.

#### `geos-wind-2026-oct-nov`

- **dir:** `data_ingest_resources/wind-speed`
- **profile:** `geos-wind`
- **description:** Near-surface wind speed at 10 meters from NASA GEOS-FP model estimates spanning about two weeks from late October to mid-November 2026. Calm areas below the drawing threshold leave the terrain visible; storm-force streaks appear where winds are strongest.

---

## Playlist 3 — Water Timelapses

**Playlist:** `water-timelapses` · **category:** `water`

| order | folder | slug | title | event-date |
|---|---|---|---|---|
| 0 | `humidity` | `geos-humidity-2026-oct-nov` | Near-Surface Humidity Forecast | `2026-11-14` |
| 1 | `precipitation` | `imerg-precipitation-2025` | Global Precipitation Rate 2025 | `2025-12-15` |
| 2 | `precipitation-clouds` | `geos-precipitation-2026-oct-nov` | Global Precipitation Forecast | `2026-11-13` |

### Track details

#### `geos-humidity-2026-oct-nov`

- **dir:** `data_ingest_resources/humidity`
- **profile:** `geos-humidity`
- **lossy:** yes (frames extracted from video; see `manifest.json`)
- **description:** Near-surface specific humidity from NASA GEOS-FP model estimates from about 30 October to 14 November 2026. Values are grams of water vapor per kilogram of air on an approximate color-bar scale, with the moistest air concentrated in the tropics.

#### `imerg-precipitation-2025`

- **dir:** `data_ingest_resources/precipitation`
- **profile:** `imerg-precipitation`
- **description:** Daily average global precipitation rate for 2025 from NASA GIBS IMERG (GPM), with two frames per month on the 1st and 15th. Rainfall is shown in millimeters per hour on the official scale, with light blue tones indicating snow.

#### `geos-precipitation-2026-oct-nov`

- **dir:** `data_ingest_resources/precipitation-clouds`
- **profile:** `geos-precipitation`
- **description:** Estimated precipitation drawn over clouds and terrain from NASA GEOS-FP model fields spanning about two weeks from late October to mid-November 2026. The color bar is an approximate 0 to 20 mm scale; the accumulation period is not stated on the source page.

---

## Playlist 4 — Climate Timelapses

**Playlist:** `climate-timelapses` · **category:** `climate`

| order | folder | slug | title | event-date |
|---|---|---|---|---|
| 0 | `co2-globe` | `globe-co2-2021` | Atmospheric Carbon Dioxide 2021 | omit |
| 1 | `sea-temperature` | `sst-anomaly-2003-2026` | Sea Surface Temperature Anomalies 2003-2026 | `2026-08-15` |

### Track details

#### `globe-co2-2021`

- **dir:** `data_ingest_resources/co2-globe`
- **profile:** `globe-co2`
- **description:** Volumetric atmospheric carbon dioxide added during 2021 from NASA SVS 5115, shown as an orange-brown haze around a fixed-camera globe. The engine measures a relative 0-1 haze index, not parts per million; density rises and falls with the seasons and ends the year higher than it began.

#### `sst-anomaly-2003-2026`

- **dir:** `data_ingest_resources/sea-temperature`
- **profile:** `sst-anomaly`
- **description:** Global sea surface temperature anomalies from NASA GIBS GHRSST MUR25, one August 15 frame per year from 2003 to 2026. Blue areas are cooler than average and red areas are warmer, showing where ocean heat has shifted over two decades.

---

## Playlist 5 — Ocean Timelapses

**Playlist:** `oceans-timelapses` · **category:** `oceans`

| order | folder | slug | title | event-date |
|---|---|---|---|---|
| 0 | `ocean-tour-temperature` | `globe-ocean-temperature-po2` | Ocean Currents Temperature | omit |
| 1 | `surface-currents-temperature` | `ecco2-sst-surface-currents` | Ocean Currents and Sea Temperature | omit |

### Track details

#### `globe-ocean-temperature-po2`

- **dir:** `data_ingest_resources/ocean-tour-temperature`
- **profile:** `globe-ocean-temperature`
- **lossy:** yes (frames extracted from video; seconds in filenames)
- **description:** Western boundary ocean currents from NASA SVS 5425 Perpetual Ocean 2, colored by water temperature on a moving-camera globe. The camera passes Kuroshio, Agulhas, and Gulf Stream regions; only the visible colored current strokes are measured.

#### `ecco2-sst-surface-currents`

- **dir:** `data_ingest_resources/surface-currents-temperature`
- **profile:** `ecco2-sst`
- **lossy:** do not pass (profile already uses a high color tolerance)
- **description:** Global ocean surface currents from the ECCO2 model (MIT/JPL), drawn as sparse strokes colored by sea surface temperature on a flat map. The engine measures only the bright current strokes, not the full ocean field; source page dates are not specified.

---

## Playlist 6 — Agriculture Timelapses

**Playlist:** `agriculture-timelapses` · **category:** `agriculture`

| order | folder | slug | title | event-date |
|---|---|---|---|---|
| 0 | `vegetation` | `ndvi-vegetation-2024` | Global Vegetation Index 2024 | `2024-12-01` |

### Track details

#### `ndvi-vegetation-2024`

- **dir:** `data_ingest_resources/vegetation`
- **profile:** `ndvi-vegetation`
- **description:** Monthly global vegetation greenness for 2024 from NASA GIBS MODIS Terra NDVI. The official index runs from 0 to 1 with no physical unit; greener land means denser active vegetation, and oceans have no data.

---

## Execution order

Run sequentially (no concurrent writers against the same playlist).

### Step A — Create playlists

```bash
python scripts/ingest_playlist.py create \
  --slug air-quality-timelapses \
  --title "Air Quality Timelapses" \
  --category air-quality \
  --description "Near-surface air composition from NASA GEOS-CF model estimates over about two weeks in late 2026. Tracks cover fine particles, ozone, carbon monoxide, and nitrogen oxides."

python scripts/ingest_playlist.py create \
  --slug weather-timelapses \
  --title "Weather Timelapses" \
  --category weather \
  --description "Near-surface weather fields from NASA GEOS-FP forecasts and lightning observed from the International Space Station."

python scripts/ingest_playlist.py create \
  --slug water-timelapses \
  --title "Water Timelapses" \
  --category water \
  --description "Global precipitation and near-surface humidity, combining NASA GPM IMERG daily rain rates with GEOS-FP forecast fields."

python scripts/ingest_playlist.py create \
  --slug climate-timelapses \
  --title "Climate Timelapses" \
  --category climate \
  --description "Multi-year climate signals: sea surface temperature anomalies and a volumetric view of atmospheric carbon dioxide."

python scripts/ingest_playlist.py create \
  --slug oceans-timelapses \
  --title "Ocean Timelapses" \
  --category oceans \
  --description "Ocean surface currents colored by water temperature, from a flat ECCO2 map and a globe fly-through of western boundary currents."

python scripts/ingest_playlist.py create \
  --slug agriculture-timelapses \
  --title "Agriculture Timelapses" \
  --category agriculture \
  --description "Global land vegetation greenness from MODIS Terra NDVI monthly composites."
```

### Step B — Dry-run every track

For each of the 15 tracks, run `ingest_timelapse.py` with the fields above plus
`--dry-run --out /tmp/opencode/ingest/<slug>.json`. Prefer a Python list-form
subprocess so titles and descriptions are not shell-interpolated.

Inspect each JSON before writing:

- `profile_id` matches the plan
- `len(frames)` equals the frame count in the table
- no color-table / unmatched-fraction warnings that imply the wrong profile

### Step C — Ingest tracks

Replay the same commands without `--dry-run`, playlist by playlist, in the
`sequence-order` listed above. Use `--replace` only if a failed write left a
partial track with the same slug and you intend to overwrite it.

### Step D — Verify

```bash
python scripts/ingest_playlist.py show --slug air-quality-timelapses
python scripts/ingest_playlist.py show --slug weather-timelapses
python scripts/ingest_playlist.py show --slug water-timelapses
python scripts/ingest_playlist.py show --slug climate-timelapses
python scripts/ingest_playlist.py show --slug oceans-timelapses
python scripts/ingest_playlist.py show --slug agriculture-timelapses
```

---

## Assumptions and notes

1. **Prefix grouping:** all `air-quality-*` folders share `air-quality-timelapses`.
   `precipitation` and `precipitation-clouds` share `water-timelapses`.
   Supported `ocean-tour-*` goes to `oceans-timelapses` with
   `surface-currents-temperature`.
2. **`air-temperature` is weather, not air quality** — different category and
   profile family (`geos-temperature` / GEOS-FP).
3. **Sequence order** within each playlist is natural folder-name order, except
   weather/water/climate/oceans where a small thematic order was preferred
   (still contiguous from 0).
4. **`--event-date`** uses the latest known frame date when the series has a clear
   end; omitted when the source page has no dates or only a multi-year window
   without a single reference day (`lightning-globe`, `co2-globe`, ocean current
   tracks).
5. **No `--frames-url` / `--frames-ext`** — none supplied in the dataset docs.
6. **No `--featured`** — not requested.
7. **Duplicate `data/` trees** under some GIBS folders are ignored; ingest the
   parent directory that already holds the frames.
8. **Skipped salinity and beauty ocean folders** remain on disk for video use only.

---

## Checklist before write

- [ ] Six playlists created (or confirmed existing with matching intent)
- [ ] All 15 tracks dry-run OK
- [ ] Lossy only on `humidity`, `lightning-globe`, `ocean-tour-temperature`
- [ ] No `--lossy` on `ecco2-sst`
- [ ] No `--replace` without confirmation
- [ ] No playlist delete
- [ ] `ocean-tour-salinity` and `ocean-tour-depth` left uningested
