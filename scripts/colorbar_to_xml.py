#!/usr/bin/env python3
"""Build GIBS-format color tables (XML) from SVS color bar images.

SVS visualizations do not publish a GIBS XML, only an image of their color
bar. This script reads the color of each bar column and assigns it a value
from the scale ticks, interpolating linearly or logarithmically between ticks.

- GEOS-FP (pages 5147-5150) and GEOS-CF (5151-5154): the plain version
  (``*_colorbar_plain.png``, 528 px wide, white border). Tick positions were
  measured on the bar (white ticks on the bottom edge).

  What the ticks confirm and what is assumed:

  - Temperature, wind, precipitation, humidity: evenly spaced ticks -> linear.
    The temperature bar reads "-40 -10 -20 ...": by tick position the second
    value is -30 (SVS typo).
  - PM2.5: evenly spaced ticks, x2 per tick -> logarithmic.
  - O3: the 40 tick sits where a linear 5-60 scale puts it; the 20 tick is
    not visible (white on white).
  - CO (40, 100, 130, 200, 500) and NOx (decades 1e-3 to 1e1): ticks are
    where listed but not evenly spaced. Log interpolation between ticks is an
    ASSUMPTION. NOx above 10 ppbv is extrapolated.
  - Wind below ~3.6 m/s is transparent on the bar (not drawn).
  - Precipitation: the bar says "mm" with no time base: UNCONFIRMED.
- ECCO2 (page 3912): ``sst_ecco2_cbar.png`` (310 px, black border), with the
  bar interior given by ``box``.
- Perpetual Ocean 2 (page 5425): 16-bit 1920x1080 bar, evenly spaced major
  ticks (0-25 °C, linear). The table starts at 4 °C because colder colors
  match the ocean background in the frames. The salinity version (33-36 PSU)
  was discarded: its gray middle matches land, ice and clouds.

Usage:
    python scripts/colorbar_to_xml.py --bars folder/with/pngs
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

import cv2
import numpy as np

COLORMAPS_DIR = Path(__file__).resolve().parents[1] / "app" / "cv_engine" / "colormaps"
GEOS = "https://svs.gsfc.nasa.gov/vis/a000000/a005100"
PO2 = "https://svs.gsfc.nasa.gov/vis/a000000/a005400/a005425"


@dataclass(frozen=True)
class Bar:
    """A color bar image and how to read its values.

    Attributes:
        url: Bar image on the SVS; the local file has the same name.
        title: Section title in the XML.
        unit: Physical unit.
        scale: ``linear`` or ``log`` interpolation between ticks.
        ticks: ``(x in pixels, value)`` pairs.
        output: XML file name.
        box: Bar interior ``(x0, x1, y0, y1)`` in pixels; ``None`` finds the
            white border.
    """

    url: str
    title: str
    unit: str
    scale: str
    ticks: tuple[tuple[float, float], ...]
    output: str
    box: tuple[int, int, int, int] | None = None

    @property
    def png(self) -> str:
        return self.url.rsplit("/", 1)[-1]


BARS = (
    Bar(f"{GEOS}/a005147/NearSurfaceTemperature_colorbar_plain.png", "Near-Surface Temperature", "°C",
        "linear", ((71.5, -40.0), (463.5, 40.0)), "GEOS_FP_Near_Surface_Temperature.xml"),
    Bar(f"{GEOS}/a005148/NearSurfaceWindSpeed_colorbar_plain.png", "Near-Surface Wind Speed", "m/s",
        "linear", ((71.5, 0.0), (463.5, 40.0)), "GEOS_FP_Near_Surface_Wind_Speed.xml"),
    Bar(f"{GEOS}/a005149/Precipitation_colorbar_plain.png", "Precipitation", "mm",
        "linear", ((71.5, 0.0), (463.5, 20.0)), "GEOS_FP_Precipitation.xml"),
    Bar(f"{GEOS}/a005150/NearSurfaceHumidity_colorbar_plain.png", "Near-Surface Humidity", "g/kg",
        "linear", ((71.5, 0.0), (463.5, 22.0)), "GEOS_FP_Near_Surface_Humidity.xml"),
    Bar(f"{GEOS}/a005151/PM2.5_colorbar_plain.png", "PM2.5", "µg/m³",
        "log", ((72.5, 0.4), (463.5, 409.6)), "GEOS_CF_PM25.xml"),
    Bar(f"{GEOS}/a005152/O3_colorbar_plain.png", "Ozone", "ppbv",
        "linear", ((71.5, 5.0), (319.5, 40.0), (463.5, 60.0)), "GEOS_CF_O3.xml"),
    Bar(f"{GEOS}/a005153/CO_colorbar_plain.png", "Carbon Monoxide", "ppbv",
        "log", ((72.0, 40.0), (188.5, 100.0), (279.5, 130.0), (370.5, 200.0), (464.5, 500.0)),
        "GEOS_CF_CO.xml"),
    Bar(f"{GEOS}/a005154/NOx_colorbar_plain.png", "Nitrogen Oxides", "ppbv",
        "log", ((72.0, 1e-3), (176.5, 1e-2), (280.5, 1e-1), (358.5, 1.0), (438.5, 10.0)),
        "GEOS_CF_NOx.xml"),
    Bar("https://svs.gsfc.nasa.gov/vis/a000000/a003900/a003912/sst_ecco2_cbar.png",
        "Sea Surface Temperature", "°C", "linear", ((14.5, 0.0), (291.5, 32.0)),
        "ECCO2_Sea_Surface_Temperature.xml", box=(16, 291, 30, 67)),
    Bar(f"{PO2}/perpetual_ocean2_CLOSE_101_cbar_temperature.png", "Ocean Temperature", "°C",
        "linear", ((263.5, 0.0), (1655.5, 25.0)), "SVS_5425_PO2_Temperature.xml",
        box=(487, 1654, 505, 576)),
)


def value_at(x: float, bar: Bar) -> float:
    """Value at position ``x``, interpolating between ticks (extrapolating at the ends)."""
    ticks = bar.ticks
    for (x0, v0), (x1, v1) in zip(ticks, ticks[1:]):
        if x <= x1 or (x1, v1) == ticks[-1]:
            t = (x - x0) / (x1 - x0)
            if bar.scale == "log":
                return math.exp(math.log(v0) + t * (math.log(v1) - math.log(v0)))
            return v0 + t * (v1 - v0)
    raise AssertionError("unreachable")


def _box_from_white_border(image: np.ndarray) -> tuple[int, int, int, int]:
    """Interior of a GEOS bar, delimited by a 2-3 px white border."""
    alpha = image[..., 3]
    white = (alpha > 200) & (image[..., :3].min(-1) > 235)
    rows = np.where(white.sum(1) > 300)[0]
    top, bottom = rows[0] + 3, rows[-1] - 3
    band = white[top:bottom]
    # Skip at most 3 px: some bars (ozone) start with pure white data.
    border = np.where(band.all(0))[0]
    left, right = border[0], border[-1]
    for _ in range(3):
        if band[:, left].all():
            left += 1
        if band[:, right].all():
            right -= 1
    return left, right + 1, top, bottom


def column_colors(image: np.ndarray, bar: Bar) -> list[tuple[int, tuple[int, int, int]]]:
    """Median color of each bar column; columns with transparency are skipped."""
    x0, x1, y0, y1 = bar.box or _box_from_white_border(image)
    rgb = cv2.cvtColor(image[..., :3], cv2.COLOR_BGR2RGB)
    result = []
    for x in range(x0, x1):
        if (image[y0:y1, x, 3] < 250).any():
            continue
        color = np.median(rgb[y0:y1, x], axis=0).round().astype(int)
        result.append((x, tuple(int(c) for c in color)))
    return result


def write_xml(bar: Bar, columns: list[tuple[int, tuple[int, int, int]]], destination: Path) -> int:
    """Write the table and return the number of distinct colors."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- Generated by scripts/colorbar_to_xml.py from {bar.url} -->",
        "<ColorMaps>",
        f"  <ColorMap title={quoteattr(bar.title)} units={quoteattr(bar.unit)}>",
        "    <Entries>",
    ]
    seen: set[tuple[int, int, int]] = set()
    for x, color in columns:
        if color in seen:
            continue
        seen.add(color)
        low, high = value_at(x - 0.5, bar), value_at(x + 0.5, bar)
        lines.append(
            f'      <ColorMapEntry rgb="{color[0]},{color[1]},{color[2]}" transparent="false" '
            f'value="[{low:.6g},{high:.6g})"/>'
        )
    lines += ["    </Entries>", "  </ColorMap>", "</ColorMaps>", ""]
    destination.write_text("\n".join(lines), encoding="utf-8")
    return len(seen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bars", required=True, help="Folder with the downloaded bar images.")
    parser.add_argument("--output", default=str(COLORMAPS_DIR), help="Destination folder for the XML files.")
    args = parser.parse_args()

    for bar in BARS:
        path = Path(args.bars) / bar.png
        image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)
        if image is None or image.ndim != 3 or image.shape[2] != 4:
            raise SystemExit(f"Could not read {path} with an alpha channel (download it from {bar.url}).")
        if image.dtype == np.uint16:
            image = np.round(image / 257.0).astype(np.uint8)
        columns = column_colors(image, bar)
        n = write_xml(bar, columns, Path(args.output) / bar.output)
        first, last = columns[0][0], columns[-1][0]
        print(
            f"{bar.output}: {n} colors, "
            f"{value_at(first - 0.5, bar):.4g} to {value_at(last + 0.5, bar):.4g} {bar.unit}"
        )


if __name__ == "__main__":
    main()
