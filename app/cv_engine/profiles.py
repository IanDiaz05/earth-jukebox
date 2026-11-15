"""Visualization profiles: everything the engine needs to know about a dataset.

The profile is the per-dataset "switch." Adding a new EIC visualization means
adding a profile here (and its color table in ``colormaps/``); the rest of the
engine remains unchanged. Two fields determine what is measured:

- ``kind``:
    - ``sequential``: scale from low to high (rain, vegetation, gases).
    - ``diverging``: scale centered around a midpoint (anomalies).
- ``missing_is_zero`` (``sequential`` only): whether an area without color
  means the phenomenon is zero (rain) or simply has no data (vegetation over
  the ocean).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from app.cv_engine.regions import LANDS, OCEANS, WORLD, Region

Kind = Literal["sequential", "diverging"]
Projection = Literal["equirectangular", "globe"]


@dataclass(frozen=True)
class LegendSpec:
    """Legend bar drawn in an image, for use when there is no official table.

    Attributes:
        file: Image containing the legend, relative to the dataset directory.
        box: Bar crop ``(left, top, right, bottom)`` as fractions from 0 to 1
            of the image.
        value_min: Value at the left (or bottom) endpoint of the bar.
        value_max: Value at the right (or top) endpoint.
        scale: ``linear`` or ``log``.
        vertical: ``True`` if the bar runs from bottom (minimum) to top (maximum).
        unit: Physical unit.
        steps: Number of colors to sample along the bar.
    """

    file: str
    box: tuple[float, float, float, float]
    value_min: float
    value_max: float
    scale: Literal["linear", "log"] = "linear"
    vertical: bool = False
    unit: str = ""
    steps: int = 128


@dataclass(frozen=True)
class DatasetProfile:
    """Describe how to read and summarize a visualization with a color scale.

    Attributes:
        id: Short identifier included in the output JSON.
        title: Human-readable name.
        label: Short name for the jukebox selector.
        topic: EIC topic the profile belongs to.
        source: Source of the frames.
        kind: Scale type (see the module header).
        variable: Short name for what is measured.
        colormap_file: Official color table XML. Searched for in
            ``app/cv_engine/colormaps/`` and, if not found, in the dataset
            directory. Ignored if ``legend`` is provided.
        sections: ``{section title in XML: short name}``. The first section is
            the primary variable; the others are measured as area fractions.
        legend: Legend drawn in the image, as an alternative to ``colormap_file``.
        unit: Physical unit; defaults to the unit declared by the color table.
        missing_is_zero: For a ``sequential`` scale, whether a pixel without
            color counts as zero (``True``) or as "no data" (``False``).
        max_delta_e: CIELAB color tolerance. ``0`` requires an exact match
            (source PNG frames); use around 18 for video or JPEG.
        despeckle: Remove isolated pixels accepted only because of tolerance.
        data_region: Image area containing data ``(left, top, right, bottom)``
            as fractions from 0 to 1. Used to exclude titles and legends.
        mask_boxes: Boxes ``(left, top, right, bottom)`` as 0-1 fractions of the
            full image that are ignored (logos or dates drawn over the map).
            Unlike ``data_region`` they do not crop rows or columns.
        projection: ``equirectangular`` (flat map, default) or ``globe`` (the
            planet seen as a sphere). On a globe ``data_region`` is the box
            around the disk and ``lat_range``, ``lon_range`` and ``regions``
            do not apply, because the view can rotate.
        track_planet: Globe only. ``True`` when the camera moves: the visible
            planet is found in each frame and only it is measured.
        background_max: With ``track_planet``, maximum brightness (0-255) of
            space.
        lat_range: Latitudes of the upper and lower edges of ``data_region``.
        lon_range: Longitudes of the left and right edges.
        grid: Exploration grid cells ``(rows, columns)``.
        thresholds: Named thresholds in the table's unit. On a diverging
            scale, thresholds below the center measure "below."
        center: Neutral value of a diverging scale.
        shape_threshold: Threshold delimiting the shapes (storms, heat waves)
            to count.
        tropics_lat: Latitude separating the tropics from the mid-latitudes.
        regions: Named regions; each receives the same features as the full map.
        hints: Hints for the frontend about how to sound. ``melody`` indicates
            which feature controls the melody and its value range; ``level``
            and ``brightness`` control the texture; ``intensity`` determines
            how many points sound; ``secondary`` controls the high-frequency
            brightness. ``words`` provides the names the interface uses to
            describe the dataset, so adding a profile does not require
            changing the frontend.
    """

    id: str
    title: str
    label: str
    topic: str
    source: str
    kind: Kind
    variable: str
    colormap_file: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    legend: LegendSpec | None = None
    unit: str | None = None
    missing_is_zero: bool = True
    max_delta_e: float = 0.0
    despeckle: bool = False
    data_region: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    mask_boxes: tuple[tuple[float, float, float, float], ...] = ()
    projection: Projection = "equirectangular"
    track_planet: bool = False
    background_max: int = 20
    lat_range: tuple[float, float] = (90.0, -90.0)
    lon_range: tuple[float, float] = (-180.0, 180.0)
    grid: tuple[int, int] = (24, 48)
    thresholds: dict[str, float] = field(default_factory=dict)
    center: float = 0.0
    shape_threshold: str | None = None
    tropics_lat: float = 23.5
    regions: tuple[Region, ...] = ()
    hints: dict[str, object] = field(default_factory=dict)


PRECIPITATION = DatasetProfile(
    id="imerg-precipitation",
    title="Precipitation Rate (GPM IMERG)",
    label="Precipitación: un año de lluvias",
    topic="Water resources",
    source="NASA GIBS · IMERG_Precipitation_Rate",
    kind="sequential",
    variable="rain",
    colormap_file="GPM_Precipitation_Rate.xml",
    sections={"Rain Rate": "rain", "Snow Rate": "snow"},
    # The layer is a daily average, so values are low: a sustained 0.5 mm/h is
    # 12 mm per day and 2 mm/h is 48 mm, a day of heavy rain.
    thresholds={"moderate": 0.5, "heavy": 2.0},
    shape_threshold="heavy",
    regions=WORLD,
    hints={
        "story": "seasonal",
        "more_is": "neutral",
        "texture": "rain",
        # The melody follows the latitude of the rain's center.
        "melody": {"feature": "centroid_lat", "range": [-15.0, 15.0]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_heavy",
        "secondary": "frac_snow",
        "words": {
            "subject": "lluvia",
            "strong": "lluvia fuerte",
            "secondary": "nieve",
            "melody": "Centro de la lluvia: nota más aguda = más al norte",
            "image": "Mapa de precipitación",
        },
    },
)

SEA_TEMPERATURE = DatasetProfile(
    id="sst-anomaly",
    title="Sea Surface Temperature Anomalies (GHRSST MUR25)",
    label="Temperatura del mar: 24 años de calentamiento",
    topic="Ocean warming",
    source="NASA GIBS · GHRSST_L4_MUR25_Sea_Surface_Temperature_Anomalies",
    kind="diverging",
    variable="sst_anomaly",
    colormap_file="GHRSST_Sea_Surface_Temperature_Anomalies.xml",
    sections={"Sea Surface Temperature Anomaly": "anomaly"},
    thresholds={"warm": 0.5, "hot": 1.5, "cool": -0.5},
    shape_threshold="hot",
    regions=OCEANS,
    hints={
        "story": "trend",
        "more_is": "alarming",
        "texture": "heat",
        # The melody follows the mean anomaly: it rises as the ocean warms.
        "melody": {"feature": "mean", "range": [-0.25, 0.75]},
        "level": "frac_warm",
        "brightness": "frac_hot",
        "intensity": "frac_hot",
        "secondary": "frac_cool",
        "words": {
            "subject": "calor del mar",
            "strong": "mar muy caliente",
            "secondary": "mar más frío de lo normal",
            "melody": "Anomalía media del mar: la nota sube cuando se calienta",
            "image": "Mapa de anomalía de temperatura de la superficie del mar",
        },
    },
)

VEGETATION = DatasetProfile(
    id="ndvi-vegetation",
    title="Vegetation Index (MODIS Terra NDVI, monthly)",
    label="Vegetación: un año de verdor",
    topic="Agriculture",
    source="NASA GIBS · MODIS_Terra_L3_NDVI_Monthly",
    kind="sequential",
    variable="ndvi",
    colormap_file="MODIS_L3_NDVI.xml",
    sections={"Vegetation Indices": "ndvi"},
    unit="NDVI",
    # Vegetation only exists on land: the sea is not "zero", it is "no data".
    missing_is_zero=False,
    thresholds={"sparse": 0.2, "green": 0.5, "dense": 0.7},
    shape_threshold="dense",
    regions=LANDS,
    hints={
        "story": "seasonal",
        "more_is": "good",
        "texture": "leaves",
        # The melody follows the latitude of greenness: it rises northward in summer.
        "melody": {"feature": "centroid_lat", "range": [5.0, 28.0]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_dense",
        "secondary": "frac_green",
        "words": {
            "subject": "vegetación",
            "strong": "vegetación densa",
            "secondary": "tierra verde",
            "melody": "Centro del verdor: nota más aguda = más al norte",
            "image": "Mapa del índice de vegetación",
        },
    },
)


# --- GEOS-FP (SVS 5147-5150) and GEOS-CF (SVS 5151-5154) -------------------
# Flat 2048x1024 maps. Color tables come from each page's color bar
# (scripts/colorbar_to_xml.py); frames are shaded, so colors are matched with
# tolerance. Melody ranges fit the 32 downloaded frames (about two weeks).
GEOS_MASKS: tuple[tuple[float, float, float, float], ...] = (
    (0.0, 0.0, 0.175, 0.075),   # NASA · GMAO logo
    (0.0, 0.9, 0.25, 1.0),      # date and time
)
GEOS_DELTA_E = 10.0


def _geos(page: int, name: str, model: str = "GEOS-FP") -> str:
    return f"NASA SVS {page} · {model} {name}"


GEOS_TEMPERATURE = DatasetProfile(
    id="geos-temperature",
    title="Near-Surface Temperature (GEOS-FP)",
    label="Temperatura del aire: dos semanas de pronóstico",
    topic="Weather",
    source=_geos(5147, "Near-Surface Temperature"),
    kind="diverging",
    variable="air_temperature",
    colormap_file="GEOS_FP_Near_Surface_Temperature.xml",
    sections={"Near-Surface Temperature": "temperature"},
    center=0.0,
    thresholds={"warm": 20.0, "hot": 30.0, "frigid": -20.0},
    shape_threshold="hot",
    max_delta_e=GEOS_DELTA_E,
    mask_boxes=GEOS_MASKS,
    regions=WORLD,
    hints={
        "story": "weather",
        "more_is": "neutral",
        "texture": "heat",
        "melody": {"feature": "mean", "range": [14.8, 16.0]},
        "level": "frac_above",
        "brightness": "frac_hot",
        "intensity": "frac_hot",
        "secondary": "frac_frigid",
        "words": {
            "subject": "temperatura del aire",
            "strong": "calor extremo",
            "secondary": "frío extremo",
            "melody": "Temperatura media: nota más aguda = planeta más cálido",
            "image": "Mapa de temperatura cerca de la superficie",
        },
    },
)

GEOS_WIND = DatasetProfile(
    id="geos-wind",
    title="Near-Surface Wind Speed (GEOS-FP)",
    label="Viento: tormentas y calmas del planeta",
    topic="Weather",
    source=_geos(5148, "Near-Surface Wind Speed"),
    kind="sequential",
    variable="wind_speed",
    colormap_file="GEOS_FP_Near_Surface_Wind_Speed.xml",
    sections={"Near-Surface Wind Speed": "wind"},
    missing_is_zero=False,
    thresholds={"strong": 15.0, "storm": 25.0},
    shape_threshold="storm",
    max_delta_e=GEOS_DELTA_E,
    mask_boxes=GEOS_MASKS,
    regions=WORLD,
    hints={
        "story": "weather",
        "more_is": "alarming",
        "texture": "rain",
        "melody": {"feature": "mean", "range": [8.7, 9.8]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_storm",
        "secondary": "frac_strong",
        "words": {
            "subject": "viento",
            "strong": "viento de tormenta",
            "secondary": "viento fuerte",
            "melody": "Viento medio: nota más aguda = más viento",
            "image": "Mapa de velocidad del viento",
        },
    },
)

GEOS_PRECIPITATION = DatasetProfile(
    id="geos-precipitation",
    title="Precipitation (GEOS-FP)",
    label="Lluvia: el pronóstico de dos semanas",
    topic="Water resources",
    source=_geos(5149, "Precipitation and Clouds"),
    kind="sequential",
    variable="rain",
    colormap_file="GEOS_FP_Precipitation.xml",
    sections={"Precipitation": "rain"},
    missing_is_zero=True,
    thresholds={"moderate": 1.0, "heavy": 4.0},
    shape_threshold="moderate",
    max_delta_e=GEOS_DELTA_E,
    mask_boxes=GEOS_MASKS,
    regions=WORLD,
    hints={
        "story": "weather",
        "more_is": "neutral",
        "texture": "rain",
        "melody": {"feature": "centroid_lat", "range": [-2.0, 7.0]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_heavy",
        "secondary": "frac_moderate",
        "words": {
            "subject": "lluvia",
            "strong": "lluvia intensa",
            "secondary": "lluvia moderada",
            "melody": "Centro de la lluvia: nota más aguda = más al norte",
            "image": "Mapa de precipitación y nubes",
        },
    },
)

GEOS_HUMIDITY = DatasetProfile(
    id="geos-humidity",
    title="Near-Surface Humidity (GEOS-FP)",
    label="Humedad: dónde el aire carga agua",
    topic="Water resources",
    source=_geos(5150, "Near-Surface Humidity"),
    kind="sequential",
    variable="specific_humidity",
    colormap_file="GEOS_FP_Near_Surface_Humidity.xml",
    sections={"Near-Surface Humidity": "humidity"},
    missing_is_zero=False,
    thresholds={"humid": 14.0, "very_humid": 18.0},
    shape_threshold="very_humid",
    max_delta_e=GEOS_DELTA_E,
    mask_boxes=GEOS_MASKS,
    regions=WORLD,
    hints={
        "story": "weather",
        "more_is": "neutral",
        "texture": "rain",
        "melody": {"feature": "centroid_lat", "range": [-1.5, 1.5]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_very_humid",
        "secondary": "frac_humid",
        "words": {
            "subject": "humedad",
            "strong": "aire muy húmedo",
            "secondary": "aire húmedo",
            "melody": "Centro de la humedad: nota más aguda = más al norte",
            "image": "Mapa de humedad cerca de la superficie",
        },
    },
)

GEOS_PM25 = DatasetProfile(
    id="geos-pm25",
    title="Particulate Matter PM2.5 (GEOS-CF)",
    label="Partículas finas: el aire que respiramos",
    topic="Air quality",
    source=_geos(5151, "PM2.5", "GEOS-CF"),
    kind="sequential",
    variable="pm25",
    colormap_file="GEOS_CF_PM25.xml",
    sections={"PM2.5": "pm25"},
    missing_is_zero=False,
    # WHO daily guideline and EPA daily limit.
    thresholds={"who_limit": 15.0, "unhealthy": 35.0},
    shape_threshold="unhealthy",
    max_delta_e=GEOS_DELTA_E,
    mask_boxes=GEOS_MASKS,
    regions=WORLD,
    hints={
        "story": "weather",
        "more_is": "alarming",
        "texture": "heat",
        "melody": {"feature": "mean", "range": [1.5, 2.5]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_unhealthy",
        "secondary": "frac_who_limit",
        "words": {
            "subject": "partículas finas",
            "strong": "aire insalubre",
            "secondary": "aire sobre la guía de la OMS",
            "melody": "Partículas medias: nota más aguda = aire más sucio",
            "image": "Mapa de partículas finas PM2.5",
        },
    },
)

GEOS_O3 = DatasetProfile(
    id="geos-o3",
    title="Near-Surface Ozone (GEOS-CF)",
    label="Ozono a ras de suelo",
    topic="Air quality",
    source=_geos(5152, "Near-Surface Ozone", "GEOS-CF"),
    kind="sequential",
    variable="o3",
    colormap_file="GEOS_CF_O3.xml",
    sections={"Ozone": "o3"},
    missing_is_zero=False,
    thresholds={"elevated": 40.0, "high": 50.0},
    shape_threshold="high",
    max_delta_e=GEOS_DELTA_E,
    mask_boxes=GEOS_MASKS,
    regions=WORLD,
    hints={
        "story": "weather",
        "more_is": "alarming",
        "texture": "heat",
        "melody": {"feature": "mean", "range": [39.0, 41.5]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_high",
        "secondary": "frac_elevated",
        "words": {
            "subject": "ozono",
            "strong": "ozono alto",
            "secondary": "ozono elevado",
            "melody": "Ozono medio: nota más aguda = más ozono",
            "image": "Mapa de ozono cerca de la superficie",
        },
    },
)

GEOS_CO = DatasetProfile(
    id="geos-co",
    title="Carbon Monoxide (GEOS-CF)",
    label="Monóxido de carbono: humo de incendios y ciudades",
    topic="Air quality",
    source=_geos(5153, "Carbon Monoxide", "GEOS-CF"),
    kind="sequential",
    variable="co",
    colormap_file="GEOS_CF_CO.xml",
    sections={"Carbon Monoxide": "co"},
    missing_is_zero=False,
    thresholds={"elevated": 130.0, "high": 200.0},
    shape_threshold="high",
    max_delta_e=GEOS_DELTA_E,
    mask_boxes=GEOS_MASKS,
    regions=WORLD,
    hints={
        "story": "weather",
        "more_is": "alarming",
        "texture": "heat",
        "melody": {"feature": "mean", "range": [74.0, 84.0]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_high",
        "secondary": "frac_elevated",
        "words": {
            "subject": "monóxido de carbono",
            "strong": "humo denso",
            "secondary": "monóxido elevado",
            "melody": "Monóxido medio: nota más aguda = más humo",
            "image": "Mapa de monóxido de carbono",
        },
    },
)

GEOS_NOX = DatasetProfile(
    id="geos-nox",
    title="Nitrogen Oxides (GEOS-CF)",
    label="Óxidos de nitrógeno: el rastro del tráfico y la industria",
    topic="Air quality",
    source=_geos(5154, "Nitrogen Oxides", "GEOS-CF"),
    kind="sequential",
    variable="nox",
    colormap_file="GEOS_CF_NOx.xml",
    sections={"Nitrogen Oxides": "nox"},
    missing_is_zero=False,
    thresholds={"elevated": 1.0, "high": 10.0},
    shape_threshold="elevated",
    max_delta_e=GEOS_DELTA_E,
    mask_boxes=GEOS_MASKS,
    regions=WORLD,
    hints={
        "story": "weather",
        "more_is": "alarming",
        "texture": "heat",
        "melody": {"feature": "frac_elevated", "range": [0.095, 0.13]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_high",
        "secondary": "frac_elevated",
        "words": {
            "subject": "óxidos de nitrógeno",
            "strong": "contaminación alta",
            "secondary": "contaminación elevada",
            "melody": "Zonas contaminadas: nota más aguda = más superficie contaminada",
            "image": "Mapa de óxidos de nitrógeno",
        },
    },
)


# --- ECCO2 (SVS 3912) -------------------------------------------------------
# Currents drawn as shaded strokes colored by sea surface temperature; only
# the strokes are data (~6 % of the map is readable).
ECCO2_SST = DatasetProfile(
    id="ecco2-sst",
    title="Global Sea Surface Currents and Temperature (ECCO2)",
    label="Corrientes del océano y su temperatura",
    topic="Ocean currents",
    source="NASA SVS 3912 · ECCO2 Sea Surface Currents and Temperature",
    kind="sequential",
    variable="sst",
    colormap_file="ECCO2_Sea_Surface_Temperature.xml",
    sections={"Sea Surface Temperature": "sst"},
    missing_is_zero=False,
    thresholds={"tropical": 20.0, "hurricane": 26.5},
    shape_threshold="hurricane",
    max_delta_e=30.0,
    regions=(),
    hints={
        "story": "seasonal",
        "more_is": "neutral",
        "texture": "heat",
        "melody": {"feature": "centroid_lat", "range": [-2.0, 6.0]},
        "level": "mean",
        "brightness": "p95",
        "intensity": "frac_hurricane",
        "secondary": "frac_tropical",
        "words": {
            "subject": "temperatura del mar",
            "strong": "agua de huracán",
            "secondary": "agua tropical",
            "melody": "Centro del agua cálida: nota más aguda = más al norte",
            "image": "Mapa de corrientes y temperatura del mar",
        },
    },
)


# --- Globes -----------------------------------------------------------------
# GLOBE_CO2 is the base profile for planets seen as a sphere; derive others
# with ``replace``. SVS 5115 publishes no color bar: its table is a relative
# 0-1 haze index (scripts/haze_ramp_to_xml.py), not ppm.
GLOBE_CO2 = DatasetProfile(
    id="globe-co2",
    title="Global Atmospheric Carbon Dioxide, volumetric (GEOS)",
    label="CO₂: la respiración del planeta en un año",
    topic="Carbon dioxide",
    source="NASA SVS 5115 · Global Atmospheric Carbon Dioxide (CO₂)",
    kind="sequential",
    variable="co2_haze",
    colormap_file="SVS_5115_CO2_Haze_Index.xml",
    sections={"CO2 Haze": "haze"},
    unit="índice",
    missing_is_zero=False,
    projection="globe",
    data_region=(0.078, 0.058, 0.921, 0.901),
    lat_range=(90.0, -90.0),
    lon_range=(-90.0, 90.0),
    max_delta_e=8.0,
    thresholds={"dense": 0.3, "very_dense": 0.5},
    shape_threshold="very_dense",
    regions=(),
    hints={
        "story": "seasonal",
        "more_is": "alarming",
        "texture": "heat",
        "melody": {"feature": "mean", "range": [0.2, 0.55]},
        "level": "frac_dense",
        "brightness": "p95",
        "intensity": "frac_very_dense",
        "secondary": "north_share",
        "words": {
            "subject": "dióxido de carbono",
            "strong": "bruma muy densa",
            "secondary": "bruma en el hemisferio norte",
            "melody": "Bruma de CO₂: nota más aguda = más CO₂ acumulado",
            "image": "Globo con la bruma de dióxido de carbono",
        },
    },
)


# Moving-camera globes: ``track_planet`` finds the visible planet in each
# frame, so values follow what the camera frames.
GLOBE_LIGHTNING = replace(
    GLOBE_CO2,
    id="globe-lightning",
    title="Lightning Events Detected from the ISS 2017-2023",
    label="Rayos: las tormentas vistas desde la Estación Espacial",
    topic="Weather",
    source="NASA SVS 5011 · Lightning Events Detected from the ISS 2017-2023",
    variable="lightning",
    colormap_file="SVS_5011_Lightning_Index.xml",
    sections={"Lightning": "flash"},
    unit="índice",
    missing_is_zero=True,
    track_planet=True,
    background_max=6,
    data_region=(0.0, 0.0, 1.0, 1.0),
    max_delta_e=12.0,
    thresholds={"flash": 0.2, "bright_flash": 0.5},
    shape_threshold="flash",
    hints={
        "story": "weather",
        "more_is": "neutral",
        "texture": "rain",
        "melody": {"feature": "coverage", "range": [0.0, 0.06]},
        "level": "coverage",
        "brightness": "p95",
        "intensity": "frac_flash",
        "secondary": "frac_bright_flash",
        "words": {
            "subject": "rayos",
            "strong": "destellos intensos",
            "secondary": "tormentas eléctricas",
            "melody": "Rayos a la vista: nota más aguda = más destellos",
            "image": "Globo con los rayos detectados desde la ISS",
        },
    },
)


# Perpetual Ocean 2 (SVS 5425), temperature version with its official bar.
# The table starts at 4 °C: colder colors match the ocean background.
GLOBE_OCEAN_TEMPERATURE = replace(
    GLOBE_CO2,
    id="globe-ocean-temperature",
    title="Perpetual Ocean 2: Western Boundary Currents (temperature)",
    label="Corrientes del océano y su temperatura: un viaje por el planeta",
    topic="Ocean currents",
    source="NASA SVS 5425 · Perpetual Ocean 2, temperature version",
    variable="current_temperature",
    colormap_file="SVS_5425_PO2_Temperature.xml",
    sections={"Ocean Temperature": "temperature"},
    unit="°C",
    missing_is_zero=False,
    track_planet=True,
    background_max=20,
    data_region=(0.0, 0.0, 1.0, 1.0),
    max_delta_e=14.0,
    thresholds={"temperate": 10.0, "warm": 20.0},
    shape_threshold="warm",
    hints={
        "story": "weather",
        "more_is": "neutral",
        "texture": "heat",
        "melody": {"feature": "mean", "range": [9.0, 18.0]},
        "level": "coverage",
        "brightness": "p95",
        "intensity": "frac_warm",
        "secondary": "frac_temperate",
        "words": {
            "subject": "temperatura de las corrientes",
            "strong": "corrientes cálidas",
            "secondary": "agua templada",
            "melody": "Temperatura del agua en movimiento: nota más aguda = más cálida",
            "image": "Globo con las corrientes coloreadas por temperatura",
        },
    },
)

PROFILES: dict[str, DatasetProfile] = {
    p.id: p
    for p in (
        PRECIPITATION,
        SEA_TEMPERATURE,
        VEGETATION,
        GEOS_TEMPERATURE,
        GEOS_WIND,
        GEOS_PRECIPITATION,
        GEOS_HUMIDITY,
        GEOS_PM25,
        GEOS_O3,
        GEOS_CO,
        GEOS_NOX,
        ECCO2_SST,
        GLOBE_CO2,
        GLOBE_LIGHTNING,
        GLOBE_OCEAN_TEMPERATURE,
    )
}

def lossy(profile: DatasetProfile, max_delta_e: float = 18.0, despeckle: bool = False) -> DatasetProfile:
    """Profile variant for compressed frames (video, JPEG, screenshots).

    ``despeckle`` removes isolated background pixels, but also erases fine
    structures (rain bands); it is best used only for datasets with large
    features.
    """
    return replace(profile, max_delta_e=max_delta_e, despeckle=despeckle)
