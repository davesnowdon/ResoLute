"""Agent tools for the MentorAgent with database integration."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from resolute.game.exercise_timer import ExerciseTimer
from resolute.game.services import ExerciseService, PlayerService, QuestService


# Input schemas for tools that need parameters
class TravelInput(BaseModel):
    """Input for the start_travel tool."""

    destination_name: str = Field(description="The name of the destination to travel to")


class CollectSegmentInput(BaseModel):
    """Input for the collect_song_segment tool."""

    segment_id: int = Field(description="The ID of the segment to collect")


@contextmanager
def _get_session(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Get a database session as a context manager."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tools_for_player(
    player_id: str,
    session_factory: sessionmaker[Session],
    timer: ExerciseTimer,
) -> list:
    """Create tools bound to a specific player.

    Each tool uses synchronous database operations to avoid greenlet/async
    boundary issues when invoked by LangGraph's ReAct agent.

    Args:
        player_id: The player's ID.
        session_factory: Factory for creating database sessions.
        timer: The exercise timer instance.

    Returns:
        List of StructuredTool instances.
    """

    def get_player_stats() -> dict[str, Any]:
        """Get the current stats and progress for the player.
        Returns player level, XP, gold, reputation, and skill levels.
        """
        with _get_session(session_factory) as session:
            service = PlayerService(session)
            result = service.get_stats(player_id)
            return result.to_dict()

    def get_current_location() -> dict[str, Any]:
        """Get the player's current location and available actions.
        Shows where the player is, available travel destinations,
        and any collectible song segments.
        """
        with _get_session(session_factory) as session:
            service = PlayerService(session)
            result = service.get_current_location(player_id)
            return result.to_dict()

    def start_travel(destination_name: str) -> dict[str, Any]:
        """Start traveling to a new location.
        This begins a timed practice exercise that must be completed
        before arriving at the destination.
        """
        with _get_session(session_factory) as session:
            player_service = PlayerService(session)
            exercise_service = ExerciseService(session, timer)

            # Get current location to find destination
            loc_result = player_service.get_current_location(player_id)
            if loc_result.is_err:
                return loc_result.to_dict()

            location_info = loc_result.unwrap()
            destinations = location_info.get("available_destinations", [])

            # Find matching destination
            destination = None
            for dest in destinations:
                if dest["name"].lower() == destination_name.lower():
                    destination = dest
                    break

            if destination is None:
                available = [d["name"] for d in destinations]
                return {
                    "error": f"Destination '{destination_name}' not found or not unlocked",
                    "available_destinations": available,
                }

            result = exercise_service.start_travel(player_id, destination["id"])
            return result.to_dict()

    def check_exercise() -> dict[str, Any]:
        """Check the status of the current exercise.
        Shows time remaining and whether the exercise can be completed.
        """
        with _get_session(session_factory) as session:
            service = ExerciseService(session, timer)
            result = service.check_exercise(player_id)
            if result.is_err:
                return {"status": "no_active_exercise", "message": result.error}
            return result.to_dict()

    def complete_exercise() -> dict[str, Any]:
        """Complete the current exercise and receive rewards.
        Can only be called after the exercise timer has finished.
        Awards XP, gold, and skill bonuses.
        """
        with _get_session(session_factory) as session:
            service = ExerciseService(session, timer)
            result = service.complete_exercise(player_id)
            return result.to_dict()

    def collect_song_segment(segment_id: int) -> dict[str, Any]:
        """Collect a song segment from the current location.
        Song segments are pieces of the legendary Hero's Ballad
        that must be collected to complete the final quest.
        """
        with _get_session(session_factory) as session:
            service = QuestService(session)
            result = service.collect_segment(player_id, segment_id)
            return result.to_dict()

    def get_inventory() -> dict[str, Any]:
        """Get the player's inventory of collected song segments.
        Shows all segments collected and whether the player is
        ready for the final quest.
        """
        with _get_session(session_factory) as session:
            service = QuestService(session)
            result = service.get_inventory(player_id)
            return result.to_dict()

    def perform_at_tavern() -> dict[str, Any]:
        """Perform at the tavern to earn gold and reputation.
        Must be at a tavern location. Performance rewards scale
        with the number of song segments collected.
        """
        with _get_session(session_factory) as session:
            service = QuestService(session)
            result = service.perform_at_tavern(player_id)
            return result.to_dict()

    def check_final_quest_ready() -> dict[str, Any]:
        """Check if the player is ready for the final quest.
        The final quest requires all song segments to be collected.
        Shows progress toward the goal.
        """
        with _get_session(session_factory) as session:
            service = QuestService(session)
            result = service.check_final_quest_ready(player_id)
            return result.to_dict()

    def attempt_final_quest() -> dict[str, Any]:
        """Attempt the final quest to rescue the captive.
        Performs the complete Hero's Ballad to charm the monster.
        Requires all song segments to be collected.
        """
        with _get_session(session_factory) as session:
            service = QuestService(session)
            result = service.complete_final_quest(player_id)
            return result.to_dict()

    # Create StructuredTool instances (using func for sync tools)
    tools = [
        StructuredTool.from_function(
            func=get_player_stats,
            name="get_player_stats",
            description="Get the current stats and progress for the player. Returns player level, XP, gold, reputation, and skill levels.",
        ),
        StructuredTool.from_function(
            func=get_current_location,
            name="get_current_location",
            description="Get the player's current location and available actions. Shows where the player is, available travel destinations, and any collectible song segments.",
        ),
        StructuredTool.from_function(
            func=start_travel,
            name="start_travel",
            description="Start traveling to a new location. This begins a timed practice exercise that must be completed before arriving at the destination.",
            args_schema=TravelInput,
        ),
        StructuredTool.from_function(
            func=check_exercise,
            name="check_exercise",
            description="Check the status of the current exercise. Shows time remaining and whether the exercise can be completed.",
        ),
        StructuredTool.from_function(
            func=complete_exercise,
            name="complete_exercise",
            description="Complete the current exercise and receive rewards. Can only be called after the exercise timer has finished. Awards XP, gold, and skill bonuses.",
        ),
        StructuredTool.from_function(
            func=collect_song_segment,
            name="collect_song_segment",
            description="Collect a song segment from the current location. Song segments are pieces of the legendary Hero's Ballad that must be collected to complete the final quest.",
            args_schema=CollectSegmentInput,
        ),
        StructuredTool.from_function(
            func=get_inventory,
            name="get_inventory",
            description="Get the player's inventory of collected song segments. Shows all segments collected and whether the player is ready for the final quest.",
        ),
        StructuredTool.from_function(
            func=perform_at_tavern,
            name="perform_at_tavern",
            description="Perform at the tavern to earn gold and reputation. Must be at a tavern location. Performance rewards scale with the number of song segments collected.",
        ),
        StructuredTool.from_function(
            func=check_final_quest_ready,
            name="check_final_quest_ready",
            description="Check if the player is ready for the final quest. The final quest requires all song segments to be collected. Shows progress toward the goal.",
        ),
        StructuredTool.from_function(
            func=attempt_final_quest,
            name="attempt_final_quest",
            description="Attempt the final quest to rescue the captive. Performs the complete Hero's Ballad to charm the monster. Requires all song segments to be collected.",
        ),
    ]

    return tools


def get_tool_definitions() -> list[dict]:
    """Get tool definitions for documentation/testing purposes."""
    return [
        {"name": "get_player_stats", "description": "Get player stats"},
        {"name": "get_current_location", "description": "Get current location"},
        {"name": "start_travel", "description": "Start traveling to a location"},
        {"name": "check_exercise", "description": "Check exercise status"},
        {"name": "complete_exercise", "description": "Complete exercise"},
        {"name": "collect_song_segment", "description": "Collect a song segment"},
        {"name": "get_inventory", "description": "Get inventory"},
        {"name": "perform_at_tavern", "description": "Perform at tavern"},
        {"name": "check_final_quest_ready", "description": "Check final quest readiness"},
        {"name": "attempt_final_quest", "description": "Attempt final quest"},
    ]
