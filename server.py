# FastAPI entry point — run with: python server.py
#
# NOTE: This entry point creates the agency once at startup and serves it
# for the lifetime of the process. The SwitchProvider tool registered on
# the orchestrator writes to .env and signals a restart, but only the TUI
# loop in run_utils.main() reads that signal — the FastAPI surface does
# not. Provider switches issued through this server appear to succeed but
# stay pinned to the original DEFAULT_MODEL until the server is restarted.

import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

from swarm import create_agency
from agency_swarm.integrations.fastapi import run_fastapi


if __name__ == "__main__":
    run_fastapi(
        agencies={
            # you must export your create agency function here
            "open-swarm": create_agency,
        },
        port=8080,
        enable_logging=True,
        allowed_local_file_dirs=[
            "./uploads",
        ],
    )
