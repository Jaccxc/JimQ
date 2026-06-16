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
import os
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI

from jimq_core.constants import REDIS_BUS_DB

from ..services.consumer_supervisor import ConsumerSupervisor
from ..services.hub import Hub
from ..services.nautilus_consumer import run_consumer
from .stream import register_ws

# Nautilus bus Redis(localhost DB0)。
DEFAULT_REDIS_URL = f"redis://localhost:6379/{REDIS_BUS_DB}"

# engine 把實際 stream key(帶隨機 instance_id)寫到這個已知 Redis key,供
# API 端在 ``JIMQ_STREAM_KEY=@latest`` 時解析(卡 #10 全棧整合)。
LATEST_STREAM_KEY = "jimq:latest_stream_key"
# ``JIMQ_STREAM_KEY`` 的 sentinel:從 LATEST_STREAM_KEY 讀實際 key。
LATEST_SENTINEL = "@latest"


def bus_redis_url(env: Mapping[str, str] | None = None) -> str:
    """Nautilus bus(DB0)Redis URL,可由 ``REDIS_HOST`` / ``REDIS_PORT`` 覆寫。

    compose 內設為服務名(``redis``);未設時維持既有 localhost 開發流程。
    """
    env = os.environ if env is None else env
    host = env.get("REDIS_HOST", "localhost")
    port = env.get("REDIS_PORT", "6379")
    return f"redis://{host}:{port}/{REDIS_BUS_DB}"


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


def resolve_stream_key(
    env: Mapping[str, str] | None = None, *, client: Any = None
) -> str | None:
    """解析 API 要消費的 Nautilus stream key。

    - ``JIMQ_STREAM_KEY`` 未設 → None(WS 端點仍可用,等灌入)。
    - 字面值 → 直接用該 key。
    - sentinel ``@latest`` → 從 Redis 的 ``LATEST_STREAM_KEY`` 讀 engine 最近一次
      backtest 寫入的實際 key;讀不到回 None。
    """
    env = os.environ if env is None else env
    configured = env.get("JIMQ_STREAM_KEY")
    if not configured:
        return None
    if configured != LATEST_SENTINEL:
        return configured
    if client is None:
        return None
    return _as_str(client.get(LATEST_STREAM_KEY))


def make_streaming_lifespan(
    *,
    stream_key: str,
    redis_url: str | None = None,
):
    """建一個啟動 hub + Redis consumer task 的 lifespan。

    ``redis_url`` 預設讀環境變數(``REDIS_HOST`` / ``REDIS_PORT``;compose 內為
    服務名),維持 localhost 開發流程。
    """
    if redis_url is None:
        redis_url = bus_redis_url()

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


def make_hotreload_lifespan(
    *,
    redis_url: str | None = None,
    client: Any = None,
    poll_interval: float = 1.0,
):
    """@latest 模式 lifespan:用 ConsumerSupervisor 熱重載 consumer。

    監看 ``LATEST_STREAM_KEY``:engine(make live/paper/exp)後起寫新 key 時,
    自動停舊 consumer、``hub.clear()``、起新 consumer,免手動 ``make reload``。

    ``client`` 可注入(測試用);未注入時連 localhost DB0 bus。app.state 掛上
    ``hub`` / ``consumer_supervisor`` / ``consumer_supervisor_task`` 供關閉與測試。
    """
    if redis_url is None:
        redis_url = bus_redis_url()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        hub = Hub()
        app.state.hub = hub
        owns_client = client is None
        redis_client = aioredis.from_url(redis_url) if owns_client else client
        supervisor = ConsumerSupervisor(
            client=redis_client,
            hub=hub,
            consumer_factory=run_consumer,
            poll_interval=poll_interval,
            latest_key=LATEST_STREAM_KEY,
        )
        app.state.consumer_supervisor = supervisor
        task = asyncio.create_task(supervisor.run())
        app.state.consumer_supervisor_task = task
        try:
            yield
        finally:
            await supervisor.stop()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            if owns_client:
                await redis_client.aclose()
            else:
                # 注入的 client 由呼叫端管理生命週期;若有 aclose 仍禮貌關閉。
                aclose = getattr(redis_client, "aclose", None)
                if aclose is not None:
                    await aclose()

    return lifespan


def build_streaming_app(
    *,
    stream_key: str,
    redis_url: str | None = None,
) -> FastAPI:
    """建一個只含 WS gateway + 串流 lifespan 的精簡 app(e2e / 部署用)。"""
    app = FastAPI(lifespan=make_streaming_lifespan(stream_key=stream_key, redis_url=redis_url))
    register_ws(app)
    return app
