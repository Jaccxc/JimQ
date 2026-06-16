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
    LATEST_STREAM_KEY,
    make_hotreload_lifespan,
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
                # @latest 模式:用 supervisor 監看 LATEST_STREAM_KEY 熱重載,
                # engine(make live/paper/exp)後起寫新 key 即自動接上,免 make reload。
                logger.info("串流 consumer 熱重載模式啟動(監看 %s)", LATEST_STREAM_KEY)
                hotreload = make_hotreload_lifespan()
                async with hotreload(app):
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
