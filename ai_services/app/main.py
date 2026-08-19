"""Nexus AI Services FastAPI application."""
import logging
import time

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routers import sql, ocr, health, ai_assistant
from app.security import require_api_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nexus Enterprise AI",
    version="1.0.0",
    description="AI microservices for the Nexus Enterprise Engine.",
)

def _parse_cors_origins(raw: str) -> list[str]:
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


# Health/readiness endpoint is intentionally open; all business endpoints are key-protected.
app.include_router(health.router)
app.include_router(
    sql.router,
    prefix="/api/v1/sql",
    tags=["sql-agent"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    ocr.router,
    prefix="/api/v1/ocr",
    tags=["ocr-engine"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    ai_assistant.router,
    prefix="/api/v1/ai",
    tags=["ai-assistant"],
    dependencies=[Depends(require_api_key)],
)