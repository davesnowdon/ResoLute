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
from resolute.game.services import ExerciseService, PlayerService, QuestService, WorldService
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
                google_api_key=ctx.settings.google_api_key,
                gemini_model=ctx.settings.gemini_model,
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
    logger.info(f"Using Gemini model: {settings.gemini_model}")
    logger.info(f"Database: {settings.database_url}")

    if not settings.has_google_api_key:
        logger.warning("GOOGLE_API_KEY not set - agent will fail to respond")

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


def handle_world_request(player_id: str, ctx: AppContext) -> ServerMessage:
    """Handle world state request, generating if needed."""
    logger.info(f"[{player_id}] World request")
    with ctx.session() as session:
        world_service = WorldService(session)
        player_service = PlayerService(session)

        result = world_service.get_or_generate(player_id)
        if result.is_err:
            return error_message(result.error)

        world_data = result.unwrap()

        if world_data.get("needs_generation"):
            # Generate a new world (sync AI call)
            logger.info(f"[{player_id}] Generating new world...")
            generator = ctx.world_generator

            player_result = player_service.get_player(player_id)
            player_name = (
                player_result.unwrap().name
                if player_result.is_ok
                else f"Bard {player_id[:8]}"
            )

            try:
                generated_data = generator.generate_world(player_id, player_name)
                logger.info(
                    f"[{player_id}] World generated: {generated_data.get('name', 'unknown')}"
                )

                # Create the world in the database
                create_result = world_service.create_world(
                    player_id=player_id,
                    name=generated_data["name"],
                    theme=generated_data["theme"],
                    story_arc=generated_data["story_arc"],
                    final_monster=generated_data["final_monster"],
                    rescue_target=generated_data["rescue_target"],
                    locations=generated_data["locations"],
                )

                if create_result.is_err:
                    return error_message(create_result.error)

                world = create_result.unwrap()
                return world_state_message(world.to_dict())
            except Exception as e:
                logger.error(f"World generation failed: {e}")
                return error_message(f"Failed to generate world: {str(e)}")
        else:
            return world_state_message(world_data["world"])


def handle_travel_request(
    player_id: str, destination: str, ctx: AppContext
) -> ServerMessage:
    """Handle travel request to start an exercise."""
    with ctx.session() as session:
        player_service = PlayerService(session)
        exercise_service = ExerciseService(session, ctx.exercise_timer)

        # Get available destinations
        loc_result = player_service.get_current_location(player_id)
        if loc_result.is_err:
            return error_message(loc_result.error)

        location_info = loc_result.unwrap()
        destinations = location_info.get("available_destinations", [])

        dest_match = None
        for d in destinations:
            if destination.lower() in d["name"].lower():
                dest_match = d
                break

        if dest_match is None:
            available = [d["name"] for d in destinations]
            return error_message(f"Unknown destination. Available: {', '.join(available)}")

        result = exercise_service.start_travel(player_id, dest_match["id"])
        if result.is_err:
            return error_message(result.error)

        return exercise_state_message(result.unwrap()["session"])


def handle_exercise_request(
    player_id: str, action: str, ctx: AppContext
) -> ServerMessage:
    """Handle exercise actions (check/complete)."""
    with ctx.session() as session:
        exercise_service = ExerciseService(session, ctx.exercise_timer)

        if action == "check":
            result = exercise_service.check_exercise(player_id)
            if result.is_err:
                return error_message(result.error)
            return exercise_state_message(result.unwrap())

        elif action == "complete":
            result = exercise_service.complete_exercise(player_id)
            if result.is_err:
                return error_message(result.error)
            return exercise_complete_message(result.unwrap())

        else:
            return error_message(f"Unknown exercise action: {action}")


def handle_collect_request(
    player_id: str, segment_id: int, ctx: AppContext
) -> ServerMessage:
    """Handle segment collection."""
    with ctx.session() as session:
        quest_service = QuestService(session)
        result = quest_service.collect_segment(player_id, segment_id)

        if result.is_err:
            return error_message(result.error)

        return segment_collected_message(result.unwrap())


def handle_perform_request(player_id: str, ctx: AppContext) -> ServerMessage:
    """Handle tavern performance."""
    with ctx.session() as session:
        quest_service = QuestService(session)
        result = quest_service.perform_at_tavern(player_id)

        if result.is_err:
            return error_message(result.error)

        return performance_result_message(result.unwrap())


def handle_final_quest_request(
    player_id: str, action: str, ctx: AppContext
) -> ServerMessage:
    """Handle final quest actions."""
    with ctx.session() as session:
        quest_service = QuestService(session)

        if action == "check":
            result = quest_service.check_final_quest_ready(player_id)
            if result.is_err:
                return error_message(result.error)

            data = result.unwrap()
            content = (
                "You are ready for the final quest!"
                if data["ready"]
                else f"Collect more segments: {data['segments_collected']}/{data['segments_required']}"
            )
            return ServerMessage(
                type="response",
                content=content,
                data=data,
            )

        elif action == "attempt":
            result = quest_service.complete_final_quest(player_id)
            if result.is_err:
                return error_message(result.error)
            return game_complete_message(result.unwrap())

        else:
            return error_message(f"Unknown final quest action: {action}")


def handle_inventory_request(player_id: str, ctx: AppContext) -> ServerMessage:
    """Handle inventory request."""
    with ctx.session() as session:
        quest_service = QuestService(session)
        result = quest_service.get_inventory(player_id)

        if result.is_err:
            return error_message(result.error)

        return inventory_update_message(result.unwrap())


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

    # If player needs a world, start generation
    if needs_world:
        generating_msg = world_generating_message()
        await websocket.send_json(generating_msg.model_dump())

        world_msg = await asyncio.to_thread(handle_world_request, player_id, ctx)
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
                response = await asyncio.to_thread(handle_world_request, player_id, ctx)

            elif msg.type == "travel":
                response = handle_travel_request(player_id, msg.content, ctx)

            elif msg.type == "exercise":
                action = msg.content or msg.data.get("action", "check")
                response = handle_exercise_request(player_id, action, ctx)

            elif msg.type == "collect":
                segment_id = msg.data.get("segment_id")
                if segment_id is None:
                    try:
                        segment_id = int(msg.content)
                    except (ValueError, TypeError):
                        response = error_message("segment_id required")
                        await websocket.send_json(response.model_dump())
                        continue
                response = handle_collect_request(player_id, segment_id, ctx)

            elif msg.type == "perform":
                response = handle_perform_request(player_id, ctx)

            elif msg.type == "final_quest":
                action = msg.content or msg.data.get("action", "check")
                response = handle_final_quest_request(player_id, action, ctx)

            elif msg.type == "inventory":
                response = handle_inventory_request(player_id, ctx)

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
