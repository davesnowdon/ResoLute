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


def parse_command(user_input: str, player_name: str) -> dict | None:
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
            return {"type": "world", "player_id": player_name, "content": ""}

        elif cmd in ("location", "loc", "where"):
            return {"type": "chat", "player_id": player_name, "content": "Where am I? What can I do here?"}

        elif cmd == "travel":
            if not arg:
                print("Usage: /travel <destination name>")
                return {"_skip": True}
            return {"type": "travel", "player_id": player_name, "content": arg}

        elif cmd in ("exercise", "ex", "status"):
            return {"type": "exercise", "player_id": player_name, "content": "check"}

        elif cmd in ("complete", "done", "finish"):
            return {"type": "exercise", "player_id": player_name, "content": "complete"}

        elif cmd == "collect":
            if not arg:
                print("Usage: /collect <segment_id>")
                return {"_skip": True}
            try:
                segment_id = int(arg)
                return {"type": "collect", "player_id": player_name, "content": "", "data": {"segment_id": segment_id}}
            except ValueError:
                print("Segment ID must be a number")
                return {"_skip": True}

        elif cmd in ("inventory", "inv", "segments"):
            return {"type": "inventory", "player_id": player_name, "content": ""}

        elif cmd == "perform":
            return {"type": "perform", "player_id": player_name, "content": ""}

        elif cmd in ("quest", "ready"):
            return {"type": "final_quest", "player_id": player_name, "content": "check"}

        elif cmd == "final":
            return {"type": "final_quest", "player_id": player_name, "content": "attempt"}

        else:
            print(f"Unknown command: /{cmd}")
            print("Type /help for available commands")
            return {"_skip": True}

    else:
        # Regular chat message
        return {"type": "chat", "player_id": player_name, "content": text}


def format_response(response_data: dict) -> str:
    """Format a server response for display."""
    msg_type = response_data.get("type", "response")
    content = response_data.get("content", "")
    data = response_data.get("data", {})

    if msg_type == "error":
        return f"[ERROR] {content}"

    elif msg_type == "world_state":
        lines = [f"[WORLD] {content}"]
        if "locations" in data:
            lines.append("Locations:")
            for loc in data["locations"]:
                status = "unlocked" if loc.get("is_unlocked") else "locked"
                lines.append(f"  - {loc['name']} ({loc['type']}) [{status}]")
                if loc.get("segments"):
                    for seg in loc["segments"]:
                        lines.append(f"      Segment: {seg['name']} (ID: {seg['id']})")
        if data.get("final_monster"):
            lines.append(f"Final Boss: {data['final_monster']}")
        if data.get("rescue_target"):
            lines.append(f"Rescue: {data['rescue_target']}")
        return "\n".join(lines)

    elif msg_type == "world_generating":
        return f"[GENERATING] {content}"

    elif msg_type == "exercise_state":
        if data.get("is_complete"):
            return f"[EXERCISE] {data.get('exercise_name', 'Exercise')} COMPLETE! Type /complete to finish."
        else:
            remaining = data.get("remaining_seconds", 0)
            progress = data.get("progress_percent", 0)
            return f"[EXERCISE] {data.get('exercise_name', 'Exercise')} - {progress:.0f}% ({remaining:.0f}s left)"

    elif msg_type == "exercise_complete":
        rewards = data.get("rewards", {})
        lines = [f"[COMPLETE] {content}"]
        if data.get("new_location_id"):
            lines.append("You have arrived at your destination!")
        return "\n".join(lines)

    elif msg_type == "segment_collected":
        segment = data.get("segment", {})
        return f"[COLLECTED] {segment.get('name', 'Segment')} - {segment.get('description', '')}"

    elif msg_type == "inventory_update":
        lines = [f"[INVENTORY] {content}"]
        for seg in data.get("collected_segments", []):
            lines.append(f"  - {seg['name']}")
        if data.get("can_perform_final"):
            lines.append("You have all segments! You can attempt the final quest with /final")
        return "\n".join(lines)

    elif msg_type == "performance_result":
        rewards = data.get("rewards", {})
        return f"[PERFORMANCE] {content} (Score: {rewards.get('performance_score', 0)}%)"

    elif msg_type == "game_complete":
        if data.get("victory"):
            return f"[VICTORY] {content}"
        else:
            return f"[DEFEAT] {content}"

    elif msg_type == "location_update":
        return f"[LOCATION] {content}"

    else:
        return f"[{msg_type.upper()}] {content}"


async def main(player_name: str = "test-player"):
    """Run the text client for testing.

    Args:
        player_name: The player name to use for the connection.
    """
    settings = get_settings()
    uri = f"ws://{settings.host}:{settings.port}/ws/{player_name}"

    print(f"Connecting to {uri}...")
    print("Type /help for commands, or just chat with your mentor!")
    print("-" * 60)

    try:
        async with websockets.connect(uri) as websocket:
            # Receive connection message
            connection_msg = await websocket.recv()
            connection_data = json.loads(connection_msg)
            print(f"Server: {connection_data.get('message', 'Connected')}")

            # Check if world needs generation
            if not connection_data.get("world_ready", True):
                print("Generating your world...")
                # Receive world_generating message
                msg = await websocket.recv()
                data = json.loads(msg)
                print(format_response(data))

                # Receive world_state message
                msg = await websocket.recv()
                data = json.loads(msg)
                print(format_response(data))

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
                message = parse_command(user_input, player_name)

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


def run(player_name: str = "test-player"):
    """Run the text client synchronously.

    Args:
        player_name: The player name to use for the connection.
    """
    asyncio.run(main(player_name))


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else "test-player"
    run(player)
