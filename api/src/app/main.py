"""JimQ FastAPI entrypoint.

Stripped fork of boilerplate v0.15.0 ``main.py``: removed crudadmin mount and
admin lifespan. Wires the resource/health router + settings, and (卡 #7) mounts
the WebSocket streaming gateway with a composed lifespan that — alongside the
boilerplate Redis-cache lifespan — creates the in-process hub and, when a
Nautilus stream key is configured (``JIMQ_STREAM_KEY``), starts the consumer
task reading the Redis Streams bus (localhost DB0).
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router
from .core.config import settings
from .core.setup import create_application, lifespan_factory
from .services.hub import Hub
from .ws.app_factory import make_streaming_lifespan
from .ws.stream import register_ws


def _composed_lifespan():
    """Boilerplate cache lifespan + 串流(hub + 選用 consumer)lifespan。"""
    boilerplate = lifespan_factory(settings)
    stream_key = os.environ.get("JIMQ_STREAM_KEY")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        async with boilerplate(app):
            if stream_key:
                streaming = make_streaming_lifespan(stream_key=stream_key)
                async with streaming(app):
                    yield
            else:
                # 無 stream key:仍建 hub 讓 WS 端點可用(等未來灌入)。
                app.state.hub = Hub()
                yield

    return lifespan


app = create_application(router=router, settings=settings, lifespan=_composed_lifespan())
register_ws(app)
