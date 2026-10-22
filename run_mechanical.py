#!/usr/bin/env python
"""
Run the Integrity Engine API + UI only (no OpenSwarm agents).

Use this when python server.py is too heavy or port 8080 is occupied.

  python run_mechanical.py

Then open the URLs printed in the terminal (default port 8090).
"""

import logging
import os
import socket

import uvicorn

from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_mechanical")

PORT = int(os.getenv("PORT", "8090"))


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def _pick_port(preferred: int) -> int:
    if _port_free(preferred):
        return preferred
    for candidate in (8090, 8091, 8092, 8093, 8094, 8095):
        if _port_free(candidate):
            logger.warning("Port %s busy — using %s instead. Set PORT in .env to fix.", preferred, candidate)
            return candidate
    raise RuntimeError("No free port found between 8090-8095")


if __name__ == "__main__":
    from backend.app import create_mechanical_app

    port = _pick_port(PORT)
    app = create_mechanical_app()

    base = f"http://localhost:{port}"
    logger.info("=" * 60)
    logger.info("Integrity Engine running on %s", base)
    logger.info("  Get Started:     %s/static/get-started.html", base)
    logger.info("  Command Center:  %s/static/index.html", base)
    logger.info("  Ask Advisor:     %s/static/advisor.html (needs python server.py)", base)
    logger.info("  Learn:           %s/static/learn.html", base)
    logger.info("  Admin (ops):    %s/static/admin/", base)
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=port)
