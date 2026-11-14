"""playlists public endpoints"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.schemas.playlist import PlaylistDetailResponse, PlaylistSummaryResponse
from app.services.playlist_service import get_playlist_by_slug, list_playlists

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[PlaylistSummaryResponse])
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def list_playlists_endpoint(
    request: Request,
    db: DbSession,
    category: str | None = None,
    is_featured: bool | None = None,
) -> list[PlaylistSummaryResponse]:
    """List playlists with optional category and featured filters.

    Args:
        request: Incoming request, required by the rate limiter.
        db: Database session injected by FastAPI.
        category: Exact category to filter by; None returns all playlists.
        is_featured: Featured filter; None applies no filter.

    Returns:
        Playlists ordered chronologically, without tracks.
    """
    playlists = await run_in_threadpool(
        list_playlists,
        db,
        category,
        is_featured,
    )
    return [
        PlaylistSummaryResponse.model_validate(playlist)
        for playlist in playlists
    ]


@router.get("/{slug}", response_model=PlaylistDetailResponse)
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def get_playlist_endpoint(
    request: Request,
    slug: str,
    db: DbSession,
) -> PlaylistDetailResponse:
    """Return a playlist by its slug, with a summary of its tracks.

    Args:
        request: Incoming request, required by the rate limiter.
        slug: Unique playlist slug.
        db: Database session injected by FastAPI.

    Returns:
        The playlist with its tracks ordered by ``sequence_order``.

    Raises:
        HTTPException: 404 if the playlist does not exist.
    """
    playlist = await run_in_threadpool(get_playlist_by_slug, db, slug)
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return PlaylistDetailResponse.model_validate(playlist)
