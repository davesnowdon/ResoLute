"""WebSocket message schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class ClientMessage(BaseModel):
    """Message sent from client to server."""

    type: Literal["chat", "status", "quest"] = Field(
        description="Type of message: chat for conversation, status for player status, quest for quest actions"
    )
    player_id: str = Field(description="Unique identifier for the player")
    content: str = Field(default="", description="Message content")


class ServerMessage(BaseModel):
    """Message sent from server to client."""

    type: Literal["response", "error", "status"] = Field(
        description="Type of response: response for normal replies, error for errors, status for status updates"
    )
    content: str = Field(description="Response content")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class ConnectionMessage(BaseModel):
    """Message sent when a player connects or disconnects."""

    type: Literal["connected", "disconnected"] = Field(description="Connection event type")
    player_id: str = Field(description="Player who connected/disconnected")
    message: str = Field(description="Connection message")
