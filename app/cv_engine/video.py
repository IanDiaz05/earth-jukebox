"""Extract PNG frames from a video (e.g. an animated EIC visualization).

Video frames are compressed: use the tolerant profile (``lossy(profile)``)
when measuring them.
"""
from __future__ import annotations

from pathlib import Path

import cv2

from app.ml_engine.exceptions import MLEngineError


def extract_frames(video: Path, destino: Path, cada: float = 1.0, maximo: int = 0) -> int:
    """Save a frame every ``cada`` seconds and return the number saved.

    Args:
        video: Video file that OpenCV can open.
        destino: Output directory (created if needed).
        cada: Seconds between extracted frames.
        maximo: Maximum number of frames; ``0`` means no limit.

    Raises:
        MLEngineError: If the video cannot be opened or ``cada`` is not positive.
    """
    if cada <= 0:
        raise MLEngineError("El intervalo debe ser mayor que cero.")
    captura = cv2.VideoCapture(str(video))
    if not captura.isOpened():
        raise MLEngineError(f"No se pudo abrir el vídeo: {video}")
    fps = captura.get(cv2.CAP_PROP_FPS) or 25.0
    paso = max(1, round(fps * cada))
    destino.mkdir(parents=True, exist_ok=True)

    guardados = 0
    indice = 0
    while True:
        ok, frame = captura.read()
        if not ok:
            break
        if indice % paso == 0:
            exito, buffer = cv2.imencode(".png", frame)
            if exito:
                buffer.tofile(str(destino / f"frame_{guardados:04d}.png"))
                guardados += 1
            if maximo and guardados >= maximo:
                break
        indice += 1
    captura.release()
    return guardados
