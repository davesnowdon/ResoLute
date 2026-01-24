"""WebSocket message schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field  # noqa: I001

# Client message types
ClientMessageType = Literal[
    "chat",      # Chat with the mentor
    "status",    # Get connection status
    "quest",     # Quest-related actions (legacy)
    "world",     # Request world state
    "travel",    # Start travel to location
    "exercise",  # Exercise actions (start/check/complete)
    "collect",   # Collect song segment
    "perform",   # Tavern performance
    "final_quest",  # Final quest actions
    "inventory",    # Get inventory
]

# Server message types
ServerMessageType = Literal[
    "response",          # General response
    "error",             # Error message
    "status",            # Status update
    "world_state",       # Full world sync
    "world_generating",  # World being generated
    "exercise_state",    # Timer status
    "exercise_complete", # Exercise completed with rewards
    "segment_collected", # Segment collection confirmed
    "performance_result",  # Gold/reputation earned
    "game_complete",     # Victory!
    "location_update",   # Location changed
    "inventory_update",  # Inventory contents
]


class ClientMessage(BaseModel):
    """Message sent from client to server."""

    type: ClientMessageType = Field(
        description="Type of message"
    )
    player_id: str = Field(description="Unique identifier for the player")
    content: str = Field(default="", description="Message content or action parameter")
    data: dict[str, Any] = Field(default_factory=dict, description="Additional structured data")


class ServerMessage(BaseModel):
    """Message sent from server to client."""

    type: ServerMessageType = Field(
        description="Type of response"
    )
    content: str = Field(description="Response content or description")
    data: dict[str, Any] = Field(default_factory=dict, description="Structured response data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ConnectionMessage(BaseModel):
    """Message sent when a player connects or disconnects."""

    type: Literal["connected", "disconnected"] = Field(description="Connection event type")
    player_id: str = Field(description="Player who connected/disconnected")
    message: str = Field(description="Connection message")
    world_ready: bool = Field(default=False, description="Whether player has a world")


# Helper functions to create common server messages

def world_state_message(world_data: dict) -> ServerMessage:
    """Create a world state response message."""
    return ServerMessage(
        type="world_state",
        content=f"Welcome to {world_data.get('name', 'the realm')}!",
        data=world_data,
    )


def world_generating_message() -> ServerMessage:
    """Create a world generating notification."""
    return ServerMessage(
        type="world_generating",
        content="A new realm is being woven just for you...",
        data={"status": "generating"},
    )


def exercise_state_message(session_data: dict) -> ServerMessage:
    """Create an exercise state response."""
    remaining = session_data.get("remaining_seconds", 0)
    if session_data.get("is_complete"):
        content = f"Exercise '{session_data.get('exercise_name')}' complete! Call complete to receive rewards."
    else:
        content = f"Exercise '{session_data.get('exercise_name')}' in progress. {remaining:.0f}s remaining."
    return ServerMessage(
        type="exercise_state",
        content=content,
        data=session_data,
    )


def exercise_complete_message(result: dict) -> ServerMessage:
    """Create an exercise completion message with rewards."""
    rewards = result.get("rewards", {})
    xp = rewards.get("xp_gained", 0)
    gold = rewards.get("gold_gained", 0)
    skill = rewards.get("skill_bonus_type", "")
    skill_amt = rewards.get("skill_bonus_amount", 0)

    content = f"Exercise complete! +{xp} XP, +{gold} gold"
    if skill and skill_amt:
        content += f", +{skill_amt} {skill}"

    if rewards.get("level_up"):
        content += f" LEVEL UP! You are now level {rewards.get('new_level')}!"

    return ServerMessage(
        type="exercise_complete",
        content=content,
        data=result,
    )


def segment_collected_message(segment_data: dict) -> ServerMessage:
    """Create a segment collection confirmation."""
    segment = segment_data.get("segment", {})
    return ServerMessage(
        type="segment_collected",
        content=f"You learned '{segment.get('name', 'a song fragment')}'!",
        data=segment_data,
    )


def performance_result_message(result: dict) -> ServerMessage:
    """Create a performance result message."""
    rewards = result.get("rewards", {})
    gold = rewards.get("gold_gained", 0)
    rep = rewards.get("reputation_gained", 0)
    return ServerMessage(
        type="performance_result",
        content=f"The crowd cheers! +{gold} gold, +{rep} reputation",
        data=result,
    )


def game_complete_message(result: dict) -> ServerMessage:
    """Create a game completion message."""
    if result.get("victory"):
        content = f"Victory! You charmed {result.get('monster_charmed')} and rescued {result.get('rescued')}!"
    else:
        content = "The performance was not enough... Try again when you're ready."
    return ServerMessage(
        type="game_complete",
        content=content,
        data=result,
    )


def location_update_message(location_data: dict) -> ServerMessage:
    """Create a location update message."""
    loc = location_data.get("location", {})
    return ServerMessage(
        type="location_update",
        content=f"You arrived at {loc.get('name', 'a new location')}",
        data=location_data,
    )


def inventory_update_message(inventory_data: dict) -> ServerMessage:
    """Create an inventory update message."""
    count = len(inventory_data.get("collected_segments", []))
    total = inventory_data.get("total_segments", 4)
    return ServerMessage(
        type="inventory_update",
        content=f"Segments collected: {count}/{total}",
        data=inventory_data,
    )


def error_message(error: str) -> ServerMessage:
    """Create an error message."""
    return ServerMessage(
        type="error",
        content=error,
        data={"error": error},
    )
