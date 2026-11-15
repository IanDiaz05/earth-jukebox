# -*- coding: utf-8 -*-
"""Public interface of the visual measurement engine.

The engine converts color-scaled frames into data with units, using each
visualization's color table (OpenCV + NumPy, no neural networks). It exposes
the pipeline entry point, profiles, and exceptions.
"""
from __future__ import annotations

from app.cv_engine.exceptions import (
    ColormapError,
    EmptyDirectoryError,
    InvalidProfileError,
    MLEngineError,
)
from app.cv_engine.pipeline import SCHEMA_VERSION, load_lut, measure_timelapse
from app.cv_engine.profiles import PROFILES, DatasetProfile, LegendSpec, lossy

__all__ = [
    "measure_timelapse",
    "load_lut",
    "SCHEMA_VERSION",
    "PROFILES",
    "DatasetProfile",
    "LegendSpec",
    "lossy",
    "MLEngineError",
    "EmptyDirectoryError",
    "InvalidProfileError",
    "ColormapError",
]
