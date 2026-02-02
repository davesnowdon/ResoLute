"""Text client for testing the WebSocket server."""

import asyncio
import json
import sys

import websockets

from resolute.config import get_settings

HELP_TEXT = """
Available commands:
  /world          - View your world and locations
  /location       - View current location and available actions
  /travel <name>  - Travel to a location (starts exercise)
  /exercise       - Check exercise status
  /complete       - Complete current exercise
  /collect <id>   - Collect a song segment by ID
  /inventory      - View collected segments
  /perform        - Perform at tavern (must be at tavern)
  /quest          - Check final quest readiness
  /final          - Attempt the final quest
  /help           - Show this help
  quit/exit       - Disconnect

Or just type a message to chat with your mentor!
"""


def parse_command(user_input: str, player_id: str) -> dict | None:
    """Parse user input into a message dict.

    Returns None for quit commands.
    """
    text = user_input.strip()

    if text.lower() in ("quit", "exit"):
        return None

    if text.startswith("/"):
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "help":
            print(HELP_TEXT)
            return {"_skip": True}

        elif cmd == "world":
            return {"type": "world", "player_id": player_id, "content": ""}

        elif cmd in ("location", "loc", "where"):
            return {
                "type": "chat",
                "player_id": player_id,
                "content": "Where am I? What can I do here?",
            }

        elif cmd == "travel":
            if not arg:
                print("Usage: /travel <destination name>")
                return {"_skip": True}
            return {"type": "travel", "player_id": player_id, "content": arg}

        elif cmd in ("exercise", "ex", "status"):
            return {"type": "exercise", "player_id": player_id, "content": "check"}

        elif cmd in ("complete", "done", "finish"):
            return {"type": "exercise", "player_id": player_id, "content": "complete"}

        elif cmd == "collect":
            if not arg:
                print("Usage: /collect <segment_id>")
                return {"_skip": True}
            try:
                segment_id = int(arg)
                return {
                    "type": "collect",
                    "player_id": player_id,
                    "content": "",
                    "data": {"segment_id": segment_id},
                }
            except ValueError:
                print("Segment ID must be a number")
                return {"_skip": True}

        elif cmd in ("inventory", "inv", "segments"):
            return {"type": "inventory", "player_id": player_id, "content": ""}

        elif cmd == "perform":
            return {"type": "perform", "player_id": player_id, "content": ""}

        elif cmd in ("quest", "ready"):
            return {"type": "final_quest", "player_id": player_id, "content": "check"}

        elif cmd == "final":
            return {"type": "final_quest", "player_id": player_id, "content": "attempt"}

        else:
            print(f"Unknown command: /{cmd}")
            print("Type /help for available commands")
            return {"_skip": True}

    else:
        # Regular chat message
        return {"type": "chat", "player_id": player_id, "content": text}


def format_response(response_data: dict) -> str:
    """Format a server response for display."""
    msg_type = response_data.get("type", "response")
    content = response_data.get("content", "")
    data = response_data.get("data", {})

    if msg_type == "error":
        return f"[ERROR] {content}"

    elif msg_type == "auth_success":
        player = data.get("player", {})
        return f"[AUTH] Welcome {player.get("name", "player")}! Level {player.get("level", 1)}"

    elif msg_type == "auth_failed":
        return f"[AUTH FAILED] {content}"

    elif msg_type == "world_state":
        lines = [f"[WORLD] {content}"]
        if "locations" in data:
            lines.append("Locations:")
            for loc in data["locations"]:
                status = "unlocked" if loc.get("is_unlocked") else "locked"
                lines.append(f"  - {loc["name"]} ({loc["type"]}) [{status}]")
                if loc.get("segments"):
                    for seg in loc["segments"]:
                        lines.append(f"      Segment: {seg["name"]} (ID: {seg["id"]})")
        if data.get("final_monster"):
            lines.append(f"Final Boss: {data["final_monster"]}")
        if data.get("rescue_target"):
            lines.append(f"Rescue: {data["rescue_target"]}")
        return "\n".join(lines)

    elif msg_type == "world_generating":
        return f"[GENERATING] {content}"

    elif msg_type == "exercise_state":
        if data.get("is_complete"):
            return f"[EXERCISE] {data.get("exercise_name", "Exercise")} COMPLETE! Type /complete to finish."
        else:
            remaining = data.get("remaining_seconds", 0)
            progress = data.get("progress_percent", 0)
            return f"[EXERCISE] {data.get("exercise_name", "Exercise")} - {progress:.0f}% ({remaining:.0f}s left)"

    elif msg_type == "exercise_complete":
        rewards = data.get("rewards", {})
        lines = [f"[COMPLETE] {content}"]
        if data.get("new_location_id"):
            lines.append("You have arrived at your destination!")
        return "\n".join(lines)

    elif msg_type == "segment_collected":
        segment = data.get("segment", {})
        return f"[COLLECTED] {segment.get("name", "Segment")} - {segment.get("description", "")}"

    elif msg_type == "inventory_update":
        lines = [f"[INVENTORY] {content}"]
        for seg in data.get("collected_segments", []):
            lines.append(f"  - {seg["name"]}")
        if data.get("can_perform_final"):
            lines.append("You have all segments! You can attempt the final quest with /final")
        return "\n".join(lines)

    elif msg_type == "performance_result":
        rewards = data.get("rewards", {})
        return f"[PERFORMANCE] {content} (Score: {rewards.get("performance_score", 0)}%)"

    elif msg_type == "game_complete":
        if data.get("victory"):
            return f"[VICTORY] {content}"
        else:
            return f"[DEFEAT] {content}"

    elif msg_type == "location_update":
        loc = data.get("location", {})
        lines = [f"[LOCATION] {content}"]
        if loc:
            lines.append(f"  Name: {loc.get("name", "Unknown")}")
            lines.append(f"  Type: {loc.get("type", "unknown")}")
        return "\n".join(lines)

    else:
        return f"[{msg_type.upper()}] {content}"


async def authenticate(websocket, username: str, password: str) -> tuple[bool, str | None]:
    """Send authenticate message and handle response.

    Returns (success, player_id) tuple.
    """
    # First, receive the server's welcome message
    welcome = await websocket.recv()
    welcome_data = json.loads(welcome)
    print(f"Server: {welcome_data.get('message', 'Connected')}")

    # Send authenticate message
    auth_msg = {
        "type": "authenticate",
        "content": "",
        "data": {
            "username": username,
            "password": password
        }
    }

    await websocket.send(json.dumps(auth_msg))
    response = await websocket.recv()
    response_data = json.loads(response)

    print(format_response(response_data))

    if response_data.get("type") == "auth_success":
        player_id = response_data.get("data", {}).get("player_id")
        return True, player_id
    else:
        return False, None


async def main(username: str = "test", password: str = "test"):
    """Run the text client for testing.

    Args:
        username: The username for login.
        password: The password for login.
    """
    settings = get_settings()
    uri = f"ws://{settings.host}:{settings.port}/ws"

    print(f"Connecting to {uri}...")
    print("-" * 60)

    try:
        async with websockets.connect(uri) as websocket:
            # Authenticate first
            print(f"Logging in as {username}...")
            success, player_id = await authenticate(websocket, username, password)

            if not success:
                print("Authentication failed. Disconnecting.")
                return

            print(f"Authenticated! Player ID: {player_id}")
            print("Type /help for commands, or just chat with your mentor!")
            print("-" * 60)

            while True:
                # Get user input
                try:
                    user_input = input("You: ").strip()
                except EOFError:
                    break

                if not user_input:
                    continue

                # Parse command
                message = parse_command(user_input, player_id)

                if message is None:
                    print("Disconnecting...")
                    break

                if message.get("_skip"):
                    continue

                # Send message to server
                await websocket.send(json.dumps(message))

                # Receive response
                response = await websocket.recv()
                response_data = json.loads(response)

                print(format_response(response_data))
                print("-" * 60)

    except websockets.exceptions.ConnectionClosed:
        print("Connection closed by server")
    except ConnectionRefusedError:
        print(f"Could not connect to server at {uri}")
        print("Make sure the server is running: hatch run server")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nDisconnected")


def run(username: str = "test", password: str = "test"):
    """Run the text client synchronously.

    Args:
        username: The username for login.
        password: The password for login.
    """
    asyncio.run(main(username, password))


if __name__ == "__main__":
    # Parse command line args: username [password]
    user = sys.argv[1] if len(sys.argv) > 1 else "test"
    pwd = sys.argv[2] if len(sys.argv) > 2 else "test"
    run(user, pwd)
