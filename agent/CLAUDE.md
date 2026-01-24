# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ResoLute is a music-learning adventure game that transforms New Year resolutions into a D&D-inspired fantasy quest. Players become bards guided by an AI mentor, learning music through dynamic quests and adaptive challenges.

## Repository Structure

```
/resolute/
├── agent/          # Backend (Python) - AI mentor, game logic, API
└── ui/             # Frontend (Godot 4) - Game client, pixel art UI
```

### Backend Structure (agent/)

```
agent/
├── .python-version      # pyenv virtualenv: "resolute"
├── .env.example         # API keys template
├── pyproject.toml       # Hatch + Ruff config
├── src/resolute/
│   ├── __init__.py
│   ├── __main__.py      # CLI entry point
│   ├── config.py        # Pydantic settings
│   ├── agent/           # MentorAgent (LangGraph + Gemini)
│   ├── server/          # FastAPI WebSocket server
│   ├── client/          # Text client for testing
│   └── tracing/         # Opik observability
└── tests/
```

## Tech Stack

- **Backend**: Python (pyenv virtualenv: `resolute`)
- **AI Framework**: LangChain + LangGraph with Google Gemini
- **Observability**: Opik for LLM tracing
- **Server**: FastAPI with WebSocket support
- **Frontend**: Godot 4 (GDScript)

## Development Commands

All commands use Hatch from the `agent/` directory:

| Command | Purpose |
|---------|---------|
| `hatch run server` | Start WebSocket server (uvicorn, port 8000) |
| `hatch run client` | Start text client for testing |
| `hatch run test` | Run pytest |
| `hatch run lint` | Run Ruff linting |
| `hatch run format` | Run Ruff formatting |

## Environment Setup

1. Copy `.env.example` to `.env`
2. Set `GOOGLE_API_KEY` for Gemini
3. Optionally set `OPIK_API_KEY` for tracing

## WebSocket Protocol

Connect to `ws://localhost:8000/ws/{player_id}`

**Client messages:**
```json
{"type": "chat", "player_id": "player1", "content": "Hello!"}
{"type": "status", "player_id": "player1"}
{"type": "quest", "player_id": "player1", "content": "start"}
```

**Server messages:**
```json
{"type": "response", "content": "...", "metadata": {}}
{"type": "error", "content": "..."}
{"type": "status", "content": "...", "metadata": {}}
```
