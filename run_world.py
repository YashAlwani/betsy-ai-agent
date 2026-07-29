"""
Start the World service (simulated ERP).

Usage:
  python run_world.py               # port 8001, no reload
  python run_world.py --reload      # dev mode
  python run_world.py --port 8002   # custom port

API docs: http://localhost:8001/docs
"""
import argparse
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).parent))

from shared.preflight import run_world_checks


def main():
    parser = argparse.ArgumentParser(description="Start the Betsy World service")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print(f"\nWorld service starting on http://localhost:{args.port}")
    print(f"  API docs : http://localhost:{args.port}/docs")
    run_world_checks()

    uvicorn.run(
        "world.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
