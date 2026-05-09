import os
import uvicorn


def main() -> None:
    os.environ.setdefault("OPENSWARM_ENTERPRISE", "true")
    uvicorn.run("enterprise.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

