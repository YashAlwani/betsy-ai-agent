"""
Start the World service (simulated ERP).

Usage:
  python run_world.py               # port 8001, no reload
  python run_world.py --reload      # dev mode
  python run_world.py --port 8002   # custom port

API docs: http://localhost:8001/docs
"""
import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start the Betsy World service")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print(f"\nWorld service starting on http://localhost:{args.port}")
    print(f"  API docs : http://localhost:{args.port}/docs")
    print()

    uvicorn.run(
        "world.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
