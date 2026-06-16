"""JimQ FastAPI entrypoint.

Stripped fork of boilerplate v0.15.0 ``main.py``: removed crudadmin mount and
admin lifespan. Wires the resource/health router + settings, and (卡 #7) mounts
the WebSocket streaming gateway with a composed lifespan that — alongside the
boilerplate Redis-cache lifespan — creates the in-process hub and starts the
Nautilus consumer reading the Redis Streams bus (localhost DB0). In ``@latest``
mode a ConsumerSupervisor hot-reloads the consumer when the engine writes a new
stream key (no ``make reload`` needed); a literal ``JIMQ_STREAM_KEY`` pins one
stream as before.
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router
from .core.config import settings
from .core.setup import create_application, lifespan_factory
from .services.hub import Hub
from .ws.app_factory import (
    LATEST_SENTINEL,
    make_multiscope_lifespan,
    make_streaming_lifespan,
)
from .ws.stream import register_ws

logger = logging.getLogger(__name__)


def _composed_lifespan():
    """Boilerplate cache lifespan + 串流(hub + 選用 consumer)lifespan。"""
    boilerplate = lifespan_factory(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        async with boilerplate(app):
            configured = os.environ.get("JIMQ_STREAM_KEY")
            if configured == LATEST_SENTINEL:
                # @latest 模式(卡 A):雙 scope 並行消費 —— live 與 backtest 各自
                # Hub + ConsumerSupervisor,各 watch 自己的 latest-key。一跑 backtest
                # 只切 backtest hub,Live 圖不再混入 backtest 事件;engine 後起寫
                # 對應 scope 的 key 即自動接上,免 make reload。
                logger.info("串流 consumer 雙 scope 熱重載模式啟動(live + backtest)")
                multiscope = make_multiscope_lifespan()
                async with multiscope(app):
                    yield
            elif configured:
                # 字面 key 模式:釘死該 key,維持原本單一 consumer(不監看)。
                logger.info("串流 consumer 啟動,stream key = %s", configured)
                streaming = make_streaming_lifespan(stream_key=configured)
                async with streaming(app):
                    yield
            else:
                # 無 stream key:仍建 hub 讓 WS 端點可用(等未來灌入)。
                logger.info("未設 JIMQ_STREAM_KEY;僅啟用空 hub")
                app.state.hub = Hub()
                yield

    return lifespan


app = create_application(router=router, settings=settings, lifespan=_composed_lifespan())
register_ws(app)
