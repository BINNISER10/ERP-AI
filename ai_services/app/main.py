"""Nexus AI Services FastAPI application."""
import logging

from fastapi import FastAPI

from app.routers import sql, ocr, health, ai_assistant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nexus Enterprise AI",
    version="1.0.0",
    description="AI microservices for the Nexus Enterprise Engine.",
)

app.include_router(health.router)
app.include_router(sql.router, prefix="/api/v1/sql", tags=["sql-agent"])
app.include_router(ocr.router, prefix="/api/v1/ocr", tags=["ocr-engine"])
app.include_router(ai_assistant.router, prefix="/api/v1/ai", tags=["ai-assistant"])
