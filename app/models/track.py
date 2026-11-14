"""ORM model for tracks with engine measurements."""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.playlist import Playlist


class Track(Base):
    """Track in a playlist, with its metadata and precomputed frames.

    ``source_metadata`` describes the source of the frames and where their
    public images are located, ``engine_metadata`` describes the dataset
    information provided by the engine, and ``frames`` contains measurements
    for each frame.
    """

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    event_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    engine_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    frames: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    playlist: Mapped["Playlist"] = relationship(back_populates="tracks")
