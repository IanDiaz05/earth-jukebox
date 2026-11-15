"""Orchestration: frame directory → JSON contract for the frontend."""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.cv_engine.colormap import Lut, invert, load_gibs_colormap, lut_from_legend
from app.cv_engine.exceptions import (
    ColormapError,
    EmptyDirectoryError,
    InvalidProfileError,
    MLEngineError,
)
from app.cv_engine.globe import find_planet
from app.cv_engine.profiles import DatasetProfile
from app.cv_engine.summarize import FrameValues, region_slices, summarize

SCHEMA_VERSION = "2.2"
# Official color tables are bundled with the engine.
COLORMAPS_DIR = Path(__file__).resolve().parent / "colormaps"
VALID_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"})
_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
# Above this threshold, too many opaque pixels are absent from the color table:
# the table or crop most likely does not match the image.
MAX_UNMATCHED_WARNING = 0.02


def _sort_key(path: Path) -> tuple[int, ...]:
    digits = re.findall(r"\d+", path.name)
    return tuple(int(d) for d in digits) if digits else (0,)


def collect_frames(directory: Path) -> list[Path]:
    """Return the directory's frames in numeric order."""
    if not directory.is_dir():
        raise EmptyDirectoryError(f"Directory does not exist: {directory}")
    frames = [
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS
    ]
    if not frames:
        raise EmptyDirectoryError(f"No images in {directory}")
    return sorted(frames, key=_sort_key)


def load_frame(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read a frame as RGB and return its opaque-pixel mask.

    Decode from bytes to support paths containing spaces or accented characters.

    Returns:
        ``(rgb, opaque)``: ``uint8`` image (H, W, 3) and boolean mask (H, W).
        Without an alpha channel, all pixels are considered opaque.
    """
    raw = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise MLEngineError(f"Could not read image: {path}")
    if image.dtype != np.uint8:
        image = cv2.convertScaleAbs(image, alpha=255.0 / np.iinfo(image.dtype).max)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        opaque = image[..., 3] >= 128
        rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    else:
        opaque = np.ones(image.shape[:2], dtype=bool)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return rgb, opaque


def load_lut(dataset_dir: Path, profile: DatasetProfile) -> Lut:
    """Load the profile's color table: an image legend or official XML.

    Search for the XML first in ``app/cv_engine/colormaps/`` and then in the
    dataset directory; the legend image is always in the dataset directory.
    """
    try:
        if profile.legend is not None:
            spec = profile.legend
            image, _ = load_frame(dataset_dir / spec.file)
            return lut_from_legend(
                image,
                spec.box,
                spec.value_min,
                spec.value_max,
                scale=spec.scale,
                vertical=spec.vertical,
                unit=spec.unit,
                steps=spec.steps,
            )
        packaged = COLORMAPS_DIR / profile.colormap_file
        path = packaged if packaged.is_file() else dataset_dir / profile.colormap_file
        return load_gibs_colormap(path, profile.sections)
    except ColormapError as exc:
        raise InvalidProfileError(str(exc)) from exc


def mask_boxes(
    opaque: np.ndarray, boxes: tuple[tuple[float, float, float, float], ...]
) -> np.ndarray:
    """Mark boxes drawn over the map (logos, dates) as no data.

    Boxes are 0-1 fractions of the full image.
    """
    if not boxes:
        return opaque
    height, width = opaque.shape
    masked = opaque.copy()
    for left, top, right, bottom in boxes:
        masked[round(top * height) : round(bottom * height), round(left * width) : round(right * width)] = False
    return masked


def crop_region(
    rgb: np.ndarray, opaque: np.ndarray, region: tuple[float, float, float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """Crop the data area, excluding titles and legends."""
    if region == (0.0, 0.0, 1.0, 1.0):
        return rgb, opaque
    height, width = opaque.shape
    left, top, right, bottom = region
    rows = slice(round(top * height), round(bottom * height))
    cols = slice(round(left * width), round(right * width))
    if rgb[rows, cols].size == 0:
        raise InvalidProfileError(f"Crop {region} leaves the image empty.")
    return rgb[rows, cols], opaque[rows, cols]


def frame_to_values(
    rgb: np.ndarray, opaque: np.ndarray, lut: Lut, profile: DatasetProfile
) -> FrameValues:
    """Convert a frame to physical values using the color table.

    First accept colors that exactly match the table. If the profile has a
    tolerance, assign the remaining pixels to the nearest color within that
    margin (for compressed frames).
    """
    index = invert(rgb, lut, candidates=opaque)
    if profile.max_delta_e > 0:
        pending = opaque & (index < 0)
        loose = invert(rgb, lut, candidates=pending, max_delta_e=profile.max_delta_e)
        accepted = loose >= 0
        if profile.despeckle and accepted.any():
            # A pixel accepted only by tolerance must have neighboring data pixels.
            matched = ((index >= 0) | accepted).astype(np.uint8)
            opened = cv2.morphologyEx(matched, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
            accepted &= opened > 0
        index = np.where(accepted, loose, index)

    matched = index >= 0
    safe = np.clip(index, 0, None)
    section = np.where(matched, lut.section[safe], -1)
    primary = section == 0
    values = np.where(primary, lut.value[safe], 0.0).astype(np.float32)
    extras = {name: section == i for i, name in enumerate(lut.sections) if i > 0}
    return FrameValues(values=values, valid=primary, extras=extras, unmatched=opaque & ~matched)


def _round(value: float | None, digits: int) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def _trends(series: list[dict[str, float]], names: list[str]) -> dict[str, dict[str, float]]:
    """Linear trend of each feature across a frame series."""
    count = len(series)
    if count < 2:
        return {}
    x = np.arange(count, dtype=np.float64)
    trends = {}
    for name in names:
        slope = float(np.polyfit(x, [features[name] for features in series], 1)[0])
        trends[name] = {"slope_per_frame": round(slope, 6), "fitted_change": round(slope * (count - 1), 5)}
    return trends


def _finish_series(series: list[dict[str, float]]) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Add ``mean_departure`` to a feature series and return names and ranges.

    ``mean_departure`` is how far each frame deviates from the series average.
    """
    average = float(np.mean([features["mean"] for features in series]))
    for features in series:
        features["mean_departure"] = round(features["mean"] - average, 5)
    names = list(series[0])
    stats = {
        name: {"min": min(f[name] for f in series), "max": max(f[name] for f in series)} for name in names
    }
    return names, stats


def measure_timelapse(image_directory: Path, profile: DatasetProfile) -> dict[str, Any]:
    """Measure all frames in a directory and build the JSON contract.

    Args:
        image_directory: Directory containing the frames, ordered numerically
            by filename. If the profile uses a drawn legend, its image is
            searched for in the parent directory.
        profile: Dataset profile.

    Returns:
        Dictionary with ``dataset_info`` and ``frames``. Each frame contains
        the full-map features and, under ``regions``, the same features for
        each region.

    Raises:
        EmptyDirectoryError: If there are no frames.
        InvalidProfileError: If the table, legend, or crop is invalid.
        MLEngineError: If a frame cannot be read or changes size.
    """
    frames = collect_frames(image_directory)
    lut = load_lut(image_directory.parent, profile)
    if profile.projection == "globe" and profile.regions:
        raise InvalidProfileError(
            f"{profile.id}: a globe does not support geographic regions (the view rotates)."
        )
    region_names = {region.id: region.name for region in profile.regions}

    records: list[dict[str, Any]] = []
    previous_grid: np.ndarray | None = None
    shape: tuple[int, int] | None = None
    warnings: list[str] = []
    for index, path in enumerate(frames):
        rgb, opaque = load_frame(path)
        has_alpha = not opaque.all()
        opaque = mask_boxes(opaque, profile.mask_boxes)
        rgb, opaque = crop_region(rgb, opaque, profile.data_region)
        if shape is None:
            shape = opaque.shape
        elif opaque.shape != shape:
            raise MLEngineError(f"{path.name} is {opaque.shape}, different from the first frame {shape}.")

        planet = None
        if profile.projection == "globe" and profile.track_planet:
            planet = find_planet(rgb, profile.background_max)
            opaque = opaque & planet.planet
        values = frame_to_values(rgb, opaque, lut, profile)
        measurement = summarize(values, profile, previous_grid, planet)
        previous_grid = measurement.grid

        record: dict[str, Any] = {"frame_index": index, "frame_id": path.name}
        date = _DATE_PATTERN.search(path.name)
        if date:
            record["date"] = date.group(1)
        record["features"] = {k: round(v, 5) for k, v in measurement.features.items()}
        record["regions"] = {
            region_id: None if features is None else {k: round(v, 5) for k, v in features.items()}
            for region_id, features in measurement.regions.items()
        }
        ranked = [(f["mean"], region_id) for region_id, f in measurement.regions.items() if f is not None]
        if ranked:
            top_value, top_id = max(ranked)
            record["top_region"] = {"id": top_id, "name": region_names[top_id], "value": round(top_value, 4)}
        record["grid"] = [[_round(float(v), 3) for v in row] for row in measurement.grid]
        records.append(record)

        # With frames containing a base map, the entire background is unmatched:
        # warn only when the image has transparency and still has excess colors.
        if has_alpha and measurement.features["unmatched_fraction"] > MAX_UNMATCHED_WARNING:
            warnings.append(
                f"{path.name}: {measurement.features['unmatched_fraction']:.1%} of pixels outside the table"
            )

    world = [record["features"] for record in records]
    names, stats = _finish_series(world)

    # Each region has its own series: the same features, ranges, and trends.
    regions_info: dict[str, Any] = {}
    for region in profile.regions:
        series = [record["regions"][region.id] for record in records]
        present = [features for features in series if features is not None]
        if len(present) != len(series):
            # A region with missing data in any frame cannot be played in full.
            for record in records:
                record["regions"][region.id] = None
            warnings.append(f"Region {region.name} has insufficient data: skipped")
            continue
        _, region_stats = _finish_series(present)
        grid_rows, grid_cols = region_slices(region, profile.grid, profile)
        regions_info[region.id] = {
            "name": region.name,
            "lat": list(region.lat),
            "lon": list(region.lon),
            "grid_rows": [grid_rows.start, grid_rows.stop],
            "grid_cols": [grid_cols.start, grid_cols.stop],
            "feature_stats": region_stats,
            "trends": _trends(present, ["mean"]),
        }

    low, high = lut.value_range
    info: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile.id,
        "title": profile.title,
        "label": profile.label,
        "topic": profile.topic,
        "source": profile.source,
        "kind": profile.kind,
        "projection": profile.projection,
        "variable": profile.variable,
        "unit": profile.unit if profile.unit is not None else lut.unit,
        "missing_is_zero": profile.kind == "sequential" and profile.missing_is_zero,
        "value_range": [round(low, 4), round(high, 4)],
        "thresholds": profile.thresholds,
        "grid_size": list(profile.grid),
        "lat_range": list(profile.lat_range),
        "lon_range": list(profile.lon_range),
        "hints": profile.hints,
        "frames_count": len(records),
        "feature_names": names,
        "feature_stats": stats,
        "trends": _trends(world, names),
        "regions": regions_info,
        "warnings": warnings,
    }
    if profile.kind == "diverging":
        info["center"] = profile.center
    return {"dataset_info": info, "frames": records}
