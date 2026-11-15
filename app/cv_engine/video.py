"""Extract PNG frames from a video (e.g. an animated EIC visualization).

Video frames are compressed: use the tolerant profile (``lossy(profile)``)
when measuring them.
"""
from __future__ import annotations

from pathlib import Path

import cv2

from app.cv_engine.exceptions import MLEngineError


def extract_frames(video: Path, destination: Path, every: float = 1.0, limit: int = 0) -> int:
    """Save a frame every ``every`` seconds and return the number saved.

    Args:
        video: Video file that OpenCV can open.
        destination: Output directory (created if needed).
        every: Seconds between extracted frames.
        limit: Maximum number of frames; ``0`` means no limit.

    Raises:
        MLEngineError: If the video cannot be opened or ``every`` is not positive.
    """
    if every <= 0:
        raise MLEngineError("The interval must be greater than zero.")
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise MLEngineError(f"Could not open video: {video}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(fps * every))
    destination.mkdir(parents=True, exist_ok=True)

    saved = 0
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % step == 0:
            encoded, buffer = cv2.imencode(".png", frame)
            if encoded:
                buffer.tofile(str(destination / f"frame_{saved:04d}.png"))
                saved += 1
            if limit and saved >= limit:
                break
        index += 1
    capture.release()
    return saved
