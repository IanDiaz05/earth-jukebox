# CV engine color tables

**Source:** `app/cv_engine/colormap.py`

This module converts between colors and physical values. It is the core reason
the engine's numbers have units: each table color is tied to an interval on a
published or drawn scale.

## `Lut` — color-to-value table

A frozen dataclass holding:

| Field | Contents |
|---|---|
| `rgb` | Table colors as `uint8` (N, 3) |
| `lab` | The same colors in CIELAB, used for tolerant matching |
| `value` | Representative value for each color |
| `low` | Lower bound of each color's interval |
| `section` | Index of the source section for each color |
| `sections` | Section names, for example `("rain", "snow")` |
| `unit` | Physical unit |

`value_range` returns the minimum and maximum representative values.

## Loading an official GIBS table

`load_gibs_colormap(xml_path, sections)` parses a NASA GIBS XML color table
(v1.3):

1. It selects only the `ColorMap` sections named in the profile, mapping the XML
   title to a short name.
2. It ignores transparent and no-data entries.
3. It parses intervals such as `"[0.1,0.1059)"`, including `-INF` and `+INF`.
4. It drops duplicate colors.
5. It detects whether the section uses a logarithmic scale by comparing interval
   widths, then chooses a representative value per interval: the midpoint for a
   linear scale, the geometric midpoint for a logarithmic one, and the finite
   bound for open-ended intervals.
6. It returns a `Lut` with the colors converted to CIELAB.

A missing or unusable file raises `ColormapError`.

## Reading a legend from an image

`lut_from_legend(...)` builds a table for datasets that publish only a color bar
image:

- Crop the bar using fractional coordinates.
- Take the median color across the bar's width (or height when vertical).
- Sample a fixed number of steps along the bar.
- Distribute values linearly or logarithmically between the declared endpoints.
- Collapse repeated colors by averaging their assigned values.

It raises `ColormapError` for an empty crop or a logarithmic scale with
non-positive endpoints.

## Matching pixels to the table

`invert(rgb, lut, candidates=None, max_delta_e=0.0)` assigns each pixel the
index of its color:

1. Pack RGB triples into integers and look for exact matches first.
2. If `max_delta_e` is positive, unmatched pixels are compared with the table in
   CIELAB and accepted only when the nearest distance is within the tolerance.
   Processing is chunked to bound memory use.
3. Return an `int16` array with the table index, or `-1` where the pixel is not
   data.

The tolerance path exists for compressed or smoothed frames. It is deliberately
distance-limited so base-map colors are not mistaken for measurements.

## Helper functions

| Function | Purpose |
|---|---|
| `rgb_to_lab(rgb)` | Convert `uint8` RGB colors to true CIELAB |
| `_parse_interval(text)` | Parse an interval string into low/high bounds |
| `_is_log_spaced(intervals)` | Detect proportional interval growth |
| `_representative(low, high, log_spaced)` | Choose one value per interval |
| `_pack(rgb)` | Pack RGB colors into 24-bit integers |
