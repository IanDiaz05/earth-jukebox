# CV engine overview

**Sources:** `app/cv_engine/__init__.py`, `app/cv_engine/README.md`

The CV engine turns color-scaled satellite frames into numeric measurements with
units. It uses NumPy and OpenCV only; there are no neural networks. The public
API never runs the engine: ingestion scripts measure frames offline and store
the result in PostgreSQL.

## Public interface

`app/cv_engine/__init__.py` re-exports the supported entry points:

| Export | Meaning |
|---|---|
| `measure_timelapse` | Measure a frame directory and return the JSON contract |
| `load_lut` | Load a profile's color table (XML or image legend) |
| `SCHEMA_VERSION` | Output contract version, currently `"2.2"` |
| `PROFILES` | Registry of all supported dataset profiles |
| `DatasetProfile`, `LegendSpec` | Profile data classes |
| `lossy` | Build a tolerant profile variant for compressed frames |
| `MLEngineError` and subclasses | Engine exception hierarchy |

## Processing flow

```text
frame folder
   │
   ├─ collect frames in numeric order
   ├─ load the profile's color table (LUT)
   ├─ per frame: read image → mask/crop → match colors → values
   ├─ summarize: features, grid, regions
   └─ dataset_info + frames (JSON, schema 2.2)
```

1. **Color table → values.** Each table color maps to a physical value, so every
   measurement has a unit and a documented source.
2. **Values → features.** Each frame is summarized into named features such as
   `mean`, `coverage`, `p95`, `centroid_lat`, `north_share`, threshold
   fractions, and shape counts.
3. **Series → dataset information.** Trends, feature ranges, region statistics,
   and warnings are computed across the frame series.

## Output contract (schema `2.2`)

The engine returns `{"dataset_info": {...}, "frames": [...]}`.

### `dataset_info`

| Field | Contents |
|---|---|
| `schema_version` | Contract version (`"2.2"`) |
| `profile_id`, `title`, `label`, `topic`, `source` | Profile identity and attribution |
| `kind` | `sequential` or `diverging` |
| `projection` | `equirectangular` or `globe` |
| `variable`, `unit` | What is measured and its physical unit |
| `missing_is_zero` | Whether colorless areas count as zero |
| `value_range` | Minimum and maximum values in the color table |
| `thresholds` | Named thresholds used to compute fractions |
| `center` | Neutral value, present only for diverging scales |
| `grid_size`, `lat_range`, `lon_range` | Map geometry |
| `hints` | Sonification hints and interface words for the frontend |
| `frames_count`, `feature_names`, `feature_stats` | Series summary and per-feature ranges |
| `trends` | Linear slope per feature across frames |
| `regions` | Per-region geometry, statistics, and trends |
| `warnings` | Non-fatal data problems (region skipped, excess unmatched pixels) |

### Each frame

| Field | Contents |
|---|---|
| `frame_index`, `frame_id` | Position and source filename |
| `date` | ISO date extracted from the filename, when present |
| `features` | Full-map features |
| `regions` | The same features per named region, or `null` |
| `top_region` | Region with the highest `mean`, when regions exist |
| `grid` | Exploration grid of mean values; cells without data are `null` |

Changing field names or shapes changes the database and frontend contract.
Bump `SCHEMA_VERSION`, update the README, and add tests when doing so.

## Where to look next

- [cv-engine-pipeline.md](cv-engine-pipeline.md) — orchestration and file handling
- [cv-engine-colormap.md](cv-engine-colormap.md) — color tables and inversion
- [cv-engine-profiles.md](cv-engine-profiles.md) — dataset configuration and registry
- [cv-engine-summarize.md](cv-engine-summarize.md) — feature calculation
