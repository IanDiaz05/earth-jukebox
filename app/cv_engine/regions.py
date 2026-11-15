"""Named regions for describing in words where something occurs.

They are latitude and longitude boxes, intentionally approximate. They are
used to say "North Atlantic" instead of giving coordinates, not for precise
geography.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """Geographic box. Latitudes run south to north, longitudes west to east."""

    id: str
    name: str
    lat: tuple[float, float]
    lon: tuple[float, float]


OCEANS: tuple[Region, ...] = (
    Region("arctic", "Océano Ártico", (66, 90), (-180, 180)),
    Region("north_atlantic", "Atlántico Norte", (0, 66), (-80, 0)),
    Region("south_atlantic", "Atlántico Sur", (-60, 0), (-60, 20)),
    Region("north_pacific_east", "Pacífico Norte oriental", (0, 66), (-180, -100)),
    Region("north_pacific_west", "Pacífico Norte occidental", (0, 66), (120, 180)),
    Region("tropical_pacific", "Pacífico ecuatorial", (-10, 10), (-170, -90)),
    Region("south_pacific", "Pacífico Sur", (-60, -10), (-180, -75)),
    Region("indian", "Océano Índico", (-60, 25), (40, 110)),
    Region("southern", "Océano Austral", (-70, -45), (-180, 180)),
)

LANDS: tuple[Region, ...] = (
    Region("north_america", "Norteamérica", (15, 72), (-168, -52)),
    Region("south_america", "Sudamérica", (-56, 13), (-82, -34)),
    Region("europe", "Europa", (36, 71), (-10, 40)),
    Region("africa", "África", (-35, 36), (-18, 51)),
    Region("south_asia", "Sur de Asia", (5, 35), (60, 100)),
    Region("east_asia", "Asia oriental", (20, 55), (100, 145)),
    Region("southeast_asia", "Sudeste asiático", (-10, 20), (95, 150)),
    Region("australia", "Australia", (-45, -10), (112, 155)),
)

WORLD: tuple[Region, ...] = LANDS + tuple(r for r in OCEANS if r.id not in {"arctic", "southern"})
