"""Tests for the WebSocket server."""

from unittest.mock import patch

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

    def test_client_message_world(self):
        """Test ClientMessage with world type."""
        msg = ClientMessage(type="world", player_id="test")
        assert msg.type == "world"

    def test_client_message_travel(self):
        """Test ClientMessage with travel type."""
        msg = ClientMessage(type="travel", player_id="test", content="Village")
        assert msg.type == "travel"
        assert msg.content == "Village"

    def test_client_message_exercise(self):
        """Test ClientMessage with exercise type."""
        msg = ClientMessage(type="exercise", player_id="test", content="check")
        assert msg.type == "exercise"
        assert msg.content == "check"

    def test_client_message_with_data(self):
        """Test ClientMessage with additional data."""
        msg = ClientMessage(type="collect", player_id="test", data={"segment_id": 1})
        assert msg.type == "collect"
        assert msg.data["segment_id"] == 1

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

    def test_server_message_with_data(self):
        """Test ServerMessage with data."""
        msg = ServerMessage(
            type="world_state",
            content="Welcome!",
            data={"name": "Test World", "locations": []},
        )
        assert msg.data["name"] == "Test World"

    def test_connection_message(self):
        """Test ConnectionMessage."""
        msg = ConnectionMessage(type="connected", player_id="test", message="Welcome!")
        assert msg.type == "connected"
        assert msg.player_id == "test"

    def test_connection_message_world_ready(self):
        """Test ConnectionMessage with world_ready flag."""
        msg = ConnectionMessage(
            type="connected", player_id="test", message="Welcome!", world_ready=True
        )
        assert msg.world_ready is True


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @patch("resolute.server.app.init_db")
    def test_health_check(self, mock_init_db):
        """Test that health check returns healthy status."""
        mock_init_db.return_value = None
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

    def test_get_agent_not_found(self, clean_manager):
        """Test getting an agent for a non-existent player."""
        agent = clean_manager.get_agent("nonexistent")
        assert agent is None

    def test_disconnect_nonexistent(self, clean_manager):
        """Test disconnecting a non-existent player doesn't raise error."""
        clean_manager.disconnect("nonexistent")  # Should not raise


class TestMessageHelpers:
    """Tests for message helper functions."""

    def test_error_message(self):
        """Test error_message helper."""
        from resolute.server.messages import error_message

        msg = error_message("Test error")
        assert msg.type == "error"
        assert msg.content == "Test error"
        assert msg.data["error"] == "Test error"

    def test_world_state_message(self):
        """Test world_state_message helper."""
        from resolute.server.messages import world_state_message

        world_data = {"name": "Test World", "locations": []}
        msg = world_state_message(world_data)
        assert msg.type == "world_state"
        assert "Test World" in msg.content
        assert msg.data == world_data

    def test_exercise_state_message_in_progress(self):
        """Test exercise_state_message helper for in-progress exercise."""
        from resolute.server.messages import exercise_state_message

        session_data = {
            "exercise_name": "Rhythm Practice",
            "remaining_seconds": 30,
            "is_complete": False,
        }
        msg = exercise_state_message(session_data)
        assert msg.type == "exercise_state"
        assert "30" in msg.content
        assert "Rhythm Practice" in msg.content

    def test_exercise_state_message_complete(self):
        """Test exercise_state_message helper for completed exercise."""
        from resolute.server.messages import exercise_state_message

        session_data = {
            "exercise_name": "Rhythm Practice",
            "remaining_seconds": 0,
            "is_complete": True,
        }
        msg = exercise_state_message(session_data)
        assert msg.type == "exercise_state"
        assert "complete" in msg.content.lower()

    def test_inventory_update_message(self):
        """Test inventory_update_message helper."""
        from resolute.server.messages import inventory_update_message

        inventory_data = {
            "collected_segments": [{"name": "Verse 1"}],
            "total_segments": 4,
        }
        msg = inventory_update_message(inventory_data)
        assert msg.type == "inventory_update"
        assert "1/4" in msg.content
