"""SpotiEarth API entry point."""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.api.v1.router import api_v1_router
from app.core.config import BASE_DIR, settings
from app.core.database import SessionLocal, init_db
from app.core.rate_limit import limiter
from app.ml_engine import PROFILES, MLEngineError, load_lut

logger = logging.getLogger(__name__)


def _usable_profiles() -> list[str]:
    """Return engine profiles whose color table can be loaded."""
    usable: list[str] = []
    for profile_id, profile in PROFILES.items():
        if profile.legend is not None:
            # The legend lives alongside the frames and is validated during processing.
            usable.append(profile_id)
            continue
        try:
            load_lut(BASE_DIR, profile)
        except MLEngineError as exc:
            logger.warning("Engine profile %s unavailable: %s", profile_id, exc)
        else:
            usable.append(profile_id)
    return usable


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Check the engine profiles and prepare the schema before serving requests.

    The measurement engine needs no model warm-up: it only reads each
    profile's color table, so a broken or missing table is detected here.

    Args:
        app: Application instance holding the shared engine state.

    Yields:
        Control to the application while it serves requests.
    """
    app.state.ml_profiles = await run_in_threadpool(_usable_profiles)

    try:
        await run_in_threadpool(init_db)
    except SQLAlchemyError as exc:
        logger.error("Database schema initialization failed: %s", exc)

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="SpotiEarth Backend — motor de análisis de imágenes satelitales.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Rate limit — store the limiter in the application state for slowapi to use.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Permissive CORS in development; restrict in production via settings.ALLOWED_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers.
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root welcome endpoint."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "ok",
        "docs": "/docs",
    }


def _check_database() -> None:
    """Run a `SELECT 1` query against PostgreSQL.

    Raises:
        SQLAlchemyError: If the connection or query fails.
    """
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))


def _ml_engine_state(request: Request) -> str:
    """Report the engine status: ready if at least one profile is usable."""
    if not getattr(request.app.state, "ml_profiles", None):
        return "unavailable"
    return "ready"


@app.get("/health", tags=["Health"])
async def health_check(request: Request) -> JSONResponse:
    """Health check used by orchestrators and the devcontainer.

    Checks PostgreSQL connectivity with a `SELECT 1` query and reports the
    engine status checked in `app.state` during startup.
    """
    try:
        await run_in_threadpool(_check_database)
    except SQLAlchemyError as exc:
        logger.error("Database health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "ml_engine": _ml_engine_state(request),
            },
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "database": "connected",
            "ml_engine": _ml_engine_state(request),
        },
    )