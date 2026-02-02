"""Entry point for ResoLute backend."""

import argparse
import sys


def main():
    """Main entry point for the ResoLute CLI."""
    parser = argparse.ArgumentParser(
        description="ResoLute - Music-learning adventure game backend",
        prog="resolute",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start the WebSocket server")
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    server_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    # Client command
    client_parser = subparsers.add_parser("client", help="Start the text client for testing")
    client_parser.add_argument(
        "--username", "-u",
        default="testuser",
        help="Username for login (default: testuser)",
    )
    client_parser.add_argument(
        "--password", "-p",
        default="testpass",
        help="Password for login (default: testpass)",
    )
    client_parser.add_argument(
        "--host",
        default="localhost",
        help="Server host to connect to (default: localhost)",
    )
    client_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port to connect to (default: 8000)",
    )

    args = parser.parse_args()

    if args.command == "server":
        import uvicorn

        uvicorn.run(
            "resolute.server.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )

    elif args.command == "client":
        # Override settings for client connection
        import os

        os.environ["HOST"] = args.host
        os.environ["PORT"] = str(args.port)

        from resolute.client.text import run

        run(args.username, args.password)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
