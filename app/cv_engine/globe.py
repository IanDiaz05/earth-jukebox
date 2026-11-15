"""Locate the planet in frames where it is seen as a sphere and the camera moves.

When the camera zooms, pans or the night side is invisible there is no reliable
limb to rebuild the full disk, so only the visible part is used:

- ``planet``: pixels that are planet, without space or stars.
- ``box``: bounding box of that visible part. Positions are measured relative
  to it; when the whole disk is visible the result matches a fixed globe.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class VisiblePlanet:
    """Visible part of the planet in one frame.

    Attributes:
        planet: Boolean mask (H, W) of planet pixels.
        box: ``(left, top, right, bottom)`` in pixels, right and bottom
            exclusive. The whole image when no planet is found.
    """

    planet: np.ndarray
    box: tuple[int, int, int, int]


def find_planet(rgb: np.ndarray, background_max: int = 20) -> VisiblePlanet:
    """Find the visible part of the planet in a frame.

    The planet is the largest bright blob after removing stars and thin lines,
    filled with its convex hull so the dark area between the horns of a
    crescent (where data is also drawn, e.g. lightning flashes) is included.

    Args:
        rgb: ``uint8`` image (H, W, 3).
        background_max: Maximum brightness (0-255, highest channel) of space.
    """
    height, width = rgb.shape[:2]
    bright = (rgb.max(axis=-1) > background_max).astype(np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
    if count <= 1:
        return VisiblePlanet(np.zeros((height, width), dtype=bool), (0, 0, width, height))

    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    contours, _ = cv2.findContours(
        (labels == largest).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    hull = cv2.convexHull(np.vstack(contours))
    planet = np.zeros((height, width), dtype=np.uint8)
    cv2.drawContours(planet, [hull], -1, 1, thickness=cv2.FILLED)
    x, y, w, h = cv2.boundingRect(hull)
    return VisiblePlanet(planet.astype(bool), (x, y, x + w, y + h))
