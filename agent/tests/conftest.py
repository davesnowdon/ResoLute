"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
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
