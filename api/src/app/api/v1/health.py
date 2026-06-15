"""Liveness endpoint (replaces boilerplate auth-coupled root routes)."""

from fastapi import APIRouter

from ...core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION or "0.0.0",
    }
