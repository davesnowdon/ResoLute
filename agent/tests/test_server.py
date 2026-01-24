"""Tests for the WebSocket server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from resolute.server.app import app, manager
from resolute.server.messages import ClientMessage, ConnectionMessage, ServerMessage


class TestMessages:
    """Tests for message schemas."""

    def test_client_message_chat(self):
        """Test ClientMessage with chat type."""
        msg = ClientMessage(type="chat", player_id="test", content="Hello")
        assert msg.type == "chat"
        assert msg.player_id == "test"
        assert msg.content == "Hello"

    def test_client_message_status(self):
        """Test ClientMessage with status type."""
        msg = ClientMessage(type="status", player_id="test")
        assert msg.type == "status"
        assert msg.content == ""

    def test_server_message_response(self):
        """Test ServerMessage with response type."""
        msg = ServerMessage(type="response", content="Hello adventurer!")
        assert msg.type == "response"
        assert msg.content == "Hello adventurer!"
        assert msg.metadata == {}

    def test_server_message_with_metadata(self):
        """Test ServerMessage with metadata."""
        msg = ServerMessage(type="response", content="Quest complete!", metadata={"xp": 100})
        assert msg.metadata == {"xp": 100}

    def test_connection_message(self):
        """Test ConnectionMessage."""
        msg = ConnectionMessage(type="connected", player_id="test", message="Welcome!")
        assert msg.type == "connected"
        assert msg.player_id == "test"


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self):
        """Test that health check returns healthy status."""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "resolute"


class TestConnectionManager:
    """Tests for the ConnectionManager."""

    @pytest.fixture
    def clean_manager(self):
        """Ensure manager is clean before each test."""
        manager.active_connections.clear()
        manager.agents.clear()
        yield manager
        manager.active_connections.clear()
        manager.agents.clear()

    @pytest.mark.asyncio
    @patch("resolute.server.app.MentorAgent")
    async def test_connect(self, mock_agent_class, clean_manager):
        """Test connecting a player."""
        mock_websocket = AsyncMock()
        mock_agent_class.return_value = MagicMock()

        await clean_manager.connect(mock_websocket, "test-player")

        assert "test-player" in clean_manager.active_connections
        assert "test-player" in clean_manager.agents
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    @patch("resolute.server.app.MentorAgent")
    async def test_disconnect(self, mock_agent_class, clean_manager):
        """Test disconnecting a player."""
        mock_websocket = AsyncMock()
        mock_agent_class.return_value = MagicMock()

        await clean_manager.connect(mock_websocket, "test-player")
        clean_manager.disconnect("test-player")

        assert "test-player" not in clean_manager.active_connections
        assert "test-player" not in clean_manager.agents

    @pytest.mark.asyncio
    @patch("resolute.server.app.MentorAgent")
    async def test_get_agent(self, mock_agent_class, clean_manager):
        """Test getting an agent for a player."""
        mock_websocket = AsyncMock()
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        await clean_manager.connect(mock_websocket, "test-player")
        agent = clean_manager.get_agent("test-player")

        assert agent is mock_agent

    def test_get_agent_not_found(self, clean_manager):
        """Test getting an agent for a non-existent player."""
        agent = clean_manager.get_agent("nonexistent")
        assert agent is None
