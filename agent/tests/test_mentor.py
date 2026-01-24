"""Tests for the MentorAgent."""

from unittest.mock import MagicMock, patch

from resolute.agent.prompts import MENTOR_SYSTEM_PROMPT
from resolute.agent.tools import get_tool_definitions


class TestPrompts:
    """Tests for agent prompts."""

    def test_mentor_system_prompt_contains_placeholder(self):
        """Test that the mentor prompt has the player_name placeholder."""
        assert "{player_name}" in MENTOR_SYSTEM_PROMPT

    def test_mentor_system_prompt_format(self):
        """Test that the mentor prompt can be formatted."""
        formatted = MENTOR_SYSTEM_PROMPT.format(player_name="TestPlayer")
        assert "TestPlayer" in formatted
        assert "{player_name}" not in formatted


class TestTools:
    """Tests for agent tools."""

    def test_get_tool_definitions_returns_list(self):
        """Test that get_tool_definitions returns a list of tool definitions."""
        definitions = get_tool_definitions()
        assert isinstance(definitions, list)
        assert len(definitions) == 10  # Updated count for new tools

    def test_tool_definitions_have_names(self):
        """Test that all tool definitions have names."""
        definitions = get_tool_definitions()
        expected_names = [
            "get_player_stats",
            "get_current_location",
            "start_travel",
            "check_exercise",
            "complete_exercise",
            "collect_song_segment",
            "get_inventory",
            "perform_at_tavern",
            "check_final_quest_ready",
            "attempt_final_quest",
        ]
        tool_names = [d["name"] for d in definitions]
        for name in expected_names:
            assert name in tool_names, f"Missing tool: {name}"


class TestMentorAgent:
    """Tests for MentorAgent initialization."""

    @patch("resolute.agent.mentor.ChatGoogleGenerativeAI")
    @patch("resolute.agent.mentor.create_react_agent")
    def test_mentor_agent_initialization(self, mock_create_agent, mock_llm):
        """Test that MentorAgent initializes correctly."""
        from resolute.agent.mentor import MentorAgent

        mock_create_agent.return_value = MagicMock()

        agent = MentorAgent(player_id="test-123", player_name="TestPlayer")

        assert agent.player_id == "test-123"
        assert agent.player_name == "TestPlayer"
        assert "TestPlayer" in agent.system_prompt
        mock_llm.assert_called_once()
        mock_create_agent.assert_called_once()

    @patch("resolute.agent.mentor.ChatGoogleGenerativeAI")
    @patch("resolute.agent.mentor.create_react_agent")
    def test_mentor_agent_default_name(self, mock_create_agent, mock_llm):
        """Test that MentorAgent uses default name when none provided."""
        from resolute.agent.mentor import MentorAgent

        mock_create_agent.return_value = MagicMock()

        agent = MentorAgent(player_id="test-456")

        assert agent.player_name == "Adventurer"
        assert "Adventurer" in agent.system_prompt

    @patch("resolute.agent.mentor.ChatGoogleGenerativeAI")
    @patch("resolute.agent.mentor.create_react_agent")
    def test_mentor_agent_without_state_manager(self, mock_create_agent, mock_llm):
        """Test that MentorAgent works without state_manager (no tools)."""
        from resolute.agent.mentor import MentorAgent

        mock_create_agent.return_value = MagicMock()

        agent = MentorAgent(player_id="test-789")

        assert agent.tools == []
        mock_create_agent.assert_called_once()
