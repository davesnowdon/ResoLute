"""Database session management for SQLAlchemy."""

from sqlalchemy import Engine

from resolute.db.models import Base


def create_tables(engine: Engine) -> None:
    """Create all database tables."""
    Base.metadata.create_all(engine)


def drop_tables(engine: Engine) -> None:
    """Drop all database tables (use with caution!)."""
    Base.metadata.drop_all(engine)
