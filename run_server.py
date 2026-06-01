"""
Start the Betsy server.

Usage:
  python run_server.py              # port 8000, auto-reload on
  python run_server.py --no-reload  # production-like, no reload
  python run_server.py --port 8080  # custom port

Dashboard:  http://localhost:8000
Betsy UI:   http://localhost:8000/betsy
API docs:   http://localhost:8000/docs
"""
import argparse
import os
import sys

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start the Betsy mock server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true")
    parser.add_argument("--interval", type=int, default=30,
                        help="Agent auto-run interval in minutes (default: 30)")
    args = parser.parse_args()

    os.environ.setdefault("AGENT_INTERVAL_MINUTES", str(args.interval))

    print(f"\nBetsy server starting on http://localhost:{args.port}")
    print(f"  Dashboard : http://localhost:{args.port}")
    print(f"  Betsy UI  : http://localhost:{args.port}/betsy")
    print(f"  API docs  : http://localhost:{args.port}/docs")
    print(f"  Auto-run  : every {args.interval} min  (set --interval to change)")
    print(f"  Reload    : {'off' if args.no_reload else 'on'}")
    print()

    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
