# FastAPI entry point - run with: python server.py

import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    if os.getenv("OPENSWARM_ENTERPRISE", "").lower() in {"1", "true", "yes"}:
        import uvicorn

        uvicorn.run("enterprise.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False)
    else:
        from agency_swarm.integrations.fastapi import run_fastapi
        from swarm import create_agency

        run_fastapi(
            agencies={
                "open-swarm": create_agency,
            },
            port=8080,
            enable_logging=True,
            allowed_local_file_dirs=[
                "./uploads",
            ],
        )
