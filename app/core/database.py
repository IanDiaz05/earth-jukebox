"""Configure the PostgreSQL connection with SQLAlchemy.

The DSN is taken from `app.core.config.settings`, which loads it from
environment variables / `.env`. This module contains no embedded credentials.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _normalize_database_url(url: str) -> str:
    """Force the psycopg2 driver for generic PostgreSQL DSNs.

    SQLAlchemy 2.1+ resolves `postgresql://` to psycopg (v3), but the project
    declares `psycopg2-binary`. DSNs that already specify a driver are preserved.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


engine = create_engine(
    _normalize_database_url(settings.DATABASE_URL),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Declarative base class for all SpotiEarth ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a session and closes it when finished."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all declared tables if they do not already exist.

    Import the models inside the function to register them in
    ``Base.metadata`` without introducing circular imports.
    """
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
