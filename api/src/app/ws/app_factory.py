"""卡 #7 — 串流 app 工廠 + 串流 lifespan。

把 consumer→hub→ws gateway 串成一個可啟動的 FastAPI app:
- lifespan 啟動時:建 ``Hub`` 掛上 ``app.state.hub``、開 async Redis 連線
  (localhost DB0 bus)、起 consumer asyncio task(``run_consumer`` 讀 stream
  key → normalize → ``hub.publish``)。
- 關閉時:set stop event、cancel task、關 Redis 連線。

``build_streaming_app`` 供 e2e / 部署使用;主 app(``main.py``)以
``streaming_lifespan`` 在既有 boilerplate lifespan 之外掛上串流。

只連 localhost DB0(鐵律 4/5);read 路徑非阻塞(consumer 跑在 asyncio task)。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from jimq_core.constants import REDIS_BUS_DB

from ..services.hub import Hub
from ..services.nautilus_consumer import run_consumer
from .stream import register_ws

# Nautilus bus Redis(localhost DB0)。
DEFAULT_REDIS_URL = f"redis://localhost:6379/{REDIS_BUS_DB}"


def make_streaming_lifespan(
    *,
    stream_key: str,
    redis_url: str = DEFAULT_REDIS_URL,
):
    """建一個啟動 hub + Redis consumer task 的 lifespan。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        hub = Hub()
        app.state.hub = hub
        client = aioredis.from_url(redis_url)
        stop = asyncio.Event()
        task = asyncio.create_task(
            run_consumer(client, stream_key, hub.publish, stop_event=stop)
        )
        app.state.consumer_task = task
        try:
            yield
        finally:
            stop.set()
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            await client.aclose()

    return lifespan


def build_streaming_app(
    *,
    stream_key: str,
    redis_url: str = DEFAULT_REDIS_URL,
) -> FastAPI:
    """建一個只含 WS gateway + 串流 lifespan 的精簡 app(e2e / 部署用)。"""
    app = FastAPI(lifespan=make_streaming_lifespan(stream_key=stream_key, redis_url=redis_url))
    register_ws(app)
    return app
