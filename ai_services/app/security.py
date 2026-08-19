"""Shared security dependencies for the Nexus AI services."""
import hmac
import logging

from fastapi import Header, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    """Require a shared API key on every request with constant-time comparison.

    The service refuses to start serving protected routes unless
    AI_SERVICES_API_KEY is set.
    """
    expected = settings.api_services_api_key
    if not expected:
        logger.error("AI_SERVICES_API_KEY is not configured; refusing authenticated requests.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not configured correctly (missing API key setup).",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )