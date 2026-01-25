"""FastAPI application with WebSocket endpoint."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from resolute.agent import MentorAgent
from resolute.config import get_settings
from resolute.context import AppContext, create_context
from resolute.db.seed_data import seed_exercises_and_songs
from resolute.db.session import create_tables
from resolute.game.services import PlayerService, WorldService
from resolute.server.handlers import MessageHandler
from resolute.server.messages import (
    ClientMessage,
    ConnectionMessage,
    ServerMessage,
    error_message,
    world_generating_message,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and per-player resources."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.agents: dict[str, MentorAgent] = {}

    async def connect(
        self, websocket: WebSocket, player_id: str, ctx: AppContext
    ) -> bool:
        """Accept a new connection and initialize player resources.

        Returns True if this is a new player (needs world generation).
        """
        await websocket.accept()
        self.active_connections[player_id] = websocket

        # Check if player has a world
        with ctx.session() as session:
            player_service = PlayerService(session)
            world_service = WorldService(session)

            player_result = player_service.get_or_create(player_id)
            player = player_result.unwrap()

            world_result = world_service.get_or_generate(player_id)
            world_data = world_result.unwrap()

            # Create agent
            agent = MentorAgent(
                player_id=player_id,
                session_factory=ctx.session_factory,
                timer=ctx.exercise_timer,
                model=ctx.settings.model,
                tracer=ctx.tracer,
                player_name=player.name,
            )
            self.agents[player_id] = agent

            needs_world = world_data.get("needs_generation", False)

        logger.info(f"Player connected: {player_id} (needs_world={needs_world})")
        return needs_world

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
    # Startup - create context
    ctx = create_context()
    app.state.ctx = ctx

    settings = get_settings()
    logger.info(f"ResoLute server starting on {settings.host}:{settings.port}")
    logger.info(f"Using model: {settings.model}")
    logger.info(f"Database: {settings.database_url}")

    # Initialize database
    create_tables(ctx.engine)
    with ctx.session() as session:
        seed_exercises_and_songs(session)
    logger.info("Database initialized")

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
    ctx: AppContext = app.state.ctx
    needs_world = await manager.connect(websocket, player_id, ctx)

    # Send connection confirmation
    connection_msg = ConnectionMessage(
        type="connected",
        player_id=player_id,
        message=f"Welcome, {player_id}! Your mentor awaits.",
        world_ready=not needs_world,
    )
    await websocket.send_json(connection_msg.model_dump())

    # Create message handler for this player
    handler = MessageHandler(player_id, ctx, manager.get_agent(player_id))

    # If player needs a world, start generation
    if needs_world:
        generating_msg = world_generating_message()
        await websocket.send_json(generating_msg.model_dump())

        world_msg = await asyncio.to_thread(handler.handle_world)
        await websocket.send_json(world_msg.model_dump())

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            logger.info(f"[{player_id}] Received message: {data.get('type', 'unknown')}")

            try:
                msg = ClientMessage(**data)
            except ValidationError as e:
                logger.error(f"[{player_id}] Invalid message format: {e}")
                response = error_message(f"Invalid message format: {str(e)}")
                await websocket.send_json(response.model_dump())
                continue

            # Route message to appropriate handler
            response: ServerMessage

            if msg.type == "chat":
                logger.info(f"[{player_id}] Processing chat message...")
                response = await asyncio.to_thread(handler.handle_chat, msg.content)
                logger.info(f"[{player_id}] Chat response ready")

            elif msg.type == "status":
                response = ServerMessage(
                    type="status",
                    content="Connected and ready",
                    data={"player_id": player_id, "connected": True},
                )

            elif msg.type == "world":
                response = await asyncio.to_thread(handler.handle_world)

            elif msg.type == "travel":
                response = handler.handle_travel(msg.content)

            elif msg.type == "exercise":
                action = msg.content or msg.data.get("action", "check")
                response = handler.handle_exercise(action)

            elif msg.type == "collect":
                segment_id = msg.data.get("segment_id")
                if segment_id is None:
                    try:
                        segment_id = int(msg.content)
                    except (ValueError, TypeError):
                        response = error_message("segment_id required")
                        await websocket.send_json(response.model_dump())
                        continue
                response = handler.handle_collect(segment_id)

            elif msg.type == "perform":
                response = handler.handle_perform()

            elif msg.type == "final_quest":
                action = msg.content or msg.data.get("action", "check")
                response = handler.handle_final_quest(action)

            elif msg.type == "inventory":
                response = handler.handle_inventory()

            elif msg.type == "quest":
                # Legacy quest handling - route through chat
                response = await asyncio.to_thread(
                    handler.handle_chat, f"Quest action: {msg.content}"
                )

            else:
                response = error_message(f"Unknown message type: {msg.type}")

            await websocket.send_json(response.model_dump())

    except WebSocketDisconnect:
        manager.disconnect(player_id)
        logger.info(f"Player {player_id} disconnected")
