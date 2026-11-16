# CV engine regions

**Source:** `app/cv_engine/regions.py`

Named regions turn coordinates into readable statements such as "North Atlantic"
instead of a latitude/longitude pair. The boxes are intentionally approximate:
they are for describing where something happens, not for precise geography.

## `Region`

A frozen dataclass with:

| Field | Meaning |
|---|---|
| `id` | Stable identifier used in JSON keys |
| `name` | Human-readable name used in messages |
| `lat` | `(south, north)` latitude bounds |
| `lon` | `(west, east)` longitude bounds |

## Region sets

| Constant | Contents |
|---|---|
| `OCEANS` | Nine ocean regions: Arctic, North Atlantic, South Atlantic, eastern and western North Pacific, equatorial Pacific, South Pacific, Indian Ocean, and Southern Ocean |
| `LANDS` | Eight land regions: North America, South America, Europe, Africa, South Asia, East Asia, Southeast Asia, and Australia |
| `WORLD` | All land regions plus the ocean regions except the Arctic and Southern Ocean |

Profiles attach one of these sets through `DatasetProfile.regions`. The engine
then calculates the full feature set for each region in every frame, and the
pipeline exposes per-region statistics and trends in `dataset_info`.

Globe profiles do not use geographic regions: the view rotates, so the engine
rejects a globe profile that defines them.
