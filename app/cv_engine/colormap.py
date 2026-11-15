"""Color table → physical value.

Read the official NASA GIBS color table (XML v1.3) and use it to convert each
frame pixel to its value (mm/h). This is the step MobileNetV2 could not
perform: here, every number has a unit and a source.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.cv_engine.exceptions import ColormapError


@dataclass(frozen=True)
class Lut:
    """Color-to-value table ready for inversion.

    Attributes:
        rgb: Table colors, ``uint8`` (N, 3).
        lab: The same colors in CIELAB, ``float32`` (N, 3).
        value: Representative value for each color, ``float32`` (N,).
        low: Lower bound of each interval, ``float32`` (N,).
        section: Index of the source section for each color (N,).
        sections: Section names (e.g. ``("rain", "snow")``).
        unit: Physical unit of ``value``.
    """

    rgb: np.ndarray
    lab: np.ndarray
    value: np.ndarray
    low: np.ndarray
    section: np.ndarray
    sections: tuple[str, ...]
    unit: str

    @property
    def value_range(self) -> tuple[float, float]:
        return float(self.value.min()), float(self.value.max())


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert ``uint8`` colors (N, 3) to true CIELAB (L 0–100)."""
    as_float = (rgb.reshape(-1, 1, 3).astype(np.float32)) / 255.0
    return cv2.cvtColor(as_float, cv2.COLOR_RGB2LAB).reshape(-1, 3)


def _parse_interval(text: str) -> tuple[float, float]:
    """``"[0.1,0.1059)"`` → ``(0.1, 0.1059)``; supports ``-INF`` and ``+INF``."""
    inner = text.strip().strip("[]()")
    low_text, _, high_text = inner.partition(",")

    def to_float(token: str) -> float:
        token = token.strip().upper()
        if token in {"+INF", "INF"}:
            return math.inf
        if token == "-INF":
            return -math.inf
        return float(token)

    low = to_float(low_text)
    high = to_float(high_text) if high_text else low
    return low, high


def _is_log_spaced(intervals: list[tuple[float, float]]) -> bool:
    """Check whether a section's intervals grow proportionally (logarithmic scale).

    In a linear scale, all intervals have the same width; in a logarithmic
    scale, each interval is wider than the previous one.
    """
    widths = [hi - lo for lo, hi in intervals if math.isfinite(lo) and math.isfinite(hi) and lo > 0]
    if len(widths) < 2:
        return False
    return max(widths) > 1.5 * min(widths)


def _representative(low: float, high: float, log_spaced: bool) -> float:
    """Return one value for an interval: its midpoint (geometric for a logarithmic scale)."""
    if math.isinf(high):
        return low
    if math.isinf(low):
        return high
    if log_spaced and low > 0:
        return math.sqrt(low * high)
    return (low + high) / 2.0


def load_gibs_colormap(xml_path: Path, sections: dict[str, str]) -> Lut:
    """Build the table from the official GIBS XML.

    Args:
        xml_path: Path to the color table XML.
        sections: ``{title in XML: short name}``; only these sections are used
            (e.g. ``{"Rain Rate": "rain", "Snow Rate": "snow"}``).

    Raises:
        ColormapError: If the file contains no usable entries.
    """
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ColormapError(f"No se pudo leer la tabla de color {xml_path}: {exc}") from exc

    names = tuple(sections.values())
    rgb: list[tuple[int, int, int]] = []
    value: list[float] = []
    low: list[float] = []
    section: list[int] = []
    unit = ""
    seen: set[tuple[int, int, int]] = set()

    for colormap in root.iter("ColorMap"):
        title = colormap.get("title", "")
        if title not in sections:
            continue
        unit = colormap.get("units", unit)
        index = names.index(sections[title])
        entries: list[tuple[tuple[int, int, int], float, float]] = []
        for entry in colormap.iter("ColorMapEntry"):
            if entry.get("transparent") == "true" or entry.get("nodata") == "true":
                continue
            interval = entry.get("value") or entry.get("sourceValue")
            if not interval:
                continue
            color = tuple(int(c) for c in entry.get("rgb", "").split(","))
            if len(color) != 3 or color in seen:
                continue
            seen.add(color)
            entries.append((color, *_parse_interval(interval)))  # type: ignore[arg-type]
        log_spaced = _is_log_spaced([(lo, hi) for _, lo, hi in entries])
        for color, lo, hi in entries:
            rgb.append(color)
            value.append(_representative(lo, hi, log_spaced))
            low.append(lo)
            section.append(index)

    if not rgb:
        raise ColormapError(f"La tabla {xml_path} no tiene entradas para {list(sections)}")

    rgb_array = np.array(rgb, dtype=np.uint8)
    return Lut(
        rgb=rgb_array,
        lab=rgb_to_lab(rgb_array),
        value=np.array(value, dtype=np.float32),
        low=np.array(low, dtype=np.float32),
        section=np.array(section, dtype=np.int8),
        sections=names,
        unit=unit,
    )


def lut_from_legend(
    image_rgb: np.ndarray,
    box: tuple[float, float, float, float],
    value_min: float,
    value_max: float,
    *,
    scale: str = "linear",
    vertical: bool = False,
    unit: str = "",
    steps: int = 128,
) -> Lut:
    """Build the table by reading the legend bar drawn in an image.

    For visualizations without an official color table: crop the bar, take the
    median color across its width, and distribute values along its length.

    Args:
        image_rgb: ``uint8`` image (H, W, 3) containing the legend.
        box: Bar crop ``(left, top, right, bottom)`` in fractions from 0 to 1.
        value_min: Value at the left endpoint (or bottom if ``vertical``).
        value_max: Value at the opposite endpoint.
        scale: ``"linear"`` or ``"log"``.
        vertical: The bar increases from bottom to top.
        unit: Physical unit.
        steps: Number of colors to sample along the bar.

    Raises:
        ColormapError: If the crop is empty or the scale is invalid.
    """
    height, width = image_rgb.shape[:2]
    left, top, right, bottom = box
    strip = image_rgb[round(top * height) : round(bottom * height), round(left * width) : round(right * width)]
    if strip.size == 0:
        raise ColormapError(f"El recorte de la leyenda {box} queda vacío.")
    if scale == "log" and (value_min <= 0 or value_max <= 0):
        raise ColormapError("Una leyenda logarítmica necesita valores positivos.")

    profile = np.median(strip, axis=1 if vertical else 0)
    if vertical:
        profile = profile[::-1]
    positions = np.linspace(0, len(profile) - 1, min(steps, len(profile))).round().astype(int)
    fractions = positions / max(1, len(profile) - 1)
    if scale == "log":
        values = value_min * (value_max / value_min) ** fractions
    else:
        values = value_min + (value_max - value_min) * fractions

    colors: dict[tuple[int, int, int], list[float]] = {}
    for color, value in zip(profile[positions].astype(np.uint8), values):
        colors.setdefault(tuple(int(c) for c in color), []).append(float(value))
    rgb = np.array(list(colors), dtype=np.uint8)
    value = np.array([float(np.mean(v)) for v in colors.values()], dtype=np.float32)
    return Lut(
        rgb=rgb,
        lab=rgb_to_lab(rgb),
        value=value,
        low=value.copy(),
        section=np.zeros(len(rgb), dtype=np.int8),
        sections=("value",),
        unit=unit,
    )


def _pack(rgb: np.ndarray) -> np.ndarray:
    """Pack (…, 3) ``uint8`` values into a 24-bit integer per color."""
    wide = rgb.astype(np.uint32)
    return (wide[..., 0] << 16) | (wide[..., 1] << 8) | wide[..., 2]


def invert(
    rgb: np.ndarray,
    lut: Lut,
    *,
    candidates: np.ndarray | None = None,
    max_delta_e: float = 0.0,
) -> np.ndarray:
    """Assign each pixel the index of its color in the table.

    First, look for an exact match. If ``max_delta_e`` is greater than zero,
    assign remaining pixels to the nearest color in CIELAB, provided the
    distance does not exceed that limit. This tolerates compressed or
    smoothed frames without mistaking the base map for data.

    Args:
        rgb: ``uint8`` image (H, W, 3) in RGB order.
        lut: Color-to-value table.
        candidates: Boolean mask (H, W) of pixels to consider; ``None``
            considers all pixels.
        max_delta_e: Maximum CIELAB distance for accepting a nearby color.

    Returns:
        ``np.ndarray`` ``int16`` (H, W) with the table index, or ``-1``
        where the pixel is not data.
    """
    height, width = rgb.shape[:2]
    result = np.full((height, width), -1, dtype=np.int16)
    mask = np.ones((height, width), dtype=bool) if candidates is None else candidates
    if not mask.any():
        return result

    packed = _pack(rgb)[mask]
    unique, inverse = np.unique(packed, return_inverse=True)

    lut_packed = _pack(lut.rgb)
    order = np.argsort(lut_packed)
    position = np.searchsorted(lut_packed[order], unique)
    position = np.clip(position, 0, len(order) - 1)
    exact = lut_packed[order][position] == unique
    unique_index = np.where(exact, order[position], -1).astype(np.int16)

    if max_delta_e > 0 and (~exact).any():
        pending = np.flatnonzero(~exact)
        colors = np.stack(
            [(unique[pending] >> 16) & 255, (unique[pending] >> 8) & 255, unique[pending] & 255],
            axis=1,
        ).astype(np.uint8)
        lab = rgb_to_lab(colors)
        for start in range(0, len(pending), 4096):
            chunk = lab[start : start + 4096]
            distance = np.linalg.norm(chunk[:, None, :] - lut.lab[None, :, :], axis=2)
            nearest = distance.argmin(axis=1)
            accepted = distance[np.arange(len(chunk)), nearest] <= max_delta_e
            unique_index[pending[start : start + 4096]] = np.where(accepted, nearest, -1)

    result[mask] = unique_index[inverse]
    return result
