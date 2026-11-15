"""Summarize a frame already converted to values: named features, grid, and regions.

The same features are calculated for the full map and for each named region,
so the frontend can sonify "the world" or "Africa only" using the same code.

All means are weighted by the actual area of each pixel. In an equirectangular
map, a row near the pole covers much less area than one at the equator, and
without this correction the poles would be over-weighted.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.ml_engine.profiles import DatasetProfile
from app.ml_engine.regions import Region

# A cell or region needs at least this fraction of pixels with data.
MIN_COVERAGE = 0.1
# Shapes are searched for at this resolution (full-map width); smaller ones
# are ignored.
SHAPE_WIDTH = 360
MIN_SHAPE_PIXELS = 4


@dataclass(frozen=True)
class FrameValues:
    """A frame converted to physical values.

    Attributes:
        values: Value per pixel, ``float32`` (H, W). ``0`` where not applicable.
        valid: Pixels with data for the primary variable.
        extras: Masks for secondary table sections (e.g. snow).
        unmatched: Opaque pixels that did not match the table.
    """

    values: np.ndarray
    valid: np.ndarray
    extras: dict[str, np.ndarray]
    unmatched: np.ndarray

    def crop(self, rows: slice, cols: slice) -> "FrameValues":
        return FrameValues(
            self.values[rows, cols],
            self.valid[rows, cols],
            {name: mask[rows, cols] for name, mask in self.extras.items()},
            self.unmatched[rows, cols],
        )


@dataclass(frozen=True)
class FrameMeasurement:
    """Result of measuring a frame.

    Attributes:
        features: Features of the full map.
        grid: Exploration grid; ``NaN`` in cells without data.
        regions: Features for each named region (``None`` if it has no data).
    """

    features: dict[str, float]
    grid: np.ndarray
    regions: dict[str, dict[str, float] | None]


class Geometry:
    """Latitude, longitude, and area weight of each pixel in a map or crop.

    Args:
        shape: ``(height, width)`` in pixels.
        lat_range: Latitudes of the top and bottom edges.
        lon_range: Longitudes of the left and right edges.
        band_edges: Latitudes separating the three bands (south, middle, north).
        split_lat: Latitude separating "north" from "south" in ``north_share``.
        scale: Pixels per degree, for finding shapes at a constant resolution.
    """

    def __init__(
        self,
        shape: tuple[int, int],
        lat_range: tuple[float, float],
        lon_range: tuple[float, float],
        band_edges: tuple[float, float],
        split_lat: float,
    ) -> None:
        height, width = shape
        top, bottom = lat_range
        left, right = lon_range
        self.lat = top + (np.arange(height) + 0.5) / height * (bottom - top)
        self.lon = left + (np.arange(width) + 0.5) / width * (right - left)
        row_weight = np.cos(np.radians(self.lat)).clip(min=0.0)
        self.weight = np.repeat(row_weight[:, None], width, axis=1)
        self.total = float(self.weight.sum())
        self.half_span = (right - left) / 2.0
        self.center_lon = (right + left) / 2.0
        self.band_edges = band_edges
        self.split_lat = split_lat
        self.lon_span = abs(right - left)

    def area(self, mask: np.ndarray) -> float:
        return float(self.weight[mask].sum())

    def fraction(self, mask: np.ndarray, of: float | None = None) -> float:
        base = self.total if of is None else of
        return self.area(mask) / base if base > 0 else 0.0


def weighted_percentile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """Weighted ``q`` (0–100) percentile."""
    if values.size == 0:
        return 0.0
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    index = min(int(np.searchsorted(cumulative, q / 100.0 * cumulative[-1])), values.size - 1)
    return float(values[order][index])


def block_mean(values: np.ndarray, valid: np.ndarray, rows: int, cols: int) -> np.ndarray:
    """Mean per cell over valid pixels; ``NaN`` if the cell has too little data."""
    height, width = values.shape
    row_edges = np.linspace(0, height, rows + 1).astype(int)
    col_edges = np.linspace(0, width, cols + 1).astype(int)

    def reduce(array: np.ndarray) -> np.ndarray:
        by_row = np.add.reduceat(array, row_edges[:-1], axis=0)
        return np.add.reduceat(by_row, col_edges[:-1], axis=1)

    sums = reduce(np.where(valid, values, 0.0).astype(np.float64))
    counts = reduce(valid.astype(np.float64))
    sizes = np.outer(np.diff(row_edges), np.diff(col_edges))
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = sums / counts
    mean[counts < sizes * MIN_COVERAGE] = np.nan
    return mean.astype(np.float32)


def count_shapes(mask: np.ndarray, lon_span: float = 360.0) -> tuple[int, float]:
    """Count connected components in ``mask`` and measure the largest.

    The mask is resized to a fixed resolution per degree so that the same
    storm counts equally on the full map and in a region crop.

    Returns:
        ``(number of shapes, fraction of the mask occupied by the largest)``.
    """
    height, width = mask.shape
    small_width = max(1, round(SHAPE_WIDTH * lon_span / 360.0))
    small_height = max(1, round(height * small_width / width))
    small = cv2.resize(mask.astype(np.uint8) * 255, (small_width, small_height), interpolation=cv2.INTER_AREA)
    count, _, stats, _ = cv2.connectedComponentsWithStats((small > 96).astype(np.uint8), connectivity=8)
    areas = stats[1:count, cv2.CC_STAT_AREA]
    areas = areas[areas >= MIN_SHAPE_PIXELS]
    if areas.size == 0:
        return 0, 0.0
    return int(areas.size), float(areas.max() / small.size)


def _position(mass: np.ndarray, geometry: Geometry) -> dict[str, float]:
    """Center of mass of ``mass`` (already area-weighted) and its north/south share."""
    total = float(mass.sum())
    if total <= 0:
        return {"centroid_lat": 0.0, "centroid_lon": 0.0, "centroid_x": 0.0, "north_share": 0.5}
    by_row = mass.sum(axis=1)
    by_col = mass.sum(axis=0)
    lon = float((by_col * geometry.lon).sum() / total)
    return {
        "centroid_lat": float((by_row * geometry.lat).sum() / total),
        "centroid_lon": lon,
        "centroid_x": (lon - geometry.center_lon) / geometry.half_span if geometry.half_span else 0.0,
        "north_share": float(by_row[geometry.lat > geometry.split_lat].sum() / total),
    }


def _band_means(volume: np.ndarray, base: np.ndarray, geometry: Geometry) -> dict[str, float]:
    """Mean per latitude band: south, middle, and north."""
    low, high = geometry.band_edges
    bands = {
        "south_mean": geometry.lat < low,
        "middle_mean": (geometry.lat >= low) & (geometry.lat <= high),
        "north_mean": geometry.lat > high,
    }
    result = {}
    for name, rows in bands.items():
        area = float(base[rows].sum())
        result[name] = float(volume[rows].sum() / area) if area > 0 else 0.0
    return result


def _sequential(frame: FrameValues, geometry: Geometry, profile: DatasetProfile) -> dict[str, float]:
    """Features of a low-to-high scale.

    With ``missing_is_zero`` (rain), areas without color have a value of zero
    and count toward the means. Without it (vegetation, which only exists on
    land), means are calculated only over pixels with data.
    """
    values = frame.values
    if profile.missing_is_zero:
        base = geometry.weight
        active = values > 0
    else:
        base = geometry.weight * frame.valid
        active = frame.valid
    base_area = float(base.sum())
    volume = values.astype(np.float64) * base
    total_volume = float(volume.sum())
    active_area = geometry.area(active)

    features = {
        "coverage": geometry.fraction(active),
        "mean": total_volume / base_area if base_area > 0 else 0.0,
        "mean_active": total_volume / active_area if active_area > 0 else 0.0,
        "p05": weighted_percentile(values[active], geometry.weight[active], 5.0),
        "p95": weighted_percentile(values[active], geometry.weight[active], 95.0),
        "max": float(values[active].max()) if active.any() else 0.0,
    }
    for name, threshold in profile.thresholds.items():
        features[f"frac_{name}"] = geometry.fraction(active & (values >= threshold), base_area)
    features.update(_position(volume, geometry))
    features.update(_band_means(volume, base, geometry))
    return features


def _diverging(frame: FrameValues, geometry: Geometry, profile: DatasetProfile) -> dict[str, float]:
    """Features of a scale centered around a midpoint: only pixels with data count."""
    values = frame.values
    valid = frame.valid
    base = geometry.weight * valid
    valid_area = float(base.sum())
    volume = values.astype(np.float64) * base
    center = profile.center

    above = valid & (values > center)
    below = valid & (values < center)
    features = {
        "coverage": geometry.fraction(valid),
        "mean": float(volume.sum() / valid_area) if valid_area > 0 else 0.0,
        "p05": weighted_percentile(values[valid], geometry.weight[valid], 5.0),
        "p95": weighted_percentile(values[valid], geometry.weight[valid], 95.0),
        "min": float(values[valid].min()) if valid.any() else 0.0,
        "max": float(values[valid].max()) if valid.any() else 0.0,
        "frac_above": geometry.fraction(above, valid_area),
        "frac_below": geometry.fraction(below, valid_area),
    }
    features["balance"] = features["frac_above"] - features["frac_below"]
    for name, threshold in profile.thresholds.items():
        mask = valid & ((values >= threshold) if threshold >= center else (values <= threshold))
        features[f"frac_{name}"] = geometry.fraction(mask, valid_area)
    # Where the excess above the midpoint (e.g. heat) is concentrated.
    excess = np.where(above, values - center, 0.0).astype(np.float64) * geometry.weight
    features.update(_position(excess, geometry))
    features.update(_band_means(volume, base, geometry))
    return features


def measure_area(frame: FrameValues, geometry: Geometry, profile: DatasetProfile) -> dict[str, float]:
    """Features for a map or crop; the profile's ``kind`` determines which ones."""
    if profile.kind == "sequential":
        features = _sequential(frame, geometry, profile)
    else:
        features = _diverging(frame, geometry, profile)

    for name, mask in frame.extras.items():
        features[f"frac_{name}"] = geometry.fraction(mask)

    if profile.shape_threshold:
        threshold = profile.thresholds[profile.shape_threshold]
        shapes, largest = count_shapes(frame.valid & (frame.values >= threshold), geometry.lon_span)
        features["shapes_count"] = float(shapes)
        features["shapes_largest"] = largest
    return features


def region_slices(region: Region, shape: tuple[int, int], profile: DatasetProfile) -> tuple[slice, slice]:
    """Map rows and columns that fall within a region's bounding box."""
    height, width = shape
    top, bottom = profile.lat_range
    left, right = profile.lon_range

    def edge(value: float, start: float, end: float, size: int) -> int:
        return int(round(np.clip((value - start) / (end - start), 0.0, 1.0) * size))

    row_a, row_b = sorted((edge(region.lat[1], top, bottom, height), edge(region.lat[0], top, bottom, height)))
    col_a, col_b = sorted((edge(region.lon[0], left, right, width), edge(region.lon[1], left, right, width)))
    return slice(row_a, row_b), slice(col_a, col_b)


def _grid_change(grid: np.ndarray, previous: np.ndarray | None) -> float:
    """Mean difference between two grids, over cells with data in both."""
    if previous is None:
        return 0.0
    both = ~np.isnan(grid) & ~np.isnan(previous)
    return float(np.abs(grid[both] - previous[both]).mean()) if both.any() else 0.0


def summarize(
    frame: FrameValues, profile: DatasetProfile, previous_grid: np.ndarray | None
) -> FrameMeasurement:
    """Calculate features for the full map and each region, along with the grid.

    For the full map, the bands are south, tropics, and north, and
    ``north_share`` is measured relative to the equator. Within a region, the
    bands are its southern, central, and northern thirds, and ``north_share``
    is measured relative to its center.

    Args:
        frame: Frame already converted to values.
        profile: Dataset profile.
        previous_grid: Grid from the previous frame, or ``None`` for the first.
    """
    shape = frame.values.shape
    world = Geometry(
        shape, profile.lat_range, profile.lon_range, (-profile.tropics_lat, profile.tropics_lat), 0.0
    )
    features = measure_area(frame, world, profile)

    uses_valid = profile.kind == "diverging" or not profile.missing_is_zero
    grid_valid = frame.valid if uses_valid else np.ones(shape, dtype=bool)
    grid = block_mean(frame.values, grid_valid, *profile.grid)
    features["change"] = _grid_change(grid, previous_grid)
    features["unmatched_fraction"] = world.fraction(frame.unmatched)

    grid_shape = grid.shape
    regions: dict[str, dict[str, float] | None] = {}
    for region in profile.regions:
        rows, cols = region_slices(region, shape, profile)
        part = frame.crop(rows, cols)
        if part.values.size == 0 or (uses_valid and part.valid.mean() < MIN_COVERAGE):
            regions[region.id] = None
            continue
        south, north = region.lat
        third = (north - south) / 3.0
        geometry = Geometry(
            part.values.shape,
            (north, south),
            region.lon,
            (south + third, north - third),
            (south + north) / 2.0,
        )
        measured = measure_area(part, geometry, profile)
        grid_rows, grid_cols = region_slices(region, grid_shape, profile)
        measured["change"] = _grid_change(
            grid[grid_rows, grid_cols],
            None if previous_grid is None else previous_grid[grid_rows, grid_cols],
        )
        regions[region.id] = measured

    return FrameMeasurement(features=features, grid=grid, regions=regions)
