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
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).parent))

from shared.preflight import run_betsy_checks


def main():
    parser = argparse.ArgumentParser(description="Start the Betsy server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true")
    parser.add_argument("--run-every-days", type=int, default=1,
                        help="Agent runs every N sim days (default: 1)")
    args = parser.parse_args()

    os.environ.setdefault("AGENT_RUN_EVERY_DAYS", str(args.run_every_days))

    print(f"\nBetsy server starting on http://localhost:{args.port}")
    print(f"  Betsy UI  : http://localhost:{args.port}/betsy")
    print(f"  Dev view  : http://localhost:{args.port}")
    print(f"  API docs  : http://localhost:{args.port}/docs")
    print(f"  Agent     : runs every {args.run_every_days} sim day(s)")
    print(f"  Reload    : {'off' if args.no_reload else 'on'}")
    run_betsy_checks()

    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
