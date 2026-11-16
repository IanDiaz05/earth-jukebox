# CV engine summarization

**Source:** `app/cv_engine/summarize.py`

This module turns a frame that has already been converted to physical values
into named features, an exploration grid, and per-region measurements. The same
logic is used for the whole map and for each region, so the frontend can sonify
"the world" or "Africa only" with the same code.

## Area weighting

Every mean is weighted by pixel area. On an equirectangular map, rows near the
poles cover much less area than rows at the equator; without weighting, the
poles would dominate. `Geometry` stores the latitude, longitude, and area weight
of each pixel, and supports:

- **Flat maps**: latitude and longitude from the profile's ranges, with row
  weight proportional to the cosine of latitude.
- **Globes**: latitude from the disk curvature, "longitude" as the angle from
  the view center, and equal weight per disk pixel.
- **Moving-camera globes**: positions relative to the visible planet's bounding
  box, weighting only planet pixels.

`Geometry.area(mask)` sums weights, and `Geometry.fraction(mask, of)` divides by
a base area.

## Data structures

- **`FrameValues`** holds the per-pixel value array, the validity mask for the
  primary variable, masks for secondary color-table sections, and unmatched
  pixels. `crop(rows, cols)` returns the same structure for a sub-area.
- **`FrameMeasurement`** holds the full-map features, the grid array (`NaN` where
  there is no data), and a dictionary of per-region features (or `None` when a
  region has no data).

## Feature calculation

`measure_area` chooses the feature set from `profile.kind`.

### Sequential scales

| Feature | Meaning |
|---|---|
| `coverage` | Fraction of the area that has data |
| `mean` | Area-weighted mean; colorless areas count as zero when `missing_is_zero` |
| `mean_active` | Area-weighted mean over pixels that have data |
| `p05`, `p95` | Weighted percentiles of active pixels |
| `max` | Maximum active value |
| `frac_<threshold>` | Area fraction at or above each named threshold |
| `centroid_lat`, `centroid_lon`, `centroid_x` | Center of mass of the measured volume |
| `north_share` | Share of the volume north of the split latitude |
| `south_mean`, `middle_mean`, `north_mean` | Area-weighted means per latitude band |

### Diverging scales

| Feature | Meaning |
|---|---|
| `coverage` | Fraction of the area with data |
| `mean` | Area-weighted mean over valid pixels |
| `p05`, `p95`, `min`, `max` | Weighted percentiles and extremes of valid pixels |
| `frac_above`, `frac_below` | Fractions above and below `center` |
| `balance` | `frac_above - frac_below` |
| `frac_<threshold>` | Fraction at or above a threshold above the center, or at or below one below it |
| `centroid_*`, `north_share` | Position of the excess above the center |
| `south_mean`, `middle_mean`, `north_mean` | Area-weighted means per band |

### Added by the summarizer

- **`change`**: mean absolute difference between this frame's grid and the
  previous frame's grid, over cells with data in both. The first frame is `0`.
- **`unmatched_fraction`**: area fraction of opaque pixels that did not match
  the color table.
- **`shapes_count`, `shapes_largest`**: when the profile defines
  `shape_threshold`, connected components at or above that threshold are counted
  and the largest component's area fraction is reported. The mask is resized to
  a fixed width so storm counts are comparable between the world and a crop.
- **`frac_<section>`**: for each secondary color-table section, the area
  fraction it covers (for example snow alongside rain).

## Grid

`block_mean(values, valid, rows, cols)` averages valid values into the profile's
exploration grid. A cell with less than 10% data becomes `NaN`, which the
pipeline serializes as `null`.

## Regions

`region_slices(region, shape, profile)` converts a region's latitude/longitude
box into row and column slices. Within a region, the latitude bands are its
southern, central, and northern thirds, and `north_share` is measured relative
to the region center.

## Helper functions

| Function | Purpose |
|---|---|
| `weighted_percentile(values, weights, q)` | Weighted percentile |
| `count_shapes(mask, lon_span)` | Count components and measure the largest |
| `_position(mass, geometry)` | Center of mass and north share |
| `_band_means(volume, base, geometry)` | Mean per latitude band |
| `_grid_change(grid, previous)` | Mean grid difference between frames |
| `summarize(frame, profile, previous_grid, planet)` | Full-map and regional measurement |
