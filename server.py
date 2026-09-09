# FastAPI entry point — run with: python server.py

import logging
import os

from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

# Agency Swarm's FastAPI integration reads APP_TOKEN by default. Accept API_TOKEN
# as an alias so users with the documented alternate name still get auth enabled.
# Never map model keys (e.g. OPENAI_API_KEY) here — HTTP bearer secrets only.
if not os.getenv("APP_TOKEN", "").strip() and os.getenv("API_TOKEN", "").strip():
    os.environ["APP_TOKEN"] = os.getenv("API_TOKEN", "").strip()

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
