"""Pydantic schemas for tracks."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrackBase(BaseModel):
    """Common track fields."""

    slug: str = Field(max_length=100)
    title: str = Field(max_length=150)
    description: str | None = None
    sequence_order: int = 0
    event_date: datetime | None = None
    source_metadata: dict[str, Any]
    engine_metadata: dict[str, Any]
    frames: list[dict[str, Any]]


class TrackCreate(TrackBase):
    """Creation payload for a track within a playlist."""

    playlist_id: int


class TrackIngestData(BaseModel):
    """Editorial data for a track produced by the ML pipeline.

    The pipeline output (`dataset_info`, `frames`) and audio configuration
    are added by the ingestion layer and are not passed here.
    """

    title: str = Field(max_length=150)
    slug: str = Field(max_length=100)
    description: str | None = None
    sequence_order: int = 0
    event_date: datetime | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class TrackUpdate(BaseModel):
    """Partial track update payload."""

    title: str | None = Field(default=None, max_length=150)
    description: str | None = None
    sequence_order: int | None = None
    event_date: datetime | None = None
    source_metadata: dict[str, Any] | None = None
    engine_metadata: dict[str, Any] | None = None
    frames: list[dict[str, Any]] | None = None


class TrackSummaryResponse(BaseModel):
    """Lightweight representation of a track for playlist listings.

    Omits ``engine_metadata`` and ``frames``; those are included only in the
    detail response.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    playlist_id: int
    slug: str
    title: str
    description: str | None
    sequence_order: int
    event_date: datetime | None
    source_metadata: dict[str, Any]
    created_at: datetime


class TrackDetailResponse(TrackSummaryResponse):
    """Full representation of a track for playback.

    Includes ``engine_metadata`` (the ML engine dataset) and ``frames``.
    """

    engine_metadata: dict[str, Any]
    frames: list[dict]
