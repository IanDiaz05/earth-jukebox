# CV engine profiles

**Source:** `app/cv_engine/profiles.py`

A profile describes everything the engine needs to know about one visualization:
where its colors come from, what it measures, how to interpret missing areas,
which regions to report, and how the frontend should sonify it. Adding a dataset
means adding a profile and its color table; the rest of the engine stays
unchanged.

## Data classes

### `LegendSpec`

Describes a legend bar drawn inside an image, used when no official color table
exists.

| Field | Meaning |
|---|---|
| `file` | Image containing the legend, relative to the dataset directory |
| `box` | Bar crop `(left, top, right, bottom)` as 0–1 fractions |
| `value_min`, `value_max` | Values at the bar endpoints |
| `scale` | `linear` or `log` |
| `vertical` | Whether the bar runs bottom-to-top |
| `unit` | Physical unit |
| `steps` | Number of colors sampled along the bar |

### `DatasetProfile`

The per-dataset configuration. Key fields:

| Field | Meaning |
|---|---|
| `id`, `title`, `label`, `topic`, `source` | Identity, display names, and attribution |
| `kind` | `sequential` (low to high) or `diverging` (centered on a midpoint) |
| `variable` | Short name of the measured quantity |
| `colormap_file`, `sections` | Official XML table and the sections to read |
| `legend` | Alternative image legend |
| `unit` | Overrides the unit declared by the table |
| `missing_is_zero` | Whether colorless areas are zero or "no data" |
| `max_delta_e`, `despeckle` | Color tolerance and speckle removal for compressed frames |
| `data_region`, `mask_boxes` | Crop for data and overlays to ignore |
| `projection` | `equirectangular` or `globe` |
| `track_planet`, `background_max` | Locate the planet in moving-camera globes |
| `lat_range`, `lon_range`, `grid` | Map geometry and exploration grid |
| `thresholds`, `center`, `shape_threshold` | Named levels and the level used to count shapes |
| `tropics_lat` | Boundary between tropics and mid-latitudes |
| `regions` | Named regions that receive the same features as the full map |
| `hints` | Sonification mapping and interface words |

## Scale kinds

- **`sequential`**: values from low to high, such as rain, vegetation, wind, or
  gases. `missing_is_zero=True` means an uncolored area is a real zero (rain);
  `False` means no data (vegetation over the ocean), so means use only pixels
  with data.
- **`diverging`**: values centered on `center`, such as temperature anomalies.
  Only pixels with data count, and the engine tracks both sides of the midpoint.

## Registered profiles

`PROFILES` maps each profile ID to its `DatasetProfile`. There are 15:

| Profile ID | Variable | Kind | Projection |
|---|---|---|---|
| `imerg-precipitation` | Rain and snow rate | sequential | flat map |
| `sst-anomaly` | Sea surface temperature anomaly | diverging | flat map |
| `ndvi-vegetation` | Vegetation index | sequential | flat map |
| `geos-temperature` | Near-surface air temperature | diverging | flat map |
| `geos-wind` | Near-surface wind speed | sequential | flat map |
| `geos-precipitation` | Precipitation and clouds | sequential | flat map |
| `geos-humidity` | Near-surface humidity | sequential | flat map |
| `geos-pm25` | PM2.5 particulate matter | sequential | flat map |
| `geos-o3` | Near-surface ozone | sequential | flat map |
| `geos-co` | Carbon monoxide | sequential | flat map |
| `geos-nox` | Nitrogen oxides | sequential | flat map |
| `ecco2-sst` | Currents colored by sea temperature | sequential | flat map |
| `globe-co2` | CO₂ haze index | sequential | globe |
| `globe-lightning` | Lightning index | sequential | globe, moving camera |
| `globe-ocean-temperature` | Current temperature | sequential | globe, moving camera |

The GEOS profiles share overlay masks and a color tolerance because their frames
are shaded and carry a logo and timestamp.

## Helpers

- `lossy(profile, max_delta_e=18.0, despeckle=False)` returns a copy with
  relaxed color matching. Use it for frames extracted from video, JPEG
  screenshots, or other compressed sources.
- `_geos(page, name, model)` builds the NASA SVS source string used by the GEOS
  profiles.
- `replace(...)` (from `dataclasses`) derives new profiles from a base profile;
  the globe variants build on `GLOBE_CO2`.

## Adding a visualization

1. Add the color table XML under `app/cv_engine/colormaps/`.
2. Define a `DatasetProfile` with its scale, unit, thresholds, and hints.
3. Register it in `PROFILES`.
4. Add tests and, if the contract changes, bump the schema version.
