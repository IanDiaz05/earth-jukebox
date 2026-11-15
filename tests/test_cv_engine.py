"""Engine tests with synthetic images (known expected results).

Run from the repository root:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cv_engine.colormap import (  # noqa: E402
    ColormapError,
    _parse_interval,
    invert,
    load_gibs_colormap,
    lut_from_legend,
)
from app.cv_engine.exceptions import (  # noqa: E402
    EmptyDirectoryError,
    InvalidProfileError,
    MLEngineError,
)
from app.cv_engine.globe import find_planet  # noqa: E402
from app.cv_engine.pipeline import (  # noqa: E402
    crop_region,
    frame_to_values,
    load_frame,
    mask_boxes,
    measure_timelapse,
)
from app.cv_engine.profiles import (  # noqa: E402
    PRECIPITATION,
    PROFILES,
    SEA_TEMPERATURE,
    VEGETATION,
    LegendSpec,
    lossy,
)
from app.cv_engine.regions import Region  # noqa: E402
from app.cv_engine.summarize import FrameValues, count_shapes, region_slices, summarize  # noqa: E402
from app.cv_engine.video import extract_frames  # noqa: E402

COLORMAPS = Path(__file__).resolve().parents[1] / "app" / "cv_engine" / "colormaps"

XML = """<?xml version="1.0"?>
<ColorMaps>
  <ColorMap title="Classifications">
    <Entries>
      <ColorMapEntry rgb="128,128,128" transparent="true" nodata="true" ref="0"/>
      <ColorMapEntry rgb="191,191,191" transparent="true" value="[-INF,0.1)" ref="1"/>
    </Entries>
  </ColorMap>
  <ColorMap title="Rain Rate" units="mm/hr">
    <Entries>
      <ColorMapEntry rgb="0,120,80" transparent="false" value="[0.1,1.0)" ref="2"/>
      <ColorMapEntry rgb="240,220,0" transparent="false" value="[1.0,10.0)" ref="3"/>
      <ColorMapEntry rgb="200,0,0" transparent="false" value="[10.0,+INF)" ref="4"/>
    </Entries>
  </ColorMap>
  <ColorMap title="Snow Rate" units="mm/hr">
    <Entries>
      <ColorMapEntry rgb="0,200,255" transparent="false" value="[0.1,1.0)" ref="5"/>
    </Entries>
  </ColorMap>
  <ColorMap title="Anomaly" units="C">
    <Entries>
      <ColorMapEntry rgb="0,0,200" transparent="false" value="[-INF,-1.0)" ref="6"/>
      <ColorMapEntry rgb="250,250,250" transparent="false" value="[-1.0,1.0)" ref="7"/>
      <ColorMapEntry rgb="220,60,0" transparent="false" value="[1.0,3.0)" ref="8"/>
    </Entries>
  </ColorMap>
</ColorMaps>
"""
GREEN, YELLOW, RED, SNOW = (0, 120, 80), (240, 220, 0), (200, 0, 0), (0, 200, 255)
COLD, NEUTRAL, HOT = (0, 0, 200), (250, 250, 250), (220, 60, 0)

RAIN = replace(
    PRECIPITATION,
    colormap_file="colormap.xml",
    grid=(4, 8),
    regions=(Region("west", "Oeste", (-90, 90), (-180, 0)), Region("east", "Este", (-90, 90), (0, 180))),
)
ANOMALY = replace(
    SEA_TEMPERATURE,
    colormap_file="colormap.xml",
    sections={"Anomaly": "anomaly"},
    grid=(4, 8),
    thresholds={"warm": 0.5, "hot": 1.5, "cool": -0.5},
    regions=(Region("north", "Norte", (0, 90), (-180, 180)), Region("south", "Sur", (-90, 0), (-180, 180))),
)


def write_png(path: Path, rgb: np.ndarray, alpha: np.ndarray | None = None) -> None:
    channels = [rgb[..., ::-1]] + ([alpha] if alpha is not None else [])
    ok, buffer = cv2.imencode(".png", np.dstack(channels).astype(np.uint8))
    assert ok
    buffer.tofile(str(path))


def frame_values(values: np.ndarray, valid: np.ndarray | None = None) -> FrameValues:
    valid = (values > 0) if valid is None else valid
    return FrameValues(values.astype(np.float32), valid, {}, np.zeros(values.shape, dtype=bool))


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "colormap.xml").write_text(XML, encoding="utf-8")
        self.lut = load_gibs_colormap(self.root / "colormap.xml", RAIN.sections)

    def tearDown(self) -> None:
        self.tmp.cleanup()


class ColormapTests(Base):
    def test_intervals(self) -> None:
        self.assertEqual(_parse_interval("[0.1,0.1059)"), (0.1, 0.1059))
        self.assertEqual(_parse_interval("[53.0884,+INF)")[0], 53.0884)
        self.assertTrue(np.isinf(_parse_interval("[-INF,0.1)")[0]))

    def test_table_skips_transparent_and_splits_sections(self) -> None:
        self.assertEqual(len(self.lut.rgb), 4)
        self.assertEqual(self.lut.unit, "mm/hr")
        self.assertEqual(self.lut.sections, ("rain", "snow"))
        self.assertEqual(list(self.lut.section), [0, 0, 0, 1])
        # Ever wider intervals: logarithmic scale, geometric center.
        self.assertAlmostEqual(float(self.lut.value[1]), 10**0.5, places=4)
        self.assertAlmostEqual(float(self.lut.value[2]), 10.0, places=4)

    def test_diverging_table_with_open_ends(self) -> None:
        lut = load_gibs_colormap(self.root / "colormap.xml", ANOMALY.sections)
        self.assertEqual([round(float(v), 2) for v in lut.value], [-1.0, 0.0, 2.0])
        self.assertEqual(lut.value_range, (-1.0, 2.0))

    def test_missing_table(self) -> None:
        with self.assertRaises(ColormapError):
            load_gibs_colormap(self.root / "missing.xml", RAIN.sections)

    def test_exact_inversion(self) -> None:
        image = np.zeros((2, 4, 3), dtype=np.uint8)
        image[0] = [GREEN, YELLOW, RED, SNOW]
        image[1] = [(10, 10, 10), GREEN, (255, 255, 255), RED]
        self.assertEqual(invert(image, self.lut).tolist(), [[0, 1, 2, 3], [-1, 0, -1, 2]])

    def test_color_tolerance(self) -> None:
        near = np.array([[(2, 121, 79), (238, 221, 3), (90, 90, 90)]], dtype=np.uint8)
        self.assertEqual(invert(near, self.lut).tolist(), [[-1, -1, -1]])
        self.assertEqual(invert(near, self.lut, max_delta_e=3.0).tolist(), [[0, 1, -1]])

    def test_candidate_mask(self) -> None:
        image = np.full((1, 2, 3), GREEN, dtype=np.uint8)
        mask = np.array([[True, False]])
        self.assertEqual(invert(image, self.lut, candidates=mask).tolist(), [[0, -1]])


class LegendTests(Base):
    def make_legend(self, vertical: bool = False) -> np.ndarray:
        """White image with a bar from blue (0) to red (100)."""
        image = np.full((100, 300, 3), 255, dtype=np.uint8)
        ramp = np.linspace(0, 255, 200).astype(np.uint8)
        if vertical:
            image = np.full((300, 100, 3), 255, dtype=np.uint8)
            image[50:250, 40:60, 0] = ramp[::-1, None]
            image[50:250, 40:60, 1] = 0
            image[50:250, 40:60, 2] = 255 - ramp[::-1, None]
        else:
            image[40:60, 50:250, 0] = ramp[None, :]
            image[40:60, 50:250, 1] = 0
            image[40:60, 50:250, 2] = 255 - ramp[None, :]
        return image

    def test_horizontal_legend(self) -> None:
        lut = lut_from_legend(self.make_legend(), (50 / 300, 0.4, 250 / 300, 0.6), 0.0, 100.0, unit="u")
        self.assertGreater(len(lut.rgb), 100)
        self.assertAlmostEqual(float(lut.value.min()), 0.0, places=3)
        self.assertAlmostEqual(float(lut.value.max()), 100.0, places=3)
        middle = np.array([[(128, 0, 127)]], dtype=np.uint8)
        index = invert(middle, lut, max_delta_e=3.0)[0, 0]
        self.assertAlmostEqual(float(lut.value[index]), 50.0, delta=2.0)

    def test_vertical_log_legend(self) -> None:
        lut = lut_from_legend(
            self.make_legend(vertical=True), (0.4, 50 / 300, 0.6, 250 / 300), 0.1, 100.0, scale="log", vertical=True
        )
        blue = invert(np.array([[(0, 0, 255)]], dtype=np.uint8), lut, max_delta_e=3.0)[0, 0]
        red = invert(np.array([[(255, 0, 0)]], dtype=np.uint8), lut, max_delta_e=3.0)[0, 0]
        self.assertAlmostEqual(float(lut.value[blue]), 0.1, delta=0.01)
        self.assertAlmostEqual(float(lut.value[red]), 100.0, delta=1.0)
        middle = invert(np.array([[(128, 0, 127)]], dtype=np.uint8), lut, max_delta_e=3.0)[0, 0]
        self.assertAlmostEqual(float(lut.value[middle]), 10**0.5, delta=0.3)

    def test_invalid_legend(self) -> None:
        with self.assertRaises(ColormapError):
            lut_from_legend(self.make_legend(), (0.5, 0.5, 0.5, 0.5), 0, 1)
        with self.assertRaises(ColormapError):
            lut_from_legend(self.make_legend(), (0.1, 0.4, 0.9, 0.6), 0, 1, scale="log")

    def test_profile_with_legend_in_image(self) -> None:
        """Full flow without an official table: the legend comes from the frame itself."""
        frames = self.root / "frames"
        frames.mkdir()
        legend = self.make_legend()
        write_png(self.root / "legend.png", legend)
        frame = np.full((120, 300, 3), 255, dtype=np.uint8)
        frame[0:100, 0:150] = (255, 0, 0)  # left half at maximum
        frame[0:100, 150:300] = (0, 0, 255)  # right half at minimum
        frame[100:120] = legend[40:60]  # legend drawn below the map
        write_png(frames / "frame_0001.png", frame)
        profile = replace(
            RAIN,
            sections={},
            legend=LegendSpec("legend.png", (50 / 300, 0.4, 250 / 300, 0.6), 1.0, 100.0, unit="ppm"),
            data_region=(0.0, 0.0, 1.0, 100 / 120),
            thresholds={"heavy": 50.0},
            regions=(),
        )
        result = measure_timelapse(frames, profile)
        features = result["frames"][0]["features"]
        self.assertEqual(result["dataset_info"]["unit"], "ppm")
        self.assertAlmostEqual(features["mean"], 50.5, delta=1.0)
        self.assertAlmostEqual(features["frac_heavy"], 0.5, places=2)
        self.assertLess(features["centroid_x"], 0)


class SequentialTests(Base):
    def measure(self, values: np.ndarray, previous=None):
        return summarize(frame_values(values), RAIN, previous)

    def test_uniform_rain(self) -> None:
        f = self.measure(np.full((40, 80), 2.0)).features
        self.assertAlmostEqual(f["coverage"], 1.0, places=5)
        self.assertAlmostEqual(f["mean"], 2.0, places=5)
        self.assertAlmostEqual(f["centroid_lat"], 0.0, places=3)
        self.assertAlmostEqual(f["centroid_x"], 0.0, places=3)
        self.assertAlmostEqual(f["north_share"], 0.5, places=3)
        self.assertAlmostEqual(f["frac_moderate"], 1.0, places=5)

    def test_no_rain(self) -> None:
        f = self.measure(np.zeros((40, 80))).features
        self.assertEqual((f["coverage"], f["mean"], f["p95"], f["shapes_count"]), (0.0, 0.0, 0.0, 0.0))

    def test_position_and_regions(self) -> None:
        values = np.zeros((40, 80))
        values[:20, :40] = 8.0  # northwest quadrant
        m = self.measure(values)
        f = m.features
        self.assertGreater(f["centroid_lat"], 0)
        self.assertLess(f["centroid_x"], 0)
        self.assertAlmostEqual(f["north_share"], 1.0, places=5)
        self.assertGreater(f["north_mean"], 0)
        self.assertEqual(f["south_mean"], 0.0)
        self.assertAlmostEqual(f["frac_heavy"], 0.25, places=3)
        self.assertGreater(m.regions["west"]["mean"], 0)
        self.assertEqual(m.regions["east"]["mean"], 0.0)

    def test_area_weighting(self) -> None:
        pole = np.zeros((90, 180))
        pole[:10] = 5.0
        equator = np.zeros((90, 180))
        equator[40:50] = 5.0
        self.assertLess(self.measure(pole).features["coverage"], self.measure(equator).features["coverage"])

    def test_change_between_frames(self) -> None:
        a = self.measure(np.zeros((40, 80)))
        b = self.measure(np.full((40, 80), 1.0), previous=a.grid)
        self.assertEqual(a.features["change"], 0.0)
        self.assertAlmostEqual(b.features["change"], 1.0, places=5)
        self.assertEqual(b.grid.shape, (4, 8))

    def test_shapes(self) -> None:
        mask = np.zeros((180, 360), dtype=bool)
        mask[20:40, 20:60] = True
        mask[100:110, 200:220] = True
        mask[150, 300] = True  # too small: not counted
        count, largest = count_shapes(mask)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(largest, (20 * 40) / (180 * 360), places=3)


class DivergingTests(Base):
    def measure(self, values: np.ndarray, valid: np.ndarray, previous=None):
        return summarize(frame_values(values, valid), ANOMALY, previous)

    def test_only_pixels_with_data_count(self) -> None:
        values = np.zeros((40, 80))
        valid = np.zeros((40, 80), dtype=bool)
        valid[:, :40] = True  # the right half is "land"
        values[:, :40] = 2.0
        m = self.measure(values, valid)
        f = m.features
        self.assertAlmostEqual(f["coverage"], 0.5, places=5)
        self.assertAlmostEqual(f["mean"], 2.0, places=5)
        self.assertAlmostEqual(f["frac_above"], 1.0, places=5)
        self.assertAlmostEqual(f["frac_hot"], 1.0, places=5)
        self.assertEqual(f["frac_cool"], 0.0)
        self.assertTrue(np.isnan(m.grid[:, 4:]).all(), "cells without data stay empty")
        self.assertFalse(np.isnan(m.grid[:, :4]).any())

    def test_warm_cold_balance_and_regions(self) -> None:
        values = np.zeros((40, 80))
        values[:20] = 1.0  # warm north
        values[20:] = -1.0  # cold south
        m = self.measure(values, np.ones((40, 80), dtype=bool))
        f = m.features
        self.assertAlmostEqual(f["mean"], 0.0, places=5)
        self.assertAlmostEqual(f["balance"], 0.0, places=5)
        self.assertAlmostEqual(f["frac_warm"], 0.5, places=5)
        self.assertAlmostEqual(f["frac_cool"], 0.5, places=5)
        self.assertGreater(f["centroid_lat"], 0, "the heat is in the north")
        self.assertAlmostEqual(f["north_share"], 1.0, places=5)
        self.assertAlmostEqual(m.regions["north"]["mean"], 1.0, places=5)
        self.assertAlmostEqual(m.regions["south"]["mean"], -1.0, places=5)
        self.assertEqual(m.regions["north"]["frac_warm"], 1.0)
        self.assertEqual(m.regions["south"]["frac_cool"], 1.0)

    def test_region_without_data(self) -> None:
        valid = np.zeros((40, 80), dtype=bool)
        valid[:20] = True
        m = self.measure(np.ones((40, 80)), valid)
        self.assertIsNone(m.regions["south"])


class PipelineTests(Base):
    def make_rain_frames(self) -> Path:
        frames = self.root / "frames"
        frames.mkdir()
        for day, color in (("2025-01-01", GREEN), ("2025-01-15", YELLOW), ("2025-02-01", RED)):
            rgb = np.zeros((40, 80, 3), dtype=np.uint8)
            alpha = np.zeros((40, 80), dtype=np.uint8)
            rgb[10:30, 0:40] = color
            alpha[10:30, 0:40] = 255
            rgb[0:5, 60:80] = SNOW
            alpha[0:5, 60:80] = 255
            write_png(frames / f"frame_{day}.png", rgb, alpha)
        return frames

    def test_frame_to_values(self) -> None:
        frames = self.make_rain_frames()
        values = frame_to_values(*load_frame(frames / "frame_2025-02-01.png"), self.lut, RAIN)
        self.assertAlmostEqual(float(values.values.max()), 10.0, places=4)
        self.assertEqual(int(values.valid.sum()), 20 * 40)
        self.assertEqual(int(values.extras["snow"].sum()), 5 * 20)
        self.assertEqual(int(values.unmatched.sum()), 0)

    def test_output_contract(self) -> None:
        result = measure_timelapse(self.make_rain_frames(), RAIN)
        info = result["dataset_info"]
        self.assertEqual(info["schema_version"], "2.2")
        self.assertEqual((info["kind"], info["unit"], info["frames_count"]), ("sequential", "mm/hr", 3))
        self.assertEqual(info["grid_size"], [4, 8])
        self.assertEqual({k: v["name"] for k, v in info["regions"].items()}, {"west": "Oeste", "east": "Este"})
        self.assertEqual(info["regions"]["west"]["grid_cols"], [0, 4])
        self.assertEqual(info["regions"]["east"]["grid_cols"], [4, 8])
        self.assertEqual(info["regions"]["west"]["lon"], [-180, 0])
        self.assertIn("melody", info["hints"])
        self.assertEqual(info["warnings"], [])
        first, second, third = result["frames"]
        self.assertEqual([f["frame_index"] for f in result["frames"]], [0, 1, 2])
        self.assertEqual(first["date"], "2025-01-01")
        self.assertEqual(set(first["features"]), set(info["feature_names"]))
        self.assertEqual((len(first["grid"]), len(first["grid"][0])), (4, 8))
        self.assertEqual(first["features"]["change"], 0.0)
        self.assertGreater(second["features"]["change"], 0.0)
        self.assertEqual(first["top_region"]["id"], "west")
        self.assertGreater(first["features"]["frac_snow"], 0)

    def test_trend_and_departure(self) -> None:
        result = measure_timelapse(self.make_rain_frames(), RAIN)
        means = [f["features"]["mean"] for f in result["frames"]]
        self.assertTrue(means[0] < means[1] < means[2])
        self.assertGreater(result["dataset_info"]["trends"]["mean"]["slope_per_frame"], 0)
        departures = [f["features"]["mean_departure"] for f in result["frames"]]
        self.assertLess(departures[0], 0)
        self.assertGreater(departures[2], 0)
        self.assertAlmostEqual(sum(departures), 0.0, places=3)

    def test_diverging_timelapse(self) -> None:
        frames = self.root / "sst"
        frames.mkdir()
        for year, color in (("2003-08-15", COLD), ("2014-08-15", NEUTRAL), ("2025-08-15", HOT)):
            rgb = np.zeros((40, 80, 3), dtype=np.uint8)
            alpha = np.zeros((40, 80), dtype=np.uint8)
            rgb[:, :60] = color
            alpha[:, :60] = 255  # the rest is land, transparent
            write_png(frames / f"frame_{year}.png", rgb, alpha)
        result = measure_timelapse(frames, ANOMALY)
        info = result["dataset_info"]
        self.assertEqual((info["kind"], info["center"]), ("diverging", 0.0))
        means = [f["features"]["mean"] for f in result["frames"]]
        self.assertEqual(means, [-1.0, 0.0, 2.0])
        self.assertGreater(info["trends"]["mean"]["fitted_change"], 2.5)
        self.assertIsNone(result["frames"][0]["grid"][0][7], "land cell without data")
        self.assertEqual(result["frames"][2]["features"]["frac_hot"], 1.0)

    def test_compressed_frames(self) -> None:
        """With JPEG the exact reading fails and the tolerant one recovers the data."""
        rgb = np.full((80, 160, 3), (60, 60, 60), dtype=np.uint8)
        rgb[20:60, 40:120] = YELLOW
        _, encoded = cv2.imencode(".jpg", rgb[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 80])
        damaged = cv2.imdecode(encoded, cv2.IMREAD_COLOR)[..., ::-1]
        opaque = np.ones((80, 160), dtype=bool)
        exact = frame_to_values(damaged, opaque, self.lut, RAIN)
        tolerant = frame_to_values(damaged, opaque, self.lut, lossy(RAIN))
        expected = 40 * 80
        self.assertLess(int(exact.valid.sum()), expected * 0.9)
        self.assertGreater(int(tolerant.valid.sum()), expected * 0.9)
        self.assertLess(int(tolerant.valid.sum()), expected * 1.1)

    def test_crop(self) -> None:
        rgb = np.zeros((10, 20, 3), dtype=np.uint8)
        opaque = np.ones((10, 20), dtype=bool)
        cropped, mask = crop_region(rgb, opaque, (0.0, 0.0, 0.5, 0.8))
        self.assertEqual((cropped.shape[:2], mask.shape), ((8, 10), (8, 10)))
        with self.assertRaises(InvalidProfileError):
            crop_region(rgb, opaque, (0.5, 0.5, 0.5, 0.5))

    def test_masked_boxes_do_not_count_or_resize(self) -> None:
        opaque = np.ones((10, 20), dtype=bool)
        masked = mask_boxes(opaque, ((0.0, 0.0, 0.25, 0.2), (0.0, 0.9, 0.5, 1.0)))
        self.assertEqual(masked.shape, (10, 20))
        self.assertEqual(int((~masked).sum()), 5 * 2 + 10 * 1)
        self.assertTrue(opaque.all(), "the original mask is not modified")
        self.assertIs(mask_boxes(opaque, ()), opaque)

    def test_globe_measures_only_the_disk_with_curved_latitude(self) -> None:
        # The whole frame in heavy-rain color: outside the disk does not count.
        frames = self.root / "globe"
        frames.mkdir()
        rgb = np.zeros((80, 80, 3), dtype=np.uint8)
        rgb[:] = RED
        write_png(frames / "f_0.png", rgb)
        globe = replace(RAIN, projection="globe", regions=(), missing_is_zero=False)
        result = measure_timelapse(frames, globe)
        features = result["frames"][0]["features"]
        self.assertEqual(result["dataset_info"]["projection"], "globe")
        self.assertAlmostEqual(features["coverage"], 1.0, places=6)
        self.assertEqual(features["unmatched_fraction"], 0.0)
        self.assertAlmostEqual(features["centroid_lat"], 0.0, places=3)
        self.assertAlmostEqual(features["north_share"], 0.5, places=3)
        self.assertIsNone(result["frames"][0]["grid"][0][0], "the corner is outside the disk")

        # Only the top half: the north, with curved (non-linear) latitude.
        rgb[40:] = 0
        write_png(frames / "f_0.png", rgb)
        north = measure_timelapse(frames, globe)["frames"][0]["features"]
        self.assertAlmostEqual(north["coverage"], 0.5, places=2)
        self.assertEqual(north["north_share"], 1.0)
        self.assertGreater(north["centroid_lat"], 20.0)
        self.assertLess(north["centroid_lat"], 30.0)

    def test_find_planet_ignores_stars_and_fills_crescent(self) -> None:
        rgb = np.zeros((100, 120, 3), dtype=np.uint8)
        cv2.circle(rgb, (60, 50), 40, (40, 40, 40), thickness=-1)
        cv2.circle(rgb, (75, 50), 40, (0, 0, 0), thickness=-1)   # night side: crescent
        rgb[5, 5] = rgb[90, 110] = 255                              # stars
        found = find_planet(rgb, background_max=10)
        self.assertFalse(found.planet[5, 5] or found.planet[90, 110], "stars are not planet")
        left, top, right, bottom = found.box
        self.assertLessEqual(abs(left - 20), 2)
        self.assertLessEqual(abs(top - 10), 2)
        self.assertLessEqual(abs(bottom - 90), 2)
        # The convex hull covers the dark area between the horns (the thin tips
        # are lost when stars are removed, so it does not reach them).
        self.assertTrue(found.planet[50, 45])
        self.assertTrue(found.planet[30, 50])
        self.assertFalse(found.planet[50, 90], "the night side far from the crescent does not count")

    def test_moving_camera_globe_tracks_the_planet(self) -> None:
        # The same planet filled with "heavy rain" at a different place and size:
        # with track_planet the measurement does not change.
        frames = self.root / "camera"
        frames.mkdir()
        for i, (cx, cy, r) in enumerate([(40, 40, 20), (90, 50, 35)]):
            rgb = np.zeros((100, 140, 3), dtype=np.uint8)
            cv2.circle(rgb, (cx, cy), r, RED, thickness=-1)
            rgb[95, 5] = 255   # a star
            write_png(frames / f"f_{i}.png", rgb)
        moving = replace(RAIN, projection="globe", track_planet=True, regions=(), missing_is_zero=False)
        result = measure_timelapse(frames, moving)
        for frame in result["frames"]:
            features = frame["features"]
            # The hull of the pixelated circle adds a 1 px border without color.
            self.assertAlmostEqual(features["coverage"], 1.0, delta=0.02)
            self.assertAlmostEqual(features["north_share"], 0.5, delta=0.05)
            self.assertAlmostEqual(features["centroid_x"], 0.0, delta=0.05)

    def test_globe_rejects_regions(self) -> None:
        frames = self.root / "globe"
        frames.mkdir()
        write_png(frames / "f_0.png", np.zeros((8, 8, 3), dtype=np.uint8))
        with self.assertRaises(InvalidProfileError):
            measure_timelapse(frames, replace(RAIN, projection="globe"))

    def test_masked_boxes_in_measurement(self) -> None:
        # A logo in "heavy rain" color drawn on top must not be measured.
        frames = self.root / "logo"
        frames.mkdir()
        rgb = np.zeros((40, 80, 3), dtype=np.uint8)
        alpha = np.zeros((40, 80), dtype=np.uint8)
        rgb[:8, :16] = RED
        alpha[:8, :16] = 255
        write_png(frames / "f_0.png", rgb, alpha)
        profile = replace(RAIN, mask_boxes=((0.0, 0.0, 0.2, 0.2),))
        masked = measure_timelapse(frames, profile)["frames"][0]["features"]
        unmasked = measure_timelapse(frames, RAIN)["frames"][0]["features"]
        self.assertEqual(masked["coverage"], 0.0)
        self.assertGreater(unmasked["coverage"], 0.0)

    def test_errors(self) -> None:
        (self.root / "empty").mkdir()
        with self.assertRaises(EmptyDirectoryError):
            measure_timelapse(self.root / "empty", RAIN)
        with self.assertRaises(EmptyDirectoryError):
            measure_timelapse(self.root / "missing", RAIN)
        frames = self.make_rain_frames()
        write_png(frames / "frame_2025-03-01.png", np.zeros((20, 40, 3), dtype=np.uint8))
        with self.assertRaises(MLEngineError):
            measure_timelapse(frames, RAIN)
        with self.assertRaises(InvalidProfileError):
            measure_timelapse(frames, replace(RAIN, colormap_file="falta.xml"))

    def test_warning_when_table_does_not_match(self) -> None:
        frames = self.root / "unmatched"
        frames.mkdir()
        rgb = np.full((40, 80, 3), (123, 45, 67), dtype=np.uint8)  # color outside the table
        alpha = np.zeros((40, 80), dtype=np.uint8)
        alpha[:, :40] = 255
        write_png(frames / "frame_0001.png", rgb, alpha)
        result = measure_timelapse(frames, RAIN)
        self.assertEqual(len(result["dataset_info"]["warnings"]), 1)


class VideoTests(Base):
    def test_extract_frames_from_video(self) -> None:
        video = self.root / "clip.avi"
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (64, 32))
        if not writer.isOpened():
            self.skipTest("OpenCV cannot write video on this machine")
        for i in range(30):
            writer.write(np.full((32, 64, 3), i * 8, dtype=np.uint8))
        writer.release()
        total = extract_frames(video, self.root / "out", every=1.0)
        self.assertEqual(total, 3)
        self.assertEqual(len(list((self.root / "out").glob("*.png"))), 3)
        self.assertEqual(extract_frames(video, self.root / "out2", every=0.5, limit=2), 2)
        with self.assertRaises(MLEngineError):
            extract_frames(self.root / "missing.avi", self.root / "out3")


class RegionTests(Base):
    """Each region gets the same features as the full map."""

    def test_region_covering_whole_map_matches_world(self) -> None:
        rng = np.random.default_rng(7)
        values = rng.random((60, 120)).astype(np.float32) * 5
        whole = replace(RAIN, regions=(Region("all", "Todo", (-90, 90), (-180, 180)),))
        m = summarize(frame_values(values), whole, None)
        for name in ("coverage", "mean", "p95", "max", "frac_heavy", "centroid_lon", "shapes_count"):
            self.assertAlmostEqual(m.regions["all"][name], m.features[name], places=4, msg=name)

    def test_region_features_only_see_their_crop(self) -> None:
        values = np.zeros((40, 80), dtype=np.float32)
        values[:, :40] = 4.0  # rain over the whole west and none in the east
        m = summarize(frame_values(values), RAIN, None)
        west, east = m.regions["west"], m.regions["east"]
        self.assertAlmostEqual(west["coverage"], 1.0, places=5)
        self.assertAlmostEqual(west["mean"], 4.0, places=5)
        self.assertAlmostEqual(west["frac_heavy"], 1.0, places=5)
        self.assertEqual((east["coverage"], east["mean"], east["shapes_count"]), (0.0, 0.0, 0.0))
        self.assertAlmostEqual(m.features["mean"], 2.0, places=5)
        self.assertEqual(set(west), set(m.features) - {"unmatched_fraction"})

    def test_position_inside_region_is_relative_to_it(self) -> None:
        box = Region("box", "Caja", (0, 60), (0, 120))
        profile = replace(RAIN, regions=(box,))
        values = np.zeros((180, 360), dtype=np.float32)
        values[30:50, 300:340] = 3.0  # latitudes 40-60 N, longitudes 120-160: outside the box
        values[35:50, 180:200] = 3.0  # latitudes 40-55 N, longitudes 0-20: northwest corner of the box
        region = summarize(frame_values(values), profile, None).regions["box"]
        self.assertLess(region["centroid_x"], -0.5, "against the west edge of the box")
        self.assertAlmostEqual(region["north_share"], 1.0, places=5)  # north of the box center (30 N)
        self.assertGreater(region["north_mean"], 0)
        self.assertEqual(region["south_mean"], 0.0)

    def test_change_per_region(self) -> None:
        a = summarize(frame_values(np.zeros((40, 80), dtype=np.float32)), RAIN, None)
        changed = np.zeros((40, 80), dtype=np.float32)
        changed[:, 40:] = 2.0  # only the east changes
        b = summarize(frame_values(changed), RAIN, a.grid)
        self.assertEqual(b.regions["west"]["change"], 0.0)
        self.assertAlmostEqual(b.regions["east"]["change"], 2.0, places=5)

    def test_region_crop_in_pixels_and_grid(self) -> None:
        europe = Region("europe", "Europa", (36, 72), (-10, 40))
        rows, cols = region_slices(europe, (180, 360), RAIN)
        self.assertEqual((rows.start, rows.stop, cols.start, cols.stop), (18, 54, 170, 220))
        rows, cols = region_slices(europe, (24, 48), PRECIPITATION)
        # 7.5° grid cells: Europe spans 5 rows and 6 columns.
        self.assertEqual((rows.stop - rows.start, cols.stop - cols.start), (5, 6))

    def test_series_and_trend_per_region(self) -> None:
        frames = self.root / "frames"
        frames.mkdir()
        for day, color in (("2025-01-01", GREEN), ("2025-01-15", YELLOW), ("2025-02-01", RED)):
            rgb = np.zeros((40, 80, 3), dtype=np.uint8)
            alpha = np.zeros((40, 80), dtype=np.uint8)
            rgb[:, :40] = color
            alpha[:, :40] = 255
            write_png(frames / f"frame_{day}.png", rgb, alpha)
        result = measure_timelapse(frames, RAIN)
        info = result["dataset_info"]
        self.assertGreater(info["regions"]["west"]["trends"]["mean"]["fitted_change"], 5)
        self.assertEqual(info["regions"]["east"]["trends"]["mean"]["fitted_change"], 0.0)
        stats = info["regions"]["west"]["feature_stats"]["mean"]
        self.assertLess(stats["min"], stats["max"])
        departures = [f["regions"]["west"]["mean_departure"] for f in result["frames"]]
        self.assertAlmostEqual(sum(departures), 0.0, places=3)

    def test_region_without_data_is_skipped_with_warning(self) -> None:
        frames = self.root / "sst"
        frames.mkdir()
        rgb = np.zeros((40, 80, 3), dtype=np.uint8)
        alpha = np.zeros((40, 80), dtype=np.uint8)
        rgb[:20] = HOT
        alpha[:20] = 255  # the south has no data
        write_png(frames / "frame_2025-08-15.png", rgb, alpha)
        result = measure_timelapse(frames, ANOMALY)
        self.assertEqual(list(result["dataset_info"]["regions"]), ["north"])
        self.assertIsNone(result["frames"][0]["regions"]["south"])
        self.assertTrue(any("Sur" in w for w in result["dataset_info"]["warnings"]))


class AdaptabilityTests(Base):
    """A new dataset is added with only a profile."""

    def test_no_data_is_not_zero(self) -> None:
        """Vegetation: the sea does not lower the mean, unlike rain."""
        values = np.zeros((40, 80), dtype=np.float32)
        valid = np.zeros((40, 80), dtype=bool)
        valid[:, :20] = True  # only a quarter of the map is land
        values[:, :20] = 0.6
        land_only = replace(RAIN, missing_is_zero=False, thresholds={"green": 0.5}, shape_threshold=None, regions=())
        as_zero = replace(land_only, missing_is_zero=True)
        f_land = summarize(frame_values(values, valid), land_only, None)
        f_zero = summarize(frame_values(values, valid), as_zero, None)
        self.assertAlmostEqual(f_land.features["mean"], 0.6, places=5)
        self.assertAlmostEqual(f_zero.features["mean"], 0.15, places=5)
        self.assertAlmostEqual(f_land.features["frac_green"], 1.0, places=5)
        self.assertAlmostEqual(f_zero.features["frac_green"], 0.25, places=5)
        self.assertTrue(np.isnan(f_land.grid[:, 4:]).all())
        self.assertFalse(np.isnan(f_zero.grid).any())

    def test_new_profile_with_another_table(self) -> None:
        """Another variable, unit and thresholds: zero engine changes."""
        (self.root / "gas.xml").write_text(
            """<ColorMaps><ColorMap title="Gas" units="ppm"><Entries>
            <ColorMapEntry rgb="10,10,60" transparent="false" value="[380,400)" ref="1"/>
            <ColorMapEntry rgb="200,200,40" transparent="false" value="[400,420)" ref="2"/>
            <ColorMapEntry rgb="220,30,30" transparent="false" value="[420,440)" ref="3"/>
            </Entries></ColorMap></ColorMaps>""",
            encoding="utf-8",
        )
        frames = self.root / "gas"
        frames.mkdir()
        for year, color in (("2005-01-01", (10, 10, 60)), ("2015-01-01", (200, 200, 40)), ("2025-01-01", (220, 30, 30))):
            write_png(frames / f"frame_{year}.png", np.full((40, 80, 3), color, dtype=np.uint8))
        gas = replace(
            RAIN,
            id="gas",
            colormap_file="gas.xml",
            sections={"Gas": "gas"},
            missing_is_zero=False,
            thresholds={"high": 415.0},
            shape_threshold=None,
            hints={"melody": {"feature": "mean", "range": [380, 440]}},
        )
        result = measure_timelapse(frames, gas)
        info = result["dataset_info"]
        self.assertEqual((info["unit"], info["profile_id"]), ("ppm", "gas"))
        self.assertEqual([f["features"]["mean"] for f in result["frames"]], [390.0, 410.0, 430.0])
        self.assertEqual([f["features"]["frac_high"] for f in result["frames"]], [0.0, 0.0, 1.0])
        self.assertAlmostEqual(info["trends"]["mean"]["fitted_change"], 40.0, places=3)
        self.assertEqual(info["hints"]["melody"]["feature"], "mean")

    def test_registered_profiles_are_consistent(self) -> None:
        self.assertEqual(
            set(PROFILES),
            {
                "globe-co2",
                "globe-lightning",
                "globe-ocean-temperature",
                "imerg-precipitation",
                "sst-anomaly",
                "ndvi-vegetation",
                "geos-temperature",
                "geos-wind",
                "geos-precipitation",
                "geos-humidity",
                "geos-pm25",
                "geos-o3",
                "geos-co",
                "geos-nox",
                "ecco2-sst",
            },
        )
        for profile in PROFILES.values():
            self.assertIn(profile.kind, ("sequential", "diverging"))
            self.assertTrue((COLORMAPS / profile.colormap_file).is_file(), profile.colormap_file)
            lut = load_gibs_colormap(COLORMAPS / profile.colormap_file, profile.sections)
            self.assertGreater(len(lut.rgb), 20)
            if profile.shape_threshold:
                self.assertIn(profile.shape_threshold, profile.thresholds)
            for key in ("melody", "level", "brightness", "intensity", "secondary", "texture", "words"):
                self.assertIn(key, profile.hints, f"{profile.id}: missing hint {key}")
            for word in ("subject", "strong", "secondary", "melody", "image"):
                self.assertIn(word, profile.hints["words"], f"{profile.id}: missing word {word}")
            self.assertTrue(profile.label)
            ids = [region.id for region in profile.regions]
            self.assertEqual(len(ids), len(set(ids)))


class RealColormapTests(unittest.TestCase):
    def test_official_rain_table(self) -> None:
        lut = load_gibs_colormap(COLORMAPS / PRECIPITATION.colormap_file, PRECIPITATION.sections)
        self.assertEqual(lut.unit, "mm/hr")
        rain = lut.section == 0
        self.assertGreater(int(rain.sum()), 50)
        self.assertGreater(int((~rain).sum()), 50)
        self.assertTrue(np.all(np.diff(lut.value[rain]) > 0), "the rain scale must be increasing")

    def test_official_temperature_table(self) -> None:
        lut = load_gibs_colormap(COLORMAPS / SEA_TEMPERATURE.colormap_file, SEA_TEMPERATURE.sections)
        self.assertEqual(lut.unit, "°C")
        self.assertTrue(np.all(np.diff(lut.value) > 0))
        low, high = lut.value_range
        self.assertAlmostEqual(low, -3.0, places=3)
        self.assertAlmostEqual(high, 3.0, places=3)

    def test_official_vegetation_table(self) -> None:
        lut = load_gibs_colormap(COLORMAPS / VEGETATION.colormap_file, VEGETATION.sections)
        self.assertTrue(np.all(np.diff(lut.value) > 0))
        low, high = lut.value_range
        self.assertGreaterEqual(low, 0.0)
        self.assertAlmostEqual(high, 1.0, delta=0.02)


if __name__ == "__main__":
    unittest.main()
