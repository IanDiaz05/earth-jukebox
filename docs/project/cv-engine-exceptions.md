# CV engine exceptions

**Source:** `app/cv_engine/exceptions.py`

The engine uses a small exception hierarchy so callers can distinguish data
problems from configuration problems. Engine code does not raise generic
`Exception` or `ValueError`.

```text
MLEngineError
├── EmptyDirectoryError
├── InvalidProfileError
└── ColormapError
```

| Exception | Meaning | Typical cause |
|---|---|---|
| `MLEngineError` | Base class for all engine errors | Unreadable frame, frame size mismatch, invalid video interval |
| `EmptyDirectoryError` | The input directory is missing or has no frames | Wrong path or empty dataset |
| `InvalidProfileError` | The profile cannot be applied to the data | Bad color table, legend, crop, or a globe profile with regions |
| `ColormapError` | The color table cannot be read or has no usable entries | Malformed XML, empty legend crop, invalid logarithmic endpoints |

## How they are used

- The pipeline raises `EmptyDirectoryError` before processing when there is
  nothing to measure.
- Color-table functions raise `ColormapError`; `load_lut` converts it to
  `InvalidProfileError` because it means the profile and data do not match.
- `MLEngineError` covers frame-level failures and invalid extraction arguments.
- The API startup check catches `MLEngineError` when probing profiles, so a
  broken table is logged and the profile is marked unavailable instead of
  crashing the app.

Callers that need to report a friendly message can catch `MLEngineError` and
use the message as-is.
