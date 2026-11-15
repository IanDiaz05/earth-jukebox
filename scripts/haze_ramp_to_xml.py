#!/usr/bin/env python3
"""Build a relative scale (XML) for a visualization without a color bar.

Some SVS visualizations draw a single-hue layer over the planet and publish no
scale: the orange CO2 haze (5115) or the yellow lightning flashes (5011). The
physical value cannot be recovered, but the amount can: the denser the layer,
the brighter the hue. This script collects the planet pixels of that hue from
the frames, sorts them by brightness and writes a color -> 0-1 index table.

The index is relative to the visualization itself, not physical units. Check
the SVS page first for a color bar or another version with a scale: on
Perpetual Ocean (5425) the "beauty" colors turned out to be depth, and the page
publishes temperature and salinity versions with official bars.

Usage:
    # Fixed globe: the disk is always the same box.
    python scripts/haze_ramp_to_xml.py --dir frames/VolumetricCO2_Composite \\
        --disk 0.078 0.058 0.921 0.901 --out SVS_5115_CO2_Haze_Index.xml \\
        --title "CO2 Haze" --hue 8 36 --min-saturation 0.6

    # Moving camera: the planet is found in each frame, as the engine does.
    python scripts/haze_ramp_to_xml.py --dir frames/iss_lightning_sphere_07312023_frames \\
        --track --background-max 6 --out SVS_5011_Lightning_Index.xml \\
        --title "Lightning" --hue 35 65 --min-saturation 0.6 --min-brightness 0.35

    # If the layer ends in pure white, add --include-white.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.cv_engine.globe import find_planet  # noqa: E402

COLORMAPS_DIR = PROJECT_ROOT / "app" / "cv_engine" / "colormaps"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
STEPS = 128
MAX_BRIGHTNESS = 1.0
# Below this brightness (0-1) a pixel is background, not layer. Raise it when a
# dark planet surface is confused with the faint end of the layer (lightning).
DEFAULT_MIN_BRIGHTNESS = 0.08


def layer_pixels(
    folder: Path,
    disk: tuple[float, float, float, float] | None,
    hue: tuple[float, float],
    min_saturation: float,
    background_max: int,
    min_brightness: float,
    include_white: bool = False,
) -> np.ndarray:
    """Return ``(N, 3)`` RGB of the planet pixels with the requested hue.

    With ``disk`` the planet is the ellipse inscribed in that box (fixed
    globe); without it, the planet is found in each frame (``track_planet``).
    """
    collected = []
    for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTENSIONS):
        bgr = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
        height, width = bgr.shape[:2]
        if disk is not None:
            left, top, right, bottom = disk
            crop = bgr[round(top * height) : round(bottom * height) : 3, round(left * width) : round(right * width) : 3]
            h, w = crop.shape[:2]
            y, x = np.mgrid[0:h, 0:w]
            inside = ((x + 0.5) / w * 2 - 1) ** 2 + ((y + 0.5) / h * 2 - 1) ** 2 <= 1.0
        else:
            crop = np.ascontiguousarray(bgr[::3, ::3])
            inside = find_planet(crop[..., ::-1], background_max).planet
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
        degrees, sat, value = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
        is_layer = (
            inside & (degrees >= hue[0]) & (degrees <= hue[1]) & (sat >= min_saturation) & (value >= min_brightness)
        )
        if include_white:
            # The top of the layer can be pure white, which has no hue.
            is_layer |= inside & (sat < 0.2) & (value >= 0.6)
        collected.append(crop[is_layer][:, ::-1])
    return np.concatenate(collected)


def ramp(
    rgb: np.ndarray, min_brightness: float, by_luminance: bool = False
) -> list[tuple[tuple[int, int, int], float, float]]:
    """Median color per brightness step: ``[(rgb, low_index, high_index)]``.

    Brightness is the highest channel; with ``by_luminance`` it is the mean of
    the three, which separates white from light blue.
    """
    brightness = (rgb.mean(axis=1) if by_luminance else rgb.max(axis=1)) / 255.0
    edges = np.linspace(min_brightness, MAX_BRIGHTNESS, STEPS + 1)
    span = MAX_BRIGHTNESS - min_brightness
    entries = []
    seen: set[tuple[int, int, int]] = set()
    for i in range(STEPS):
        in_step = (brightness >= edges[i]) & (brightness < edges[i + 1] + (1e-9 if i == STEPS - 1 else 0))
        if in_step.sum() < 50:
            continue
        color = tuple(int(c) for c in np.median(rgb[in_step], axis=0).round())
        if color in seen:
            continue
        seen.add(color)
        entries.append((color, (edges[i] - min_brightness) / span, (edges[i + 1] - min_brightness) / span))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", required=True, help="Folder with the frames.")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--disk", type=float, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
                       help="Fixed globe: disk box as 0-1 fractions (the profile's data_region).")
    where.add_argument("--track", action="store_true", help="Moving camera: find the planet in each frame.")
    parser.add_argument("--background-max", type=int, default=20,
                        help="With --track: maximum brightness (0-255) of space (the profile's background_max).")
    parser.add_argument("--hue", type=float, nargs=2, required=True, metavar=("MIN", "MAX"),
                        help="Hue range of the layer in degrees (orange: 8 36; yellow: 35 65).")
    parser.add_argument("--min-saturation", type=float, default=0.6)
    parser.add_argument("--min-brightness", type=float, default=DEFAULT_MIN_BRIGHTNESS,
                        help="Minimum layer brightness (0-1); index 0 starts here.")
    parser.add_argument("--include-white", action="store_true", help="The layer ends in pure white.")
    parser.add_argument("--title", required=True, help="Section title in the XML.")
    parser.add_argument("--out", required=True, help="XML file name (saved in colormaps/).")
    args = parser.parse_args()

    disk = None if args.track else tuple(args.disk)
    rgb = layer_pixels(
        Path(args.dir), disk, tuple(args.hue), args.min_saturation, args.background_max, args.min_brightness,
        args.include_white,
    )
    entries = ramp(rgb, args.min_brightness, by_luminance=args.include_white)
    if len(entries) < 20:
        raise SystemExit(f"Only {len(entries)} colors found: check --hue and --min-saturation.")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- Generated by scripts/haze_ramp_to_xml.py from the frames in {Path(args.dir).name}. -->",
        "<!-- Relative scale: 0 = barely visible layer, 1 = densest. Not physical units. -->",
        "<ColorMaps>",
        f'  <ColorMap title={quoteattr(args.title)} units="índice">',
        "    <Entries>",
    ]
    lines += [
        f'      <ColorMapEntry rgb="{c[0]},{c[1]},{c[2]}" transparent="false" value="[{lo:.4f},{hi:.4f})"/>'
        for c, lo, hi in entries
    ]
    lines += ["    </Entries>", "  </ColorMap>", "</ColorMaps>", ""]
    destination = COLORMAPS_DIR / args.out
    destination.write_text("\n".join(lines), encoding="utf-8")
    print(f"{destination.name}: {len(entries)} colors from {len(rgb):,} pixels")
    print("  faintest:", entries[0][0], " densest:", entries[-1][0])


if __name__ == "__main__":
    main()
