"""API consumer 熱重載 — 真 Redis e2e:@latest supervisor 自動切 stream。

證明真正的修復:engine 後起寫新 stream key 到 LATEST_STREAM_KEY 時,@latest 模式
的 API 自動切到新 stream(免 make reload)。

直接對本機 Redis(DB0)手寫兩個聚合 stream(沿用 #5 entry 格式:topic + msgpack
payload),並改寫 LATEST_STREAM_KEY 指向,驗 supervisor lifespan 端到端切換。

需本機 docker Redis(localhost:6379 DB0);無則跳過。api 套件本身不依賴 engine。
"""

from __future__ import annotations

import asyncio
import uuid

import msgspec
import pytest
from fastapi import FastAPI

redis = pytest.importorskip("redis")
import redis.asyncio as aioredis  # noqa: E402

from app.services.hub import Hub  # noqa: E402
from app.ws.app_factory import LATEST_STREAM_KEY, make_hotreload_lifespan  # noqa: E402


def _bar_fields(close: str) -> dict:
    return {
        "topic": "data.bars.BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        "payload": msgspec.msgpack.encode({
            "type": "Bar",
            "open": close, "high": close, "low": close, "close": close,
            "volume": "1", "ts_event": "1700000000000000000",
            "ts_init": "1700000000000000000",
        }),
    }


def _sync_client():
    try:
        c = redis.Redis(host="localhost", port=6379, db=0)
        c.ping()
    except Exception:  # noqa: BLE001
        pytest.skip("本機 Redis(localhost:6379)未啟動,跳過 hot-reload e2e")
    return c


async def _wait_for(pred, *, tries=600):
    for _ in range(tries):
        if pred():
            return True
        await asyncio.sleep(0.01)
    return False


@pytest.mark.asyncio
async def test_hotreload_switches_stream_on_latest_key_change_real_redis():
    sync = _sync_client()
    tag = uuid.uuid4().hex[:8]
    key_a = f"trader-A-{tag}:stream"
    key_b = f"trader-B-{tag}:stream"
    sync.xadd(key_a, _bar_fields("111"))
    sync.xadd(key_b, _bar_fields("222"))
    sync.delete(LATEST_STREAM_KEY)

    client = aioredis.from_url("redis://localhost:6379/0")
    lifespan = make_hotreload_lifespan(client=client, poll_interval=0.05)
    app = FastAPI()
    try:
        async with lifespan(app):
            hub: Hub = app.state.hub
            # 無 LATEST_STREAM_KEY:hub 保持空。
            await asyncio.sleep(0.1)
            assert hub.snapshot({"bars"}) == []

            # engine 先起 A。
            sync.set(LATEST_STREAM_KEY, key_a)
            assert await _wait_for(lambda: any(
                e["data"]["close"] == "111" for e in hub.snapshot({"bars"})
            )), "A 未被消費"

            # engine 換 run 寫 B:API 自動切,清 A 殘留。
            sync.set(LATEST_STREAM_KEY, key_b)
            assert await _wait_for(lambda: hub.snapshot({"bars"}) and all(
                e["data"]["close"] == "222" for e in hub.snapshot({"bars"})
            )), "未切到 B 或殘留 A"
            assert "111" not in [e["data"]["close"] for e in hub.snapshot({"bars"})]

            # engine 停(刪 key):停 consumer + clear,不崩。
            sync.delete(LATEST_STREAM_KEY)
            assert await _wait_for(lambda: hub.snapshot({"bars"}) == [])
    finally:
        for k in (key_a, key_b, LATEST_STREAM_KEY):
            sync.delete(k)
        sync.close()
