"""JimQ FastAPI entrypoint.

Stripped fork of boilerplate v0.15.0 ``main.py``: removed crudadmin mount and
admin lifespan. Wires the resource/health router + settings, and (卡 #7) mounts
the WebSocket streaming gateway with a composed lifespan that — alongside the
boilerplate Redis-cache lifespan — creates the in-process hub and, when a
Nautilus stream key is configured (``JIMQ_STREAM_KEY``), starts the consumer
task reading the Redis Streams bus (localhost DB0).
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from .api import router
from .core.config import settings
from .core.setup import create_application, lifespan_factory
from .services.hub import Hub
from .ws.app_factory import (
    LATEST_SENTINEL,
    LATEST_STREAM_KEY,
    _as_str,
    bus_redis_url,
    make_streaming_lifespan,
)
from .ws.stream import register_ws

logger = logging.getLogger(__name__)


async def _resolve_stream_key_async() -> str | None:
    """解析 ``JIMQ_STREAM_KEY``(支援 ``@latest`` sentinel,讀 bus DB0)。

    ``@latest`` 需查 Redis 的已知 key(engine backtest 寫入),故用短暫 async
    client 在 lifespan 內解析(async get 需 await,故不直接用同步 resolve_stream_key)。
    """
    configured = os.environ.get("JIMQ_STREAM_KEY")
    if not configured:
        return None
    if configured != LATEST_SENTINEL:
        return configured
    client = aioredis.from_url(bus_redis_url())
    try:
        return _as_str(await client.get(LATEST_STREAM_KEY))
    finally:
        await client.aclose()


def _composed_lifespan():
    """Boilerplate cache lifespan + 串流(hub + 選用 consumer)lifespan。"""
    boilerplate = lifespan_factory(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        async with boilerplate(app):
            stream_key = await _resolve_stream_key_async()
            if stream_key:
                logger.info("串流 consumer 啟動,stream key = %s", stream_key)
                streaming = make_streaming_lifespan(stream_key=stream_key)
                async with streaming(app):
                    yield
            else:
                # 無 stream key:仍建 hub 讓 WS 端點可用(等未來灌入)。
                logger.info("未設 JIMQ_STREAM_KEY 或 @latest 尚無資料;僅啟用空 hub")
                app.state.hub = Hub()
                yield

    return lifespan


app = create_application(router=router, settings=settings, lifespan=_composed_lifespan())
register_ws(app)
