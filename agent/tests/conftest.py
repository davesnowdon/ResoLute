"""Pytest configuration and fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from resolute.db.models import Base
from resolute.game.exercise_timer import ExerciseTimer


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def test_session_factory(test_engine):
    """Create a session factory bound to the test engine."""
    return sessionmaker(test_engine, class_=Session, expire_on_commit=False)


@pytest.fixture
def test_session(test_session_factory):
    """Provide a test database session that auto-commits."""
    session = test_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def seeded_test_session(test_session):
    """Provide a test session with seed data (exercises and songs)."""
    from resolute.db.seed_data import seed_exercises_and_songs

    seed_exercises_and_songs(test_session)
    return test_session


@pytest.fixture
def test_timer():
    """Provide a fresh ExerciseTimer for testing."""
    return ExerciseTimer()


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("MODEL", "google_genai/gemini-2.0-flash")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key")
    monkeypatch.setenv("OPIK_API_KEY", "")
    monkeypatch.setenv("OPIK_PROJECT_NAME", "resolute-test")
    monkeypatch.setenv("HOST", "localhost")
    monkeypatch.setenv("PORT", "8000")


@pytest.fixture
def player_id():
    """Provide a test player ID."""
    return "test-player"


@pytest.fixture
def sample_chat_message(player_id):
    """Provide a sample chat message."""
    return {
        "type": "chat",
        "player_id": player_id,
        "content": "Hello, mentor!",
    }


@pytest.fixture
def sample_status_message(player_id):
    """Provide a sample status message."""
    return {
        "type": "status",
        "player_id": player_id,
        "content": "",
    }
