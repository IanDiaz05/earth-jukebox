# Visual measurement engine

Converts frames from a visualization with a color scale into data with units.
Uses OpenCV and NumPy: reads the color of each pixel, translates it to its value using the
visualization's color table, and summarizes each frame into named features. It does not use
neural networks and does not need prior calibration.

It replaces the previous engine (MobileNetV2 + PCA), whose 8 channels had no physical
meaning.

## Usage

```python
from pathlib import Path
from app.cv_engine import PROFILES, lossy, measure_timelapse

resultado = measure_timelapse(Path("frames/"), PROFILES["sst-anomaly"])
# Video or JPEG frames: tolerate compression
resultado = measure_timelapse(Path("frames/"), lossy(PROFILES["sst-anomaly"]))
```

From the command line, `scripts/ingest_timelapse.py` measures a folder and saves the
result as a track (see `--help`). With `--replace` it re-measures a track that already
exists without changing its slug; with `--dry-run --out` it measures and saves the JSON
without touching the database.

## Modules

| File | Contents |
|---|---|
| `profiles.py` | One `DatasetProfile` per visualization; `PROFILES` registry |
| `colormaps/` | Official color tables (NASA GIBS XML) |
| `colormap.py` | Reading the table (XML or drawn legend) and color → value conversion |
| `summarize.py` | Features for the whole map and for each region, grid, and shapes |
| `regions.py` | Named geographic boxes: continents and ocean basins |
| `pipeline.py` | `measure_timelapse`: frames folder → JSON contract |
| `video.py` | `extract_frames`: PNG frames from a video |
| `globe.py` | `find_planet`: visible part of the planet on moving-camera globes |
| `exceptions.py` | `MLEngineError` and derived errors |

## Adding a visualization

1. Save its color table in `colormaps/`, or describe the image's legend bar with
   `LegendSpec`.
2. Add a `DatasetProfile` in `profiles.py` and register it in `PROFILES`.

Nothing else needs to be touched. New code is only needed if the visualization is of a
scale type the engine does not yet measure: today there are `sequential` (from low to high)
and `diverging` (around a center).

Main profile fields:

| Field | Purpose |
|---|---|
| `kind` | `sequential` or `diverging` |
| `missing_is_zero` | Whether a pixel with no color is worth zero (rain) or is "no data" (vegetation over the sea) |
| `colormap_file`, `sections` | Color table and which sections to use |
| `legend` | Alternative: legend bar drawn in an image |
| `max_delta_e` | Color tolerance; `0` for source PNGs, about 18 for video or JPEG |
| `data_region` | Area of the image with data, to leave out title and legend |
| `mask_boxes` | Boxes ignored inside the map (logo, date) without cropping rows or columns |
| `projection` | `equirectangular` (flat map) or `globe` (planet seen as a sphere; `data_region` is the disk box) |
| `track_planet`, `background_max` | Moving-camera globe: find the planet in each frame, and maximum brightness of space |
| `lat_range`, `lon_range` | Geographic extent of the map (equirectangular) |
| `thresholds`, `shape_threshold` | Named thresholds and which one delimits the shapes |
| `regions` | Named regions; each one receives the same features as the world |
| `label`, `hints` | Name for the selector and sound and text hints for the frontend |

## Output contract (version 2.2)

`measure_timelapse` returns `{"dataset_info": {...}, "frames": [...]}`. In the database,
`dataset_info` is saved in `Track.engine_metadata` and `frames` in `Track.frames`.

**`dataset_info`**: `schema_version`, `profile_id`, `title`, `label`, `topic`, `kind`, `projection`,
`unit`, `missing_is_zero`, `value_range`, `thresholds`, `grid_size`, `lat_range`,
`lon_range`, `hints`, `frames_count`, `feature_names`, `feature_stats` (minimum and maximum
of each feature), `trends` (linear trend), `warnings`, and `regions`. Each region brings
`name`, `lat`, `lon`, `grid_rows`, `grid_cols`, its `feature_stats`, and its trend.

**Each frame**: `frame_index`, `frame_id` (file name), `date` (if the name contains it),
`features` (the whole map), `regions` (the same features per region),
`top_region`, and `grid` (grid of values; `null` where there is no data).

| Feature | `sequential` | `diverging` |
|---|---|---|
| How much | `coverage`, `mean`, `mean_active`, `p05`, `p95`, `max` | `coverage`, `mean`, `p05`, `p95`, `min`, `max` |
| Thresholds | `frac_<threshold>` | `frac_above`, `frac_below`, `balance`, `frac_<threshold>` |
| Where | `centroid_lat`, `centroid_lon`, `centroid_x`, `north_share` | Same, on the excess relative to the center |
| Bands | `south_mean`, `middle_mean`, `north_mean` | Same |
| Shapes | `shapes_count`, `shapes_largest` | Same |
| Time | `change`, `mean_departure` | Same |
| Control | `unmatched_fraction` (whole map only) | Same |

In the whole map the bands are south, tropics, and north, and `north_share` is measured
relative to the equator. Inside a region they are its thirds, and `north_share` and
`centroid_x` are relative to the region.

## Known limits

- Two scale types; categorical (fires) and natural color are missing.
- Measures equirectangular maps and, with `projection="globe"`, spheres. On a sphere latitude
  is approximate (assumes a vertical axis) and there is no geographic longitude nor regions,
  because the view rotates; `centroid_x` is the position in the view. `GLOBE_CO2` is the base
  profile: other globes derive from it with `replace`.
- With a moving camera (`track_planet=True`) only the visible part of the planet is measured and
  positions are relative to it, so values follow what the camera frames.
- Without a color bar there are no physical values: `scripts/haze_ramp_to_xml.py` builds a
  relative 0-1 index from the frames (CO2 5115, lightning 5011).
- Color tables built from SVS color bar images (`scripts/colorbar_to_xml.py`) are read from
  pixels; the script docstring lists which scale assumptions are confirmed by the ticks.
- Regions are latitude and longitude boxes, not real outlines.
- With compressed frames (JPEG quality 85) it recovers between 93% and 98% of the data; with
  source PNGs the reading is exact.

## Tests

```bash
python -m unittest discover -s tests
```