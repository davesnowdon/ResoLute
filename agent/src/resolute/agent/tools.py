"""Agent tools for the MentorAgent with database integration."""

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from resolute.game.state_manager import GameStateManager


# Input schemas for tools that need parameters
class TravelInput(BaseModel):
    """Input for the start_travel tool."""

    destination_name: str = Field(description="The name of the destination to travel to")


class CollectSegmentInput(BaseModel):
    """Input for the collect_song_segment tool."""

    segment_id: int = Field(description="The ID of the segment to collect")


def create_tools_for_player(state_manager: GameStateManager, player_id: str) -> list:
    """Create tools bound to a specific player and state manager.

    Args:
        state_manager: The game state manager instance.
        player_id: The player's ID.

    Returns:
        List of StructuredTool instances.
    """

    async def get_player_stats() -> dict[str, Any]:
        """Get the current stats and progress for the player.
        Returns player level, XP, gold, reputation, and skill levels.
        """
        stats = await state_manager.get_player_stats(player_id)
        if stats is None:
            return {"error": "Player not found"}
        return stats

    async def get_current_location() -> dict[str, Any]:
        """Get the player's current location and available actions.
        Shows where the player is, available travel destinations,
        and any collectible song segments.
        """
        location = await state_manager.get_current_location(player_id)
        if location is None:
            return {"error": "Player has no current location. World may need to be generated."}
        return location

    async def start_travel(destination_name: str) -> dict[str, Any]:
        """Start traveling to a new location.
        This begins a timed practice exercise that must be completed
        before arriving at the destination.
        """
        location_info = await state_manager.get_current_location(player_id)
        if location_info is None:
            return {"error": "Cannot determine current location"}

        destinations = location_info.get("available_destinations", [])
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

        result = await state_manager.start_travel(player_id, destination["id"])
        return result

    async def check_exercise() -> dict[str, Any]:
        """Check the status of the current exercise.
        Shows time remaining and whether the exercise can be completed.
        """
        status = await state_manager.check_exercise(player_id)
        if status is None:
            return {"status": "no_active_exercise", "message": "No exercise in progress"}
        return status

    async def complete_exercise() -> dict[str, Any]:
        """Complete the current exercise and receive rewards.
        Can only be called after the exercise timer has finished.
        Awards XP, gold, and skill bonuses.
        """
        result = await state_manager.complete_exercise(player_id)
        return result

    async def collect_song_segment(segment_id: int) -> dict[str, Any]:
        """Collect a song segment from the current location.
        Song segments are pieces of the legendary Hero's Ballad
        that must be collected to complete the final quest.
        """
        result = await state_manager.collect_segment(player_id, segment_id)
        return result

    async def get_inventory() -> dict[str, Any]:
        """Get the player's inventory of collected song segments.
        Shows all segments collected and whether the player is
        ready for the final quest.
        """
        inventory = await state_manager.get_inventory(player_id)
        return inventory

    async def perform_at_tavern() -> dict[str, Any]:
        """Perform at the tavern to earn gold and reputation.
        Must be at a tavern location. Performance rewards scale
        with the number of song segments collected.
        """
        result = await state_manager.perform_at_tavern(player_id)
        return result

    async def check_final_quest_ready() -> dict[str, Any]:
        """Check if the player is ready for the final quest.
        The final quest requires all song segments to be collected.
        Shows progress toward the goal.
        """
        result = await state_manager.check_final_quest_ready(player_id)
        return result

    async def attempt_final_quest() -> dict[str, Any]:
        """Attempt the final quest to rescue the captive.
        Performs the complete Hero's Ballad to charm the monster.
        Requires all song segments to be collected.
        """
        result = await state_manager.complete_final_quest(player_id)
        return result

    # Create StructuredTool instances
    tools = [
        StructuredTool.from_function(
            coroutine=get_player_stats,
            name="get_player_stats",
            description="Get the current stats and progress for the player. Returns player level, XP, gold, reputation, and skill levels.",
        ),
        StructuredTool.from_function(
            coroutine=get_current_location,
            name="get_current_location",
            description="Get the player's current location and available actions. Shows where the player is, available travel destinations, and any collectible song segments.",
        ),
        StructuredTool.from_function(
            coroutine=start_travel,
            name="start_travel",
            description="Start traveling to a new location. This begins a timed practice exercise that must be completed before arriving at the destination.",
            args_schema=TravelInput,
        ),
        StructuredTool.from_function(
            coroutine=check_exercise,
            name="check_exercise",
            description="Check the status of the current exercise. Shows time remaining and whether the exercise can be completed.",
        ),
        StructuredTool.from_function(
            coroutine=complete_exercise,
            name="complete_exercise",
            description="Complete the current exercise and receive rewards. Can only be called after the exercise timer has finished. Awards XP, gold, and skill bonuses.",
        ),
        StructuredTool.from_function(
            coroutine=collect_song_segment,
            name="collect_song_segment",
            description="Collect a song segment from the current location. Song segments are pieces of the legendary Hero's Ballad that must be collected to complete the final quest.",
            args_schema=CollectSegmentInput,
        ),
        StructuredTool.from_function(
            coroutine=get_inventory,
            name="get_inventory",
            description="Get the player's inventory of collected song segments. Shows all segments collected and whether the player is ready for the final quest.",
        ),
        StructuredTool.from_function(
            coroutine=perform_at_tavern,
            name="perform_at_tavern",
            description="Perform at the tavern to earn gold and reputation. Must be at a tavern location. Performance rewards scale with the number of song segments collected.",
        ),
        StructuredTool.from_function(
            coroutine=check_final_quest_ready,
            name="check_final_quest_ready",
            description="Check if the player is ready for the final quest. The final quest requires all song segments to be collected. Shows progress toward the goal.",
        ),
        StructuredTool.from_function(
            coroutine=attempt_final_quest,
            name="attempt_final_quest",
            description="Attempt the final quest to rescue the captive. Performs the complete Hero's Ballad to charm the monster. Requires all song segments to be collected.",
        ),
    ]

    return tools


def get_mentor_tools() -> list:
    """Get a list of tool names/descriptions (for testing without state_manager).

    Note: This returns empty list as tools require state_manager context.
    Use create_tools_for_player() to get actual tools.
    """
    return []


# For backwards compatibility in tests
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
