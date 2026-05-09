# FastAPI entry point — run with: python server.py
#
# Provider switching at runtime: the SwitchProvider tool on the orchestrator
# rewrites .env and reloads os.environ in this process. Agency-swarm rebuilds
# the agency on every chat/run request, so subsequent requests pick up the
# new DEFAULT_MODEL automatically — no server restart required. In-flight
# requests keep their existing agency until they finish.

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
