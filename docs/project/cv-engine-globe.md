# CV engine globe support

**Source:** `app/cv_engine/globe.py`

This module locates the visible part of the planet in frames where the planet is
seen as a sphere and the camera moves. Examples are the lightning and Perpetual
Ocean globe profiles.

## Why only the visible part

When the camera zooms, pans, or the night side is invisible, there is no
reliable limb with which to rebuild the full disk. The engine therefore measures
only what is visible and positions measurements relative to that visible area.

## `VisiblePlanet`

A frozen dataclass with:

| Field | Meaning |
|---|---|
| `planet` | Boolean mask (H, W) of planet pixels, excluding space and stars |
| `box` | Bounding box `(left, top, right, bottom)` in pixels, right and bottom exclusive |

When no planet is found, the mask is empty and the box is the whole image.

## `find_planet(rgb, background_max=20)`

The algorithm:

1. Treat pixels whose brightest channel exceeds `background_max` as bright.
2. Remove stars and thin lines with a morphological opening.
3. Find connected components and keep the largest bright blob.
4. Fill that blob with its convex hull, so the dark area between the horns of a
   crescent is included (data such as lightning can be drawn there).
5. Return the hull as the planet mask and its bounding rectangle.

The `background_max` value comes from the profile and describes how bright space
may be in that dataset.
