"""FastAPI application with WebSocket endpoint and static file serving."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import ValidationError

from resolute.agent import MentorAgent
from resolute.config import get_settings
from resolute.context import AppContext, create_context
from resolute.db.seed_data import seed_exercises_and_songs
from resolute.db.session import create_tables
from resolute.game.services import PlayerService, WorldService
from resolute.server.handlers import AuthHandler, MessageHandler
from resolute.server.messages import (
    ClientMessage,
    ConnectionMessage,
    ServerMessage,
    error_message,
    world_generating_message,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CrossOriginIsolationMiddleware(BaseHTTPMiddleware):
    """Middleware to add Cross-Origin Isolation headers required by Godot web exports.

    Godot 4.x web exports require SharedArrayBuffer for threading, which requires:
    - Cross-Origin-Opener-Policy: same-origin
    - Cross-Origin-Embedder-Policy: require-corp
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add Cross-Origin Isolation headers
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        return response


def get_web_build_path() -> Path | None:
    """Get the path to the Godot web build directory.

    Returns None if no valid build directory is found.
    """
    # Check environment variable first (for deployment flexibility)
    env_path = os.environ.get("RESOLUTE_WEB_BUILD_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists() and (path / "index.html").exists():
            return path

    # Get the directory containing this file
    this_file = Path(__file__).resolve()

    # Default paths to check (relative to different possible working directories)
    possible_paths = [
        # From src/resolute/server/app.py -> go up to agent/, then up to ResoLute/, then build/web
        this_file.parent.parent.parent.parent.parent / "build" / "web",
        # From current working directory
        Path.cwd() / "build" / "web",
        # From parent of cwd (if running from agent/)
        Path.cwd().parent / "build" / "web",
        # Docker/container deployment
        Path("/app/build/web"),
    ]

    for path in possible_paths:
        resolved = path.resolve()
        if resolved.exists() and (resolved / "index.html").exists():
            logger.info(f"Found web build at: {resolved}")
            return resolved

    logger.warning("No web build directory found. Checked paths:")
    for path in possible_paths:
        logger.warning(f"  - {path.resolve()} (exists: {path.exists()})")

    return None


class ConnectionManager:
    """Manages WebSocket connections and per-player resources."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.agents: dict[str, MentorAgent] = {}

    async def connect_authenticated(
        self, websocket: WebSocket, player_id: str, ctx: AppContext
    ) -> bool:
        """Initialize player resources after authentication.

        Returns True if this is a new player (needs world generation).
        """
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

        logger.info(f"Player session initialized: {player_id} (needs_world={needs_world})")
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

# Detect web build path at module load time
_web_build_path = get_web_build_path()


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

    # Log web build path
    if _web_build_path:
        logger.info(f"Serving Godot web build from: {_web_build_path}")
        logger.info("Cross-Origin Isolation headers enabled for SharedArrayBuffer support")
    else:
        logger.warning("Web build directory not found!")
        logger.warning("Run 'make export-web' or './export_web.sh' to build the game")

    yield

    # Shutdown
    logger.info("ResoLute server shutting down")


app = FastAPI(
    title="ResoLute Backend",
    description="WebSocket server for ResoLute music-learning game with integrated web frontend",
    version="0.1.0",
    lifespan=lifespan,
)

# Add Cross-Origin Isolation middleware (required for Godot web exports)
# This must be added before other middleware
app.add_middleware(CrossOriginIsolationMiddleware)

# Add CORS middleware for API access from other origins if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "resolute"}


@app.get("/api/info")
async def api_info():
    """API information endpoint."""
    return {
        "service": "resolute",
        "version": "0.1.0",
        "web_build_available": _web_build_path is not None,
        "web_build_path": str(_web_build_path) if _web_build_path else None,
        "cross_origin_isolation": True,
        "endpoints": {
            "websocket": "/ws",
            "health": "/health",
            "game": "/" if _web_build_path else None,
        }
    }


@app.websocket("/ws")
async def websocket_endpoint_auth(websocket: WebSocket):
    """WebSocket endpoint with authentication required.

    Flow:
    1. Client connects
    2. Server sends 'connected' message
    3. Client sends 'authenticate' message with credentials
    4. Server validates and sends 'auth_success' or 'auth_failed'
    5. If authenticated, normal message handling begins
    """
    ctx: AppContext = app.state.ctx
    await websocket.accept()

    # Send connection confirmation (pre-auth)
    connection_msg = ConnectionMessage(
        type="connected",
        message="Connected to ResoLute. Please authenticate.",
    )
    await websocket.send_json(connection_msg.model_dump())

    player_id: str | None = None
    auth_handler = AuthHandler(ctx)

    try:
        # Wait for authentication
        while player_id is None:
            raw_message = await websocket.receive_text()
            try:
                data = ClientMessage.model_validate_json(raw_message)
            except ValidationError as e:
                await websocket.send_json(error_message(f"Invalid message format: {e}").model_dump())
                continue

            if data.type != "authenticate":
                await websocket.send_json(
                    error_message("Please authenticate first. Send type='authenticate' with username and password.").model_dump()
                )
                continue

            # Process authentication
            username = data.data.get("username", "")
            password = data.data.get("password", "")

            success, auth_msg, authenticated_player_id = auth_handler.authenticate(username, password)
            await websocket.send_json(auth_msg.model_dump())

            if success:
                player_id = authenticated_player_id
                logger.info(f"Player authenticated: {player_id}")
            else:
                logger.warning(f"Authentication failed for: {username}")

        # Initialize player session
        needs_world = await manager.connect_authenticated(websocket, player_id, ctx)

        # Create message handler for this player
        handler = MessageHandler(player_id, ctx, manager.get_agent(player_id))

        # If player needs a world, start generation
        if needs_world:
            generating_msg = world_generating_message()
            await websocket.send_json(generating_msg.model_dump())

            world_msg = await asyncio.to_thread(handler.handle_world)
            await websocket.send_json(world_msg.model_dump())

        # Main message loop
        while True:
            raw_message = await websocket.receive_text()
            try:
                data = ClientMessage.model_validate_json(raw_message)
            except ValidationError as e:
                await websocket.send_json(error_message(f"Invalid message: {e}").model_dump())
                continue

            # Route message to appropriate handler
            logger.info(f"[{player_id}] Processing {data.type} message...")
            response = await handle_message(data, handler)
            logger.info(f"[{player_id}] Responding with {response.type} message.")

            await websocket.send_json(response.model_dump())

    except WebSocketDisconnect:
        if player_id:
            manager.disconnect(player_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if player_id:
            manager.disconnect(player_id)


async def handle_message(data: ClientMessage, handler: MessageHandler) -> ServerMessage:
    """Route a message to the appropriate handler."""
    msg_type = data.type

    if msg_type == "chat":
        return await asyncio.to_thread(handler.handle_chat, data.content)

    elif msg_type == "world":
        return await asyncio.to_thread(handler.handle_world)

    elif msg_type == "location":
        return await asyncio.to_thread(handler.handle_location)

    elif msg_type == "player":
        return await asyncio.to_thread(handler.handle_player)

    elif msg_type == "travel":
        return await asyncio.to_thread(handler.handle_travel, data.content)

    elif msg_type == "exercise":
        return await asyncio.to_thread(handler.handle_exercise, data.content)

    elif msg_type == "collect":
        segment_id = data.data.get("segment_id")
        if segment_id is None:
            return error_message("segment_id required in data")
        return await asyncio.to_thread(handler.handle_collect, segment_id)

    elif msg_type == "inventory":
        return await asyncio.to_thread(handler.handle_inventory)

    elif msg_type == "perform":
        score = data.data.get("score", 1.0) if data.data else 1.0
        return await asyncio.to_thread(handler.handle_perform, score)

    elif msg_type == "final_quest":
        return await asyncio.to_thread(handler.handle_final_quest, data.content)

    elif msg_type == "status":
        return ServerMessage(
            type="status",
            content="Connected and authenticated",
            data={"status": "ok"},
        )

    else:
        return error_message(f"Unknown message type: {msg_type}")


# Mount static files for the Godot web build
# This must be done after all API routes are defined
if _web_build_path:
    # Serve index.html explicitly at root to ensure it works
    @app.get("/", response_class=HTMLResponse)
    async def serve_game_index():
        """Serve the game index.html at root."""
        index_path = _web_build_path / "index.html"
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        return HTMLResponse("<h1>Game not found</h1>", status_code=404)

    # Mount static files for all other game assets
    app.mount("/", StaticFiles(directory=str(_web_build_path)), name="game")
else:
    @app.get("/")
    async def game_not_built():
        """Fallback when game is not built."""
        return {
            "message": "ResoLute game not built yet",
            "instructions": "Run 'make export-web' or './export_web.sh' from the ResoLute directory to build the game",
            "api_available": True,
            "websocket_endpoint": "/ws",
        }
