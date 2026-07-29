"""
Start both services: the world (simulated ERP, :8001) and Betsy (:8000).

Usage:
  python run_all.py

Then open http://localhost:8000/betsy and press ▶ Play.
Ctrl+C stops both.
"""
import subprocess
import sys
import time


def main():
    procs = []
    try:
        print("Starting world service on :8001 ...")
        procs.append(subprocess.Popen([sys.executable, "run_world.py"]))
        time.sleep(2)
        print("Starting Betsy on :8000 ...")
        procs.append(subprocess.Popen([sys.executable, "run_server.py", "--no-reload"]))
        print("\nBoth services up:")
        print("  Betsy UI  : http://localhost:8000/betsy")
        print("  Dev view  : http://localhost:8000")
        print("  World API : http://localhost:8001/docs")
        print("\nCtrl+C to stop both.\n")
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()
