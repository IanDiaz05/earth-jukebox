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
    # La capa es un promedio diario, así que los valores son bajos: 0.5 mm/h
    # sostenidos son 12 mm en el día y 2 mm/h son 48 mm, un día de lluvia fuerte.
    thresholds={"moderate": 0.5, "heavy": 2.0},
    shape_threshold="heavy",
    regions=WORLD,
    hints={
        "story": "seasonal",
        "more_is": "neutral",
        "texture": "rain",
        # La melodía sigue la latitud del centro de la lluvia.
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
        # La melodía sigue la anomalía media: sube cuando el océano se calienta.
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
    # La vegetación solo existe en tierra: el mar no es "cero", es "sin dato".
    missing_is_zero=False,
    thresholds={"sparse": 0.2, "green": 0.5, "dense": 0.7},
    shape_threshold="dense",
    regions=LANDS,
    hints={
        "story": "seasonal",
        "more_is": "good",
        "texture": "leaves",
        # La melodía sigue la latitud del verdor: sube hacia el norte en verano.
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

PROFILES: dict[str, DatasetProfile] = {
    p.id: p for p in (PRECIPITATION, SEA_TEMPERATURE, VEGETATION)
}

def lossy(profile: DatasetProfile, max_delta_e: float = 18.0, despeckle: bool = False) -> DatasetProfile:
    """Profile variant for compressed frames (video, JPEG, screenshots).

    ``despeckle`` removes isolated background pixels, but also erases fine
    structures (rain bands); it is best used only for datasets with large
    features.
    """
    return replace(profile, max_delta_e=max_delta_e, despeckle=despeckle)
