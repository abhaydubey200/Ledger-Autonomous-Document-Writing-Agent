#!/usr/bin/env python3
"""
Convenience launcher for the Autonomous Document Agent.

    python run.py

Starts the uvicorn server on the host/port from .env (default 0.0.0.0:8000).
Open http://127.0.0.1:8000 in a browser to use the app.
"""
from dotenv import load_dotenv

load_dotenv()

import os
import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"Ledger - Autonomous Document Agent")
    print(f"{"-" * 42}")
    print(f"Frontend : http://127.0.0.1:{port}")
    print(f"API docs : http://127.0.0.1:{port}/docs")
    print(f"Health   : http://127.0.0.1:{port}/health")
    print()
    print(f"Server starting...")
    uvicorn.run("main:app", host=host, port=port, reload=True)
