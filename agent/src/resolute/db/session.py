"""Database session management for SQLAlchemy.

Uses synchronous sessions for all operations to avoid greenlet/async issues.
Async engine is only used for table creation.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from resolute.config import get_settings
from resolute.db.models import Base

_async_engine: AsyncEngine | None = None
_sync_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _get_async_engine() -> AsyncEngine:
    """Get or create the async database engine (for table creation only)."""
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
        )
    return _async_engine


def get_engine() -> Engine:
    """Get or create the sync database engine."""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        # Convert async URL to sync (sqlite+aiosqlite -> sqlite)
        sync_url = settings.database_url.replace("+aiosqlite", "")
        _sync_engine = create_engine(
            sync_url,
            echo=False,
            future=True,
        )
    return _sync_engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            engine,
            class_=Session,
            expire_on_commit=False,
        )
    return _session_factory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session as a context manager."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def create_tables() -> None:
    """Create all database tables."""
    engine = _get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all database tables (use with caution!)."""
    engine = _get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def init_db() -> None:
    """Initialize the database with tables and seed data."""
    from resolute.db.seed_data import seed_exercises_and_songs

    await create_tables()
    with get_session() as session:
        seed_exercises_and_songs(session)
