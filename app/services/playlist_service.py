"""Playlist CRUD service using SQLAlchemy.

The functions are synchronous and blocking: FastAPI runs them in the
thread pool when used from `def` routes or synchronous dependencies.
"""
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.playlist import Playlist
from app.schemas.playlist import PlaylistCreate, PlaylistUpdate


def create_playlist(db: Session, data: PlaylistCreate) -> Playlist:
    """Create and persist a new playlist.

    Args:
        db: Active SQLAlchemy session.
        data: Creation payload validated by Pydantic.

    Returns:
        The persisted playlist instance.

    Raises:
        SQLAlchemyError: If the insert fails (e.g., duplicate slug).
    """
    playlist = Playlist(**data.model_dump())
    try:
        db.add(playlist)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(playlist)
    return playlist


def get_playlist_by_id(db: Session, playlist_id: int) -> Playlist | None:
    """Return a playlist by its ID, or None if it does not exist."""
    return db.get(Playlist, playlist_id)


def get_playlist_by_slug(db: Session, slug: str) -> Playlist | None:
    """Return a playlist by its unique slug, with its tracks eagerly loaded.

    Args:
        db: Active SQLAlchemy session.
        slug: Unique playlist slug.

    Returns:
        The playlist with ``tracks`` eagerly loaded, or None if it does not exist.
    """
    stmt = (
        select(Playlist)
        .where(Playlist.slug == slug)
        .options(selectinload(Playlist.tracks))
    )
    return db.execute(stmt).scalar_one_or_none()


def list_playlists(
    db: Session,
    category: str | None = None,
    is_featured: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Playlist]:
    """List playlists with optional category and featured filters.

    Args:
        db: Active SQLAlchemy session.
        category: Exact category to filter by; None applies no filter.
        is_featured: Featured filter; None applies no filter.
        limit: Maximum number of results.
        offset: Offset for pagination.

    Returns:
        Playlists ordered chronologically, with their tracks eagerly loaded.
    """
    stmt = (
        select(Playlist)
        .options(selectinload(Playlist.tracks))
        .order_by(Playlist.created_at, Playlist.id)
    )
    if category is not None:
        stmt = stmt.where(Playlist.category == category)
    if is_featured is not None:
        stmt = stmt.where(Playlist.is_featured == is_featured)
    stmt = stmt.limit(limit).offset(offset)
    playlists = db.execute(stmt).scalars().all()
    return list(playlists)


def count_playlists(db: Session) -> int:
    """Count the persisted playlists."""
    return int(db.execute(select(func.count(Playlist.id))).scalar_one())


def update_playlist(db: Session, playlist: Playlist, data: PlaylistUpdate) -> Playlist:
    """Update the editorial fields of an existing playlist.

    Args:
        db: Active SQLAlchemy session.
        playlist: Persisted playlist to update.
        data: Partial payload validated by Pydantic. Fields set to `None`
            are left unchanged.

    Returns:
        The same playlist with the updated data.

    Raises:
        SQLAlchemyError: If the update fails; a rollback is performed first.
    """
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(playlist, field, value)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(playlist)
    return playlist


def delete_playlist(db: Session, playlist: Playlist) -> None:
    """Delete a playlist and its tracks through cascading.

    Args:
        db: Active SQLAlchemy session.
        playlist: Persisted playlist to delete.

    Raises:
        SQLAlchemyError: If the deletion fails; a rollback is performed first.
    """
    try:
        db.delete(playlist)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
