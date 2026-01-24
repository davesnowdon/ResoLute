"""Tests for the MentorAgent."""

from unittest.mock import MagicMock, patch

from resolute.agent.prompts import MENTOR_SYSTEM_PROMPT
from resolute.agent.tools import (
    award_achievement,
    get_mentor_tools,
    get_player_stats,
    suggest_practice_exercise,
)


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

    def test_get_player_stats(self):
        """Test get_player_stats tool."""
        result = get_player_stats.invoke({"player_id": "test-player"})
        assert result["player_id"] == "test-player"
        assert "level" in result
        assert "xp" in result
        assert "skills" in result

    def test_suggest_practice_exercise_rhythm(self):
        """Test suggest_practice_exercise for rhythm."""
        result = suggest_practice_exercise.invoke({"skill": "rhythm", "difficulty": 1})
        assert result["skill"] == "rhythm"
        assert result["difficulty"] == 1
        assert "exercise" in result
        assert result["xp_reward"] == 10

    def test_suggest_practice_exercise_clamps_difficulty(self):
        """Test that difficulty is clamped to valid range."""
        result = suggest_practice_exercise.invoke({"skill": "melody", "difficulty": 10})
        assert result["difficulty"] == 5  # Clamped to max

        result = suggest_practice_exercise.invoke({"skill": "melody", "difficulty": 0})
        assert result["difficulty"] == 1  # Clamped to min

    def test_award_achievement(self):
        """Test award_achievement tool."""
        result = award_achievement.invoke(
            {"player_id": "test-player", "achievement": "First Steps"}
        )
        assert result["player_id"] == "test-player"
        assert result["achievement"] == "First Steps"
        assert result["awarded"] is True

    def test_get_mentor_tools_returns_list(self):
        """Test that get_mentor_tools returns a list of tools."""
        tools = get_mentor_tools()
        assert isinstance(tools, list)
        assert len(tools) == 3


class TestMentorAgent:
    """Tests for MentorAgent initialization."""

    @patch("resolute.agent.mentor.ChatGoogleGenerativeAI")
    @patch("resolute.agent.mentor.create_react_agent")
    def test_mentor_agent_initialization(self, mock_create_agent, mock_llm):
        """Test that MentorAgent initializes correctly."""
        from resolute.agent.mentor import MentorAgent

        mock_create_agent.return_value = MagicMock()

        agent = MentorAgent(player_name="TestPlayer")

        assert agent.player_name == "TestPlayer"
        assert "TestPlayer" in agent.system_prompt
        mock_llm.assert_called_once()
        mock_create_agent.assert_called_once()
