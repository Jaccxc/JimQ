"""API consumer 熱重載 — lifespan 接上 supervisor(行為測試,非 gated)。

@latest 模式:lifespan 用 ConsumerSupervisor(取代一次性解析+單一 consumer),
監看 LATEST_STREAM_KEY 熱重載;app.state 保留 supervisor/task 供測試/關閉。
字面 key 模式維持原本單一 consumer(回歸不變,另有既有 e2e 覆蓋)。

用注入 fake redis + 真 run_consumer 驗 lifespan 端到端:啟動→出現 key→消費,
切 key→換 stream + clear,離開 lifespan→乾淨關閉。
"""

from __future__ import annotations

import asyncio

import msgspec
import pytest
from fastapi import FastAPI

from app.services.hub import Hub
from app.ws.app_factory import LATEST_STREAM_KEY, make_hotreload_lifespan


def _bar_entry(entry_id: str, close: str):
    return (
        entry_id.encode(),
        {
            b"topic": b"data.bars.BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
            b"payload": msgspec.msgpack.encode({
                "type": "Bar",
                "open": close, "high": close, "low": close, "close": close,
                "volume": "1", "ts_event": "1700000000000000000",
                "ts_init": "1700000000000000000",
            }),
        },
    )


class FakeLatestRedis:
    def __init__(self, streams):
        self._streams = streams
        self._latest = None
        self._gave = {}
        self.closed = False

    def set_latest(self, key):
        self._latest = key

    async def get(self, key):
        assert key == LATEST_STREAM_KEY
        return None if self._latest is None else self._latest.encode()

    async def xgroup_create(self, *a, **k):
        return True

    async def xreadgroup(self, group, consumer, streams, count=100, block=1000):
        ((key, read_id),) = streams.items()
        if read_id == "0":
            if not self._gave.get(key):
                self._gave[key] = True
                return [(key.encode(), list(self._streams.get(key, [])))]
            return []
        await asyncio.sleep(0)
        return []

    async def xack(self, *a):
        return None

    async def aclose(self):
        self.closed = True


async def _wait_for(pred, *, tries=500):
    for _ in range(tries):
        if pred():
            return True
        await asyncio.sleep(0.001)
    return False


@pytest.mark.asyncio
async def test_hotreload_lifespan_switches_streams_and_closes_cleanly():
    client = FakeLatestRedis({
        "streamA": [_bar_entry("1-0", "111")],
        "streamB": [_bar_entry("1-0", "222")],
    })
    lifespan = make_hotreload_lifespan(client=client, poll_interval=0.0)
    app = FastAPI()

    async with lifespan(app):
        hub: Hub = app.state.hub
        assert app.state.consumer_supervisor is not None

        client.set_latest("streamA")
        assert await _wait_for(lambda: any(
            e["data"]["close"] == "111" for e in hub.snapshot({"bars"})
        ))

        client.set_latest("streamB")
        assert await _wait_for(lambda: hub.snapshot({"bars"}) and all(
            e["data"]["close"] == "222" for e in hub.snapshot({"bars"})
        ))

    # 離開 lifespan:supervisor task 收尾、redis client 關閉。
    assert app.state.consumer_supervisor_task.done()
    assert client.closed
