# FastAPI entry point — run with: python server.py
#
# Integrity Engine only (recommended — fast, no OpenSwarm load):
#   python run_mechanical.py
#
# Full Financial Advisor (AI chat + Integrity Engine):
#   python server.py
#   set AGENCY=financial  (default when unset)
#
# Generic OpenSwarm (legacy):
#   set AGENCY=openswarm
#
# Port: set PORT in .env (default 8090)

import logging
import os

import uvicorn
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

PORT = int(os.getenv("PORT", "8090"))
MECHANICAL_ONLY = os.getenv("MECHANICAL_ONLY", "").lower() in ("1", "true", "yes")
AGENCY_MODE = os.getenv("AGENCY", "financial").lower()

if __name__ == "__main__":
    if MECHANICAL_ONLY:
        from backend.app import create_mechanical_app

        app = create_mechanical_app()
    else:
        from agency_swarm.integrations.fastapi import run_fastapi
        from backend.app import register_mechanical_routes

        if AGENCY_MODE == "openswarm":
            from swarm import create_agency as create_agency_factory
            agency_key = "open-swarm"
        else:
            from financial_swarm import create_agency as create_agency_factory
            agency_key = "Architect_Blueprint"

        app = run_fastapi(
            agencies={agency_key: create_agency_factory},
            port=PORT,
            enable_logging=True,
            allowed_local_file_dirs=["./uploads", "./mnt"],
            return_app=True,
        )
        register_mechanical_routes(app)

    base = f"http://localhost:{PORT}"
    logger.info("=" * 60)
    logger.info("Listening on %s", base)
    logger.info("  Get Started:   %s/static/get-started.html", base)
    logger.info("  Home UI:       %s/static/index.html", base)
    logger.info("  Ask Advisor:   %s/static/advisor.html", base)
    if not MECHANICAL_ONLY and AGENCY_MODE != "openswarm":
        logger.info("  Chat API:      %s/Architect_Blueprint/get_response", base)
        logger.info("  Studio:        %s/static/studio.html", base)
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=PORT)
