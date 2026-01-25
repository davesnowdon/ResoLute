"""Server module - FastAPI WebSocket server."""

from resolute.server.app import app
from resolute.server.handlers import MessageHandler

__all__ = ["app", "MessageHandler"]
