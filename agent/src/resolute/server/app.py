"""FastAPI application with WebSocket endpoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from resolute.agent import MentorAgent
from resolute.config import get_settings
from resolute.db.session import get_async_session, init_db
from resolute.game.state_manager import GameStateManager
from resolute.game.world_generator import get_world_generator
from resolute.server.messages import (
    ClientMessage,
    ConnectionMessage,
    ServerMessage,
    error_message,
    exercise_complete_message,
    exercise_state_message,
    game_complete_message,
    inventory_update_message,
    performance_result_message,
    segment_collected_message,
    world_generating_message,
    world_state_message,
)
from resolute.tracing import setup_tracing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and per-player resources."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.agents: dict[str, MentorAgent] = {}

    async def connect(self, websocket: WebSocket, player_id: str) -> bool:
        """Accept a new connection and initialize player resources.

        Returns True if this is a new player (needs world generation).
        """
        await websocket.accept()
        self.active_connections[player_id] = websocket

        # Check if player has a world
        async with get_async_session() as session:
            state_manager = GameStateManager(session)
            player = await state_manager.get_or_create_player(player_id)
            world_result = await state_manager.get_or_generate_world(player_id)

            # Create agent - tools create their own sessions to avoid greenlet issues
            agent = MentorAgent(
                player_id=player_id,
                player_name=player.name,
            )
            self.agents[player_id] = agent

            needs_world = world_result.get("needs_generation", False)

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
    # Startup
    setup_tracing()
    settings = get_settings()
    logger.info(f"ResoLute server starting on {settings.host}:{settings.port}")
    logger.info(f"Using Gemini model: {settings.gemini_model}")
    logger.info(f"Database: {settings.database_url}")

    if not settings.has_google_api_key:
        logger.warning("GOOGLE_API_KEY not set - agent will fail to respond")

    # Initialize database
    await init_db()
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


async def handle_world_request(player_id: str) -> ServerMessage:
    """Handle world state request, generating if needed."""
    async with get_async_session() as session:
        state_manager = GameStateManager(session)
        world_result = await state_manager.get_or_generate_world(player_id)

        if world_result.get("needs_generation"):
            # Generate a new world
            generator = get_world_generator()
            player = await state_manager.get_player(player_id)
            player_name = player.name if player else f"Bard {player_id[:8]}"

            try:
                world_data = await generator.generate_world(player_id, player_name)

                # Create the world in the database
                world = await state_manager.create_world(
                    player_id=player_id,
                    name=world_data["name"],
                    theme=world_data["theme"],
                    story_arc=world_data["story_arc"],
                    final_monster=world_data["final_monster"],
                    rescue_target=world_data["rescue_target"],
                    locations=world_data["locations"],
                )

                return world_state_message(world.to_dict())
            except Exception as e:
                logger.error(f"World generation failed: {e}")
                return error_message(f"Failed to generate world: {str(e)}")
        else:
            return world_state_message(world_result["world"])


async def handle_travel_request(player_id: str, destination: str) -> ServerMessage:
    """Handle travel request to start an exercise."""
    async with get_async_session() as session:
        state_manager = GameStateManager(session)

        # Get available destinations
        location_info = await state_manager.get_current_location(player_id)
        if location_info is None:
            return error_message("You have no current location")

        destinations = location_info.get("available_destinations", [])
        dest_match = None
        for d in destinations:
            if destination.lower() in d["name"].lower():
                dest_match = d
                break

        if dest_match is None:
            available = [d["name"] for d in destinations]
            return error_message(f"Unknown destination. Available: {', '.join(available)}")

        result = await state_manager.start_travel(player_id, dest_match["id"])

        if "error" in result:
            return error_message(result["error"])

        return exercise_state_message(result["session"])


async def handle_exercise_request(player_id: str, action: str) -> ServerMessage:
    """Handle exercise actions (check/complete)."""
    async with get_async_session() as session:
        state_manager = GameStateManager(session)

        if action == "check":
            status = await state_manager.check_exercise(player_id)
            if status is None:
                return error_message("No active exercise")
            return exercise_state_message(status)

        elif action == "complete":
            result = await state_manager.complete_exercise(player_id)
            if "error" in result:
                return error_message(result["error"])

            # Also send location update
            return exercise_complete_message(result)

        else:
            return error_message(f"Unknown exercise action: {action}")


async def handle_collect_request(player_id: str, segment_id: int) -> ServerMessage:
    """Handle segment collection."""
    async with get_async_session() as session:
        state_manager = GameStateManager(session)
        result = await state_manager.collect_segment(player_id, segment_id)

        if "error" in result:
            return error_message(result["error"])

        return segment_collected_message(result)


async def handle_perform_request(player_id: str) -> ServerMessage:
    """Handle tavern performance."""
    async with get_async_session() as session:
        state_manager = GameStateManager(session)
        result = await state_manager.perform_at_tavern(player_id)

        if "error" in result:
            return error_message(result["error"])

        return performance_result_message(result)


async def handle_final_quest_request(player_id: str, action: str) -> ServerMessage:
    """Handle final quest actions."""
    async with get_async_session() as session:
        state_manager = GameStateManager(session)

        if action == "check":
            result = await state_manager.check_final_quest_ready(player_id)
            content = (
                "You are ready for the final quest!"
                if result["ready"]
                else f"Collect more segments: {result['segments_collected']}/{result['segments_required']}"
            )
            return ServerMessage(
                type="response",
                content=content,
                data=result,
            )

        elif action == "attempt":
            result = await state_manager.complete_final_quest(player_id)
            if "error" in result:
                return error_message(result["error"])
            return game_complete_message(result)

        else:
            return error_message(f"Unknown final quest action: {action}")


async def handle_inventory_request(player_id: str) -> ServerMessage:
    """Handle inventory request."""
    async with get_async_session() as session:
        state_manager = GameStateManager(session)
        inventory = await state_manager.get_inventory(player_id)
        return inventory_update_message(inventory)


async def handle_chat_with_context(player_id: str, message: str) -> ServerMessage:
    """Handle chat message with game context."""
    agent = manager.get_agent(player_id)
    if not agent:
        return error_message("Agent not found for this session")

    # Tools create their own sessions to avoid greenlet issues with LangGraph
    response_content = await agent.achat(message, thread_id=player_id)

    return ServerMessage(
        type="response",
        content=response_content,
        metadata={"message_type": "chat"},
    )


@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    """WebSocket endpoint for player communication."""
    needs_world = await manager.connect(websocket, player_id)

    # Send connection confirmation
    connection_msg = ConnectionMessage(
        type="connected",
        player_id=player_id,
        message=f"Welcome, {player_id}! Your mentor awaits.",
        world_ready=not needs_world,
    )
    await websocket.send_json(connection_msg.model_dump())

    # If player needs a world, start generation
    if needs_world:
        generating_msg = world_generating_message()
        await websocket.send_json(generating_msg.model_dump())

        world_msg = await handle_world_request(player_id)
        await websocket.send_json(world_msg.model_dump())

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            try:
                msg = ClientMessage(**data)
            except ValidationError as e:
                response = error_message(f"Invalid message format: {str(e)}")
                await websocket.send_json(response.model_dump())
                continue

            # Route message to appropriate handler
            response: ServerMessage

            if msg.type == "chat":
                response = await handle_chat_with_context(player_id, msg.content)

            elif msg.type == "status":
                response = ServerMessage(
                    type="status",
                    content="Connected and ready",
                    data={"player_id": player_id, "connected": True},
                )

            elif msg.type == "world":
                response = await handle_world_request(player_id)

            elif msg.type == "travel":
                response = await handle_travel_request(player_id, msg.content)

            elif msg.type == "exercise":
                action = msg.content or msg.data.get("action", "check")
                response = await handle_exercise_request(player_id, action)

            elif msg.type == "collect":
                segment_id = msg.data.get("segment_id")
                if segment_id is None:
                    try:
                        segment_id = int(msg.content)
                    except (ValueError, TypeError):
                        response = error_message("segment_id required")
                        await websocket.send_json(response.model_dump())
                        continue
                response = await handle_collect_request(player_id, segment_id)

            elif msg.type == "perform":
                response = await handle_perform_request(player_id)

            elif msg.type == "final_quest":
                action = msg.content or msg.data.get("action", "check")
                response = await handle_final_quest_request(player_id, action)

            elif msg.type == "inventory":
                response = await handle_inventory_request(player_id)

            elif msg.type == "quest":
                # Legacy quest handling - route through chat
                response = await handle_chat_with_context(player_id, f"Quest action: {msg.content}")

            else:
                response = error_message(f"Unknown message type: {msg.type}")

            await websocket.send_json(response.model_dump())

    except WebSocketDisconnect:
        manager.disconnect(player_id)
        logger.info(f"Player {player_id} disconnected")
