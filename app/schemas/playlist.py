"""Pydantic schemas for playlists."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.track import TrackSummaryResponse


class PlaylistBase(BaseModel):
    """Common playlist fields."""

    slug: str = Field(max_length=100)
    title: str = Field(max_length=150)
    description: str | None = None
    category: str = Field(max_length=50)
    cover_url: str | None = Field(default=None, max_length=255)
    is_featured: bool = False


class PlaylistCreate(PlaylistBase):
    """Playlist creation payload."""


class PlaylistUpdate(BaseModel):
    """Partial playlist update payload."""

    title: str | None = Field(default=None, max_length=150)
    description: str | None = None
    category: str | None = Field(default=None, max_length=50)
    cover_url: str | None = Field(default=None, max_length=255)
    is_featured: bool | None = None


class PlaylistSummaryResponse(PlaylistBase):
    """Summary representation of a playlist, without tracks."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PlaylistDetailResponse(PlaylistSummaryResponse):
    """Playlist with lightweight tracks (without engine_metadata or frames)."""

    tracks: list[TrackSummaryResponse] = Field(default_factory=list)
