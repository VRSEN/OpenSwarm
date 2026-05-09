import time
from collections import defaultdict, deque
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .database import create_all
from .settings import get_settings
from .web import router as web_router

_requests: dict[str, deque[float]] = defaultdict(deque)


def create_app() -> FastAPI:
    settings = get_settings()
    create_all()
    app = FastAPI(title=settings.app_name, version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_bytes:
            return JSONResponse({"detail": "Request too large"}, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        ip = request.client.host if request.client else "unknown"
        bucket = _requests[ip]
        now = time.time()
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        bucket.append(now)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "service": settings.app_name}

    @app.get("/metrics")
    def metrics() -> dict:
        return {"openswarm_enterprise_up": 1}

    app.mount("/static", StaticFiles(directory="enterprise/static"), name="static")
    app.include_router(api_router)
    app.include_router(web_router)
    return app


app = create_app()

