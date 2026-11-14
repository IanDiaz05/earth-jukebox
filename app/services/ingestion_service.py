"""Ingest a measurement engine result into the `tracks` table.

Store the engine's `dataset_info` in `engine_metadata` and the frames as
native PostgreSQL JSONB. The audio hints for the frontend are already
included in `dataset_info` (`hints`), as defined by the visualization profile.
"""
from typing import Any

from sqlalchemy.orm import Session

from app.models.track import Track
from app.schemas.track import TrackCreate, TrackIngestData
from app.services.track_service import create_track, get_track_by_slug, replace_track


class TrackAlreadyExistsError(Exception):
    """A track with that slug already exists and replacement was not requested."""


def ingest_timelapse_result(
    db: Session,
    playlist_id: int,
    track_data: TrackIngestData | dict[str, Any],
    pipeline_result: dict[str, Any],
    replace: bool = False,
) -> Track:
    """Persist the result of `measure_timelapse` as a track.

    Args:
        db: Active SQLAlchemy session.
        playlist_id: ID of the destination playlist.
        track_data: Pydantic schema or dictionary with `title`, `slug`,
            `description`, `sequence_order`, `event_date`, and `source_metadata`.
        pipeline_result: Engine JSON contract with `dataset_info` and `frames`.
        replace: If a track with that slug already exists, overwrite its
            content while preserving its ID and slug. Without this option, an
            existing track is left unchanged.

    Returns:
        The persisted track with its `engine_metadata` and `frames` in JSONB.

    Raises:
        pydantic.ValidationError: If `track_data` is invalid.
        TrackAlreadyExistsError: If the slug exists and `replace` is false.
        SQLAlchemyError: If the write fails; a rollback is performed first.
    """
    payload = (
        track_data
        if isinstance(track_data, TrackIngestData)
        else TrackIngestData.model_validate(track_data)
    )

    track_payload = TrackCreate(
        playlist_id=playlist_id,
        title=payload.title,
        slug=payload.slug,
        description=payload.description,
        sequence_order=payload.sequence_order,
        event_date=payload.event_date,
        source_metadata=payload.source_metadata,
        engine_metadata=dict(pipeline_result.get("dataset_info", {})),
        frames=pipeline_result.get("frames", []),
    )

    existing = get_track_by_slug(db, payload.slug)
    if existing is None:
        return create_track(db, track_payload)
    if not replace:
        raise TrackAlreadyExistsError(
            f"Ya existe una pista con el slug '{payload.slug}'."
        )
    return replace_track(db, existing, track_payload)
