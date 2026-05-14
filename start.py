#!/usr/bin/env python3
"""Launch AgriVani backend and Streamlit frontend together."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent


def python_bin() -> str:
    candidate = ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def streamlit_bin() -> list[str]:
    py = python_bin()
    return [py, "-m", "streamlit"]


def main() -> int:
    load_dotenv(ROOT / ".env")
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port = os.getenv("BACKEND_PORT", "8000")
    frontend_port = os.getenv("FRONTEND_PORT", "8501")

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))

    backend_cmd = [
        python_bin(),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        host,
        "--port",
        backend_port,
        "--reload",
    ]
    frontend_cmd = [
        *streamlit_bin(),
        "run",
        str(ROOT / "frontend" / "streamlit_app.py"),
        "--server.port",
        frontend_port,
        "--server.address",
        "127.0.0.1",
    ]

    processes: list[subprocess.Popen[str]] = []

    def shutdown(signum: int | None = None, frame: object | None = None) -> None:
        print("\nShutting down AgriVani services...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        deadline = time.time() + 8
        for proc in processes:
            remaining = max(0.1, deadline - time.time())
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                proc.kill()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Starting FastAPI backend at http://{host}:{backend_port}")
    processes.append(subprocess.Popen(backend_cmd, cwd=ROOT, env=env, text=True))
    time.sleep(1.5)
    print(f"Starting Streamlit frontend at http://127.0.0.1:{frontend_port}")
    processes.append(subprocess.Popen(frontend_cmd, cwd=ROOT, env=env, text=True))

    print("\nAgriVani is running.")
    print(f"Backend docs: http://{host}:{backend_port}/docs")
    print(f"Frontend:     http://127.0.0.1:{frontend_port}")

    try:
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    shutdown()
                    return proc.returncode or 1
            time.sleep(1)
    finally:
        shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
