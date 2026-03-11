#!/usr/bin/env python3
"""
Event Bus Server Launcher

Usage:
    python run_server.py [--host HOST] [--port PORT]

Example:
    python run_server.py --host 0.0.0.0 --port 8000
"""

import argparse
import uvicorn
from event_bus.server import create_server


def main():
    parser = argparse.ArgumentParser(description="Event Bus Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")

    args = parser.parse_args()

    print("=" * 60)
    print("Event Bus Server")
    print("=" * 60)
    print(f"Server will start at: http://{args.host}:{args.port}")
    print(f"Health check: http://{args.host}:{args.port}/health")
    print(f"API docs: http://{args.host}:{args.port}/docs")
    print("=" * 60)
    print()

    # Create server app
    app = create_server()

    # Run server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1
    )


if __name__ == "__main__":
    main()
