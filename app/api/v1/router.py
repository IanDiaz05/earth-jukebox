from fastapi import APIRouter

from app.api.v1.endpoints import playlists, tracks

api_v1_router = APIRouter()

api_v1_router.include_router(
    playlists.router,
    prefix="/playlists",
    tags=["Playlists"],
)
api_v1_router.include_router(
    tracks.router,
    prefix="/tracks",
    tags=["Tracks"],
)
