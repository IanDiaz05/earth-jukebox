"""Track CRUD service using SQLAlchemy.

The functions are synchronous and blocking: FastAPI runs them in the
thread pool when used from `def` routes or synchronous dependencies.
"""
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.track import Track
from app.schemas.track import TrackCreate


def create_track(db: Session, data: TrackCreate) -> Track:
    """Create and persist a new track in a playlist.

    Args:
        db: Active SQLAlchemy session.
        data: Creation payload validated by Pydantic.

    Returns:
        The persisted track instance.

    Raises:
        SQLAlchemyError: If the insert fails (e.g., duplicate slug).
    """
    track = Track(
        playlist_id=data.playlist_id,
        slug=data.slug,
        title=data.title,
        description=data.description,
        sequence_order=data.sequence_order,
        event_date=data.event_date,
        source_metadata=data.source_metadata,
        engine_metadata=data.engine_metadata,
        frames=data.frames,
    )
    try:
        db.add(track)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(track)
    return track


def replace_track(db: Session, track: Track, data: TrackCreate) -> Track:
    """Replace an existing track's content while preserving its ID and slug.

    Used when remeasuring a timelapse: the URL consumed by the frontend
    remains unchanged; only the data changes.

    Args:
        db: Active SQLAlchemy session.
        track: Persisted track to overwrite.
        data: New content validated by Pydantic. Its `slug` is ignored.

    Returns:
        The same track with the updated data.

    Raises:
        SQLAlchemyError: If the update fails; a rollback is performed first.
    """
    track.playlist_id = data.playlist_id
    track.title = data.title
    track.description = data.description
    track.sequence_order = data.sequence_order
    track.event_date = data.event_date
    track.source_metadata = data.source_metadata
    track.engine_metadata = data.engine_metadata
    track.frames = data.frames
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(track)
    return track


def get_track_by_id(db: Session, track_id: int) -> Track | None:
    """Return a track by its ID, or None if it does not exist."""
    return db.get(Track, track_id)


def get_track_by_slug(db: Session, slug: str) -> Track | None:
    """Return a track by its unique slug, or None if it does not exist."""
    stmt = select(Track).where(Track.slug == slug)
    return db.execute(stmt).scalar_one_or_none()


def list_tracks_by_playlist(db: Session, playlist_id: int) -> list[Track]:
    """List a playlist's tracks ordered by `sequence_order`."""
    stmt = (
        select(Track)
        .where(Track.playlist_id == playlist_id)
        .order_by(Track.sequence_order, Track.id)
    )
    tracks = db.execute(stmt).scalars().all()
    return list(tracks)
