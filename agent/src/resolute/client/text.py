"""Text client for testing the WebSocket server."""

import asyncio
import json
import sys

import websockets

from resolute.config import get_settings


async def main(player_name: str = "test-player"):
    """Run the text client for testing.

    Args:
        player_name: The player name to use for the connection.
    """
    settings = get_settings()
    uri = f"ws://{settings.host}:{settings.port}/ws/{player_name}"

    print(f"Connecting to {uri}...")
    print("Type 'quit' or 'exit' to disconnect")
    print("-" * 50)

    try:
        async with websockets.connect(uri) as websocket:
            # Receive connection message
            connection_msg = await websocket.recv()
            connection_data = json.loads(connection_msg)
            print(f"Server: {connection_data.get('message', 'Connected')}")
            print("-" * 50)

            while True:
                # Get user input
                try:
                    user_input = input("You: ").strip()
                except EOFError:
                    break

                if not user_input:
                    continue

                if user_input.lower() in ("quit", "exit"):
                    print("Disconnecting...")
                    break

                # Send message to server
                message = {
                    "type": "chat",
                    "player_id": player_name,
                    "content": user_input,
                }
                await websocket.send(json.dumps(message))

                # Receive response
                response = await websocket.recv()
                response_data = json.loads(response)

                if response_data.get("type") == "error":
                    print(f"Error: {response_data.get('content', 'Unknown error')}")
                else:
                    print(f"Mentor: {response_data.get('content', 'No response')}")

                print("-" * 50)

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
