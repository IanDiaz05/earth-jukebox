# -*- coding: utf-8 -*-
"""Custom exceptions for the visual engine.

Concrete hierarchy (never raise generic ``Exception`` or ``ValueError``
from engine logic):

    MLEngineError
    ├── EmptyDirectoryError
    ├── InvalidProfileError
    └── ColormapError
"""
from __future__ import annotations


class MLEngineError(Exception):
    """Base class for all visual measurement engine errors."""


class EmptyDirectoryError(MLEngineError):
    """The input directory does not exist or contains no frames."""


class InvalidProfileError(MLEngineError):
    """The profile cannot be applied to the data (colormap, legend, or crop)."""


class ColormapError(MLEngineError):
    """The colormap could not be read or contains no usable entries."""
