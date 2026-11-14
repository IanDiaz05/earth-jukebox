"""Public track endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.schemas.track import TrackDetailResponse
from app.services.track_service import get_track_by_slug

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/{slug}", response_model=TrackDetailResponse)
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def get_track_endpoint(
    request: Request,
    slug: str,
    db: DbSession,
) -> TrackDetailResponse:
    """Return a track by its slug, with the data needed to synthesize audio.

    Includes ``source_metadata``, ``engine_metadata``, and ``frames`` so the
    frontend can synthesize audio on the client.

    Args:
        request: Incoming request, required by the rate limiter.
        slug: Unique track slug.
        db: Database session injected by FastAPI.

    Returns:
        The complete track with measurements for each frame.

    Raises:
        HTTPException: 404 if the track does not exist.
    """
    track = await run_in_threadpool(get_track_by_slug, db, slug)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return TrackDetailResponse.model_validate(track)
