# ResoLute

ResoLute is a music-learning adventure game that transforms your New Year resolutions into an epic fantasy quest! Step into the shoes of a bard in a vibrant, D&D-inspired world, guided by a time-traveling mentor AI. Blending music education, motivational mechanics, and personalized storytelling, ResoLute turns real-life goals—like learning bass guitar—into engaging adventures with dynamic quests, playful reminders, and adaptive challenges. With its modular skill system, pixel art style, and clever wordplay name, ResoLute offers a unique, immersive experience designed to help you stay inspired and achieve your resolutions through the power of music and fantasy.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Godot 4.5+ (for building the game)
- Make (optional, for convenience commands)

### Development Setup

```bash
# Build the game (requires Godot 4.5)
./export_web.sh
# Or: make export-web

# Run the service
hatch run server

# Run the text test client
hatch run client
```

The game will be available at `http://localhost:8000`

### Using Make Commands

```bash
make help          # Show all available commands
make build-all     # Build game + install dependencies
make run           # Run the full service
make dev           # Run with auto-reload (development)
make deploy-check  # Verify deployment readiness
```

## 🏗️ Architecture

```
ResoLute/
├── ui/                 # Godot 4.5 game project
├── build/web/          # Exported web game (generated)
├── agent/              # Python backend
│   └── src/resolute/
│       ├── server/     # FastAPI + WebSocket server
│       ├── agent/      # AI Mentor agent
│       ├── game/       # Game logic services
│       └── db/         # Database models
├── export_web.sh       # Game export script
└── Makefile            # Convenience commands
```

## 🌐 Deployment

### Single Service Deployment

The backend serves both the API and the Godot web export, making deployment simple:

```bash
# Build everything
make build-all

# Run the service
RESOLUTE_HOST=0.0.0.0 RESOLUTE_PORT=8000 make run
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RESOLUTE_HOST` | Server host | `0.0.0.0` |
| `RESOLUTE_PORT` | Server port | `8000` |
| `RESOLUTE_MODEL` | LLM model to use | `gpt-4o-mini` |
| `RESOLUTE_DATABASE_URL` | Database connection | `sqlite:///resolute.db` |
| `RESOLUTE_WEB_BUILD_PATH` | Path to game build | Auto-detected |
| `OPENAI_API_KEY` | OpenAI API key | Required |


## 🔌 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Game frontend (Godot web export) |
| `GET /health` | Health check |
| `GET /api/info` | Service information |
| `WS /ws` | WebSocket game connection |

## 🎯 Game Flow

1. **Login** - Authenticate with username/password
2. **World Generation** - AI generates a unique world for you
3. **Explore** - Travel between locations
4. **Practice** - Complete music exercises to travel
5. **Collect** - Gather song fragments at each location
6. **Perform** - Play at taverns for gold and reputation
7. **Final Quest** - Defeat the boss with your complete song!

## 📝 License

MIT License - See LICENSE file for details.

# Credits

- Cute Fantasy asset pack by [Kenmi](https://kenmi-art.itch.io/)
