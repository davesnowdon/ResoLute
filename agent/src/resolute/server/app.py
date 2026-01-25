"""FastAPI application with WebSocket endpoint."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from resolute.agent import MentorAgent
from resolute.config import get_settings
from resolute.db.session import get_session, init_db
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
        with get_session() as session:
            state_manager = GameStateManager(session)
            player = state_manager.get_or_create_player(player_id)
            world_result = state_manager.get_or_generate_world(player_id)

            # Create agent - tools create their own sessions
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

    # Initialize database (sync)
    init_db()
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


def handle_world_request(player_id: str) -> ServerMessage:
    """Handle world state request, generating if needed."""
    logger.info(f"[{player_id}] World request")
    with get_session() as session:
        state_manager = GameStateManager(session)
        world_result = state_manager.get_or_generate_world(player_id)

        if world_result.get("needs_generation"):
            # Generate a new world (sync AI call)
            logger.info(f"[{player_id}] Generating new world...")
            generator = get_world_generator()
            player = state_manager.get_player(player_id)
            player_name = player.name if player else f"Bard {player_id[:8]}"

            try:
                world_data = generator.generate_world(player_id, player_name)
                logger.info(f"[{player_id}] World generated: {world_data.get('name', 'unknown')}")

                # Create the world in the database
                world = state_manager.create_world(
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


def handle_travel_request(player_id: str, destination: str) -> ServerMessage:
    """Handle travel request to start an exercise."""
    with get_session() as session:
        state_manager = GameStateManager(session)

        # Get available destinations
        location_info = state_manager.get_current_location(player_id)
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

        result = state_manager.start_travel(player_id, dest_match["id"])

        if "error" in result:
            return error_message(result["error"])

        return exercise_state_message(result["session"])


def handle_exercise_request(player_id: str, action: str) -> ServerMessage:
    """Handle exercise actions (check/complete)."""
    with get_session() as session:
        state_manager = GameStateManager(session)

        if action == "check":
            status = state_manager.check_exercise(player_id)
            if status is None:
                return error_message("No active exercise")
            return exercise_state_message(status)

        elif action == "complete":
            result = state_manager.complete_exercise(player_id)
            if "error" in result:
                return error_message(result["error"])

            # Also send location update
            return exercise_complete_message(result)

        else:
            return error_message(f"Unknown exercise action: {action}")


def handle_collect_request(player_id: str, segment_id: int) -> ServerMessage:
    """Handle segment collection."""
    with get_session() as session:
        state_manager = GameStateManager(session)
        result = state_manager.collect_segment(player_id, segment_id)

        if "error" in result:
            return error_message(result["error"])

        return segment_collected_message(result)


def handle_perform_request(player_id: str) -> ServerMessage:
    """Handle tavern performance."""
    with get_session() as session:
        state_manager = GameStateManager(session)
        result = state_manager.perform_at_tavern(player_id)

        if "error" in result:
            return error_message(result["error"])

        return performance_result_message(result)


def handle_final_quest_request(player_id: str, action: str) -> ServerMessage:
    """Handle final quest actions."""
    with get_session() as session:
        state_manager = GameStateManager(session)

        if action == "check":
            result = state_manager.check_final_quest_ready(player_id)
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
            result = state_manager.complete_final_quest(player_id)
            if "error" in result:
                return error_message(result["error"])
            return game_complete_message(result)

        else:
            return error_message(f"Unknown final quest action: {action}")


def handle_inventory_request(player_id: str) -> ServerMessage:
    """Handle inventory request."""
    with get_session() as session:
        state_manager = GameStateManager(session)
        inventory = state_manager.get_inventory(player_id)
        return inventory_update_message(inventory)


def handle_chat_with_context(player_id: str, message: str) -> ServerMessage:
    """Handle chat message with game context."""
    logger.info(f"[{player_id}] Chat request: {message[:50]}...")
    agent = manager.get_agent(player_id)
    if not agent:
        logger.error(f"[{player_id}] Agent not found")
        return error_message("Agent not found for this session")

    # Sync chat - run in thread pool from WebSocket handler
    logger.info(f"[{player_id}] Invoking agent...")
    response_content = agent.chat(message, thread_id=player_id)
    logger.info(f"[{player_id}] Agent response received: {response_content[:50]}...")

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

        world_msg = await asyncio.to_thread(handle_world_request, player_id)
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
                response = await asyncio.to_thread(
                    handle_chat_with_context, player_id, msg.content
                )
                logger.info(f"[{player_id}] Chat response ready")

            elif msg.type == "status":
                response = ServerMessage(
                    type="status",
                    content="Connected and ready",
                    data={"player_id": player_id, "connected": True},
                )

            elif msg.type == "world":
                response = await asyncio.to_thread(handle_world_request, player_id)

            elif msg.type == "travel":
                response = handle_travel_request(player_id, msg.content)

            elif msg.type == "exercise":
                action = msg.content or msg.data.get("action", "check")
                response = handle_exercise_request(player_id, action)

            elif msg.type == "collect":
                segment_id = msg.data.get("segment_id")
                if segment_id is None:
                    try:
                        segment_id = int(msg.content)
                    except (ValueError, TypeError):
                        response = error_message("segment_id required")
                        await websocket.send_json(response.model_dump())
                        continue
                response = handle_collect_request(player_id, segment_id)

            elif msg.type == "perform":
                response = handle_perform_request(player_id)

            elif msg.type == "final_quest":
                action = msg.content or msg.data.get("action", "check")
                response = handle_final_quest_request(player_id, action)

            elif msg.type == "inventory":
                response = handle_inventory_request(player_id)

            elif msg.type == "quest":
                # Legacy quest handling - route through chat
                response = await asyncio.to_thread(
                    handle_chat_with_context, player_id, f"Quest action: {msg.content}"
                )

            else:
                response = error_message(f"Unknown message type: {msg.type}")

            await websocket.send_json(response.model_dump())

    except WebSocketDisconnect:
        manager.disconnect(player_id)
        logger.info(f"Player {player_id} disconnected")
