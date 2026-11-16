# CV engine pipeline

**Source:** `app/cv_engine/pipeline.py`

This module orchestrates the engine: it finds the frames, loads the color table,
converts each frame to values, summarizes it, and builds the JSON contract.

## Constants

| Constant | Purpose |
|---|---|
| `SCHEMA_VERSION` | Output contract version, `"2.2"` |
| `COLORMAPS_DIR` | Bundled color tables (`app/cv_engine/colormaps/`) |
| `VALID_EXTENSIONS` | Accepted frame formats: PNG, JPEG, WebP, TIFF |
| `MAX_UNMATCHED_WARNING` | `2%`; above this, a frame with transparency gets a warning |

## Frame handling

- **`collect_frames(directory)`** returns image files sorted by the numbers in
  their names, so `frame_2` comes before `frame_10`. A missing directory or an
  empty result raises `EmptyDirectoryError`.
- **`load_frame(path)`** decodes the image from bytes (tolerating spaces and
  accented characters), normalizes non-8-bit images, converts grayscale to
  color, and returns an RGB image plus an opaque-pixel mask. PNGs with an alpha
  channel use alpha to mark data; images without alpha treat every pixel as
  opaque.
- **`mask_boxes(opaque, boxes)`** marks logos, dates, or other overlays as no
  data. Boxes are fractions of the image.
- **`crop_region(rgb, opaque, region)`** crops the data area, excluding titles
  and legends. An empty crop raises `InvalidProfileError`.

## Color table and values

`load_lut(dataset_dir, profile)` selects the color source:

1. If the profile defines an image legend, read it from the dataset directory
   and build the table with `lut_from_legend`.
2. Otherwise, look for the profile's XML first in `app/cv_engine/colormaps/`,
   then in the dataset directory, and parse it with `load_gibs_colormap`.

A color-table failure is converted to `InvalidProfileError`.

`frame_to_values(rgb, opaque, lut, profile)` converts pixels to physical
values:

- Exact color matches are always required first.
- If the profile sets `max_delta_e`, remaining pixels are matched to the nearest
  color in CIELAB within that tolerance, which handles compressed frames.
- If the profile enables `despeckle`, a tolerance-only match must have
  neighboring data pixels; isolated background colors are discarded.
- Pixels from secondary table sections (for example snow) are returned as
  separate masks, not as primary values.

The result is a `FrameValues` object holding primary values, a validity mask,
secondary-section masks, and unmatched pixels.

## `measure_timelapse(image_directory, profile)`

This is the main entry point. It:

1. Collects the frames and loads the color table from the dataset directory's
   parent (the legend image lives alongside the frames).
2. Rejects profiles that combine a globe projection with geographic regions,
   because the globe view rotates.
3. Processes each frame in order:
   - read, apply overlay masks, and crop the data region;
   - verify every frame has the same size;
   - for moving-camera globes, locate and isolate the visible planet;
   - convert colors to values and summarize features, grid, and regions.
4. Builds one record per frame with its index, filename, optional date, rounded
   features, regional features, top region, and grid.
5. Finishes the full-map series by adding `mean_departure` and computing feature
   ranges and linear trends.
6. Builds each region's series independently. If a region lacks data in any
   frame, it is disabled for the whole track and a warning is recorded.
7. Assembles `dataset_info` with profile identity, units, thresholds, ranges,
   hints, statistics, trends, regions, and warnings.

## Errors

| Error | When |
|---|---|
| `EmptyDirectoryError` | The directory is missing or has no accepted images |
| `InvalidProfileError` | The color table, legend, or crop is invalid, or a globe has regions |
| `MLEngineError` | A frame cannot be read or its size differs from the first frame |
