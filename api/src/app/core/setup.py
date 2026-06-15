"""Application factory + lifespan.

Stripped fork of boilerplate v0.15.0 ``core/setup.py``:
- removed ARQ queue pool, rate-limiter pool, and ``create_first_*`` hooks;
- removed the superuser-gated docs router (``get_current_superuser``);
- ``create_tables_on_start`` defaults to ``False`` — Alembic owns the schema
  (DEV_CONTRACT_AFK 鐵律 2), so the app never issues DDL on boot.

Kept: async SQLAlchemy table bootstrap helper, Redis cache pool lifecycle,
client-side cache middleware, environment-gated docs.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from typing import Any

import anyio
import fastapi
import redis.asyncio as redis
from fastapi import APIRouter, FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from ..middleware.client_cache_middleware import ClientCacheMiddleware
from ..models import *  # noqa: F403
from .config import (
    AppSettings,
    ClientSideCacheSettings,
    EnvironmentOption,
    EnvironmentSettings,
    RedisCacheSettings,
    settings,
)
from .db.database import Base
from .db.database import async_engine as engine
from .utils import cache


# -------------- database --------------
async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# -------------- cache --------------
async def create_redis_cache_pool() -> None:
    cache.pool = redis.ConnectionPool.from_url(settings.REDIS_CACHE_URL)
    cache.client = redis.Redis.from_pool(cache.pool)  # type: ignore


async def close_redis_cache_pool() -> None:
    if cache.client is not None:
        await cache.client.aclose()  # type: ignore


# -------------- application --------------
async def set_threadpool_tokens(number_of_tokens: int = 100) -> None:
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = number_of_tokens


def lifespan_factory(
    settings: AppSettings | RedisCacheSettings | ClientSideCacheSettings | EnvironmentSettings,
    create_tables_on_start: bool = False,
) -> Callable[[FastAPI], _AsyncGeneratorContextManager[Any]]:
    """Build a lifespan async context manager for a FastAPI app."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator:
        from asyncio import Event

        initialization_complete = Event()
        app.state.initialization_complete = initialization_complete

        await set_threadpool_tokens()

        try:
            if isinstance(settings, RedisCacheSettings):
                await create_redis_cache_pool()

            if create_tables_on_start:
                await create_tables()

            initialization_complete.set()

            yield

        finally:
            if isinstance(settings, RedisCacheSettings):
                await close_redis_cache_pool()

    return lifespan


def create_application(
    router: APIRouter,
    settings: AppSettings | RedisCacheSettings | ClientSideCacheSettings | EnvironmentSettings,
    create_tables_on_start: bool = False,
    lifespan: Callable[[FastAPI], _AsyncGeneratorContextManager[Any]] | None = None,
    **kwargs: Any,
) -> FastAPI:
    """Create and configure a FastAPI application from the provided settings."""
    if isinstance(settings, AppSettings):
        kwargs.update(
            {
                "title": settings.APP_NAME,
                "description": settings.APP_DESCRIPTION,
                "version": settings.APP_VERSION,
                "contact": {"name": settings.CONTACT_NAME, "email": settings.CONTACT_EMAIL},
                "license_info": {"name": settings.LICENSE_NAME},
            }
        )

    if isinstance(settings, EnvironmentSettings):
        kwargs.update({"docs_url": None, "redoc_url": None, "openapi_url": None})

    if lifespan is None:
        lifespan = lifespan_factory(settings, create_tables_on_start=create_tables_on_start)

    application = FastAPI(lifespan=lifespan, **kwargs)
    application.include_router(router)

    if isinstance(settings, ClientSideCacheSettings):
        application.add_middleware(ClientCacheMiddleware, max_age=settings.CLIENT_CACHE_MAX_AGE)

    if isinstance(settings, EnvironmentSettings):
        if settings.ENVIRONMENT != EnvironmentOption.PRODUCTION:
            docs_router = APIRouter()

            @docs_router.get("/docs", include_in_schema=False)
            async def get_swagger_documentation() -> fastapi.responses.HTMLResponse:
                return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")

            @docs_router.get("/redoc", include_in_schema=False)
            async def get_redoc_documentation() -> fastapi.responses.HTMLResponse:
                return get_redoc_html(openapi_url="/openapi.json", title="docs")

            @docs_router.get("/openapi.json", include_in_schema=False)
            async def openapi() -> dict[str, Any]:
                out: dict = get_openapi(
                    title=application.title, version=application.version, routes=application.routes
                )
                return out

            application.include_router(docs_router)

    return application
