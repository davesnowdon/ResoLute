"""FastAPI application with WebSocket endpoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from resolute.agent import MentorAgent
from resolute.config import get_settings
from resolute.server.messages import ClientMessage, ConnectionMessage, ServerMessage
from resolute.tracing import setup_tracing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.agents: dict[str, MentorAgent] = {}

    async def connect(self, websocket: WebSocket, player_id: str):
        """Accept a new connection and create an agent for the player."""
        await websocket.accept()
        self.active_connections[player_id] = websocket
        self.agents[player_id] = MentorAgent(player_name=player_id)
        logger.info(f"Player connected: {player_id}")

    def disconnect(self, player_id: str):
        """Remove a connection and clean up resources."""
        self.active_connections.pop(player_id, None)
        self.agents.pop(player_id, None)
        logger.info(f"Player disconnected: {player_id}")

    def get_agent(self, player_id: str) -> MentorAgent | None:
        """Get the agent for a player."""
        return self.agents.get(player_id)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_tracing()
    settings = get_settings()
    logger.info(f"ResoLute server starting on {settings.host}:{settings.port}")
    logger.info(f"Using Gemini model: {settings.gemini_model}")

    if not settings.has_google_api_key:
        logger.warning("GOOGLE_API_KEY not set - agent will fail to respond")

    yield

    # Shutdown
    logger.info("ResoLute server shutting down")


app = FastAPI(
    title="ResoLute Backend",
    description="WebSocket server for ResoLute music-learning game",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "resolute"}


@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    """WebSocket endpoint for player communication."""
    await manager.connect(websocket, player_id)

    # Send connection confirmation
    connection_msg = ConnectionMessage(
        type="connected",
        player_id=player_id,
        message=f"Welcome, {player_id}! Your mentor awaits.",
    )
    await websocket.send_json(connection_msg.model_dump())

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            try:
                msg = ClientMessage(**data)
            except ValidationError as e:
                error_response = ServerMessage(
                    type="error",
                    content=f"Invalid message format: {str(e)}",
                )
                await websocket.send_json(error_response.model_dump())
                continue

            # Handle different message types
            if msg.type == "chat":
                agent = manager.get_agent(player_id)
                if agent:
                    response_content = await agent.achat(msg.content, thread_id=player_id)
                    response = ServerMessage(
                        type="response",
                        content=response_content,
                        metadata={"message_type": "chat"},
                    )
                else:
                    response = ServerMessage(
                        type="error",
                        content="Agent not found for this session",
                    )
                await websocket.send_json(response.model_dump())

            elif msg.type == "status":
                # Return player status
                response = ServerMessage(
                    type="status",
                    content="Connected and ready",
                    metadata={"player_id": player_id, "connected": True},
                )
                await websocket.send_json(response.model_dump())

            elif msg.type == "quest":
                # Handle quest-related actions
                agent = manager.get_agent(player_id)
                if agent:
                    response_content = await agent.achat(
                        f"Quest action: {msg.content}", thread_id=player_id
                    )
                    response = ServerMessage(
                        type="response",
                        content=response_content,
                        metadata={"message_type": "quest"},
                    )
                else:
                    response = ServerMessage(
                        type="error",
                        content="Agent not found for this session",
                    )
                await websocket.send_json(response.model_dump())

    except WebSocketDisconnect:
        manager.disconnect(player_id)
        logger.info(f"Player {player_id} disconnected")
