"""卡 #10 — consumer 啟動先排空既有 backlog 再進 live(行為測試)。

全棧 demo 中 engine 一次性 job 先把整段 backtest 事件寫進 stream,API 才(重)
啟動。若 consumer 只讀 ``>``(新訊息),重啟後讀不到任何 backlog,hub 快照為空、
前端看不到資料。期望行為:``run_consumer`` 啟動時先以 ``id="0"`` 排空尚未處理的
歷史 entry(逐筆 normalize→publish→ack),排空後再切換到 ``>`` 跟 live。

只驗 public interface(publish 收到哪些信封),不驗實作細節。
"""

from __future__ import annotations

import asyncio

import msgspec
import pytest

from app.services.nautilus_consumer import run_consumer


def _entry(entry_id: str, topic: str, payload: dict):
    return (
        entry_id.encode(),
        {b"topic": topic.encode(), b"payload": msgspec.msgpack.encode(payload)},
    )


class FakeBacklogRedis:
    """模擬一個已存在 group、且有未處理 backlog 的 stream。

    - ``xreadgroup(..., {key: '0'})``:回 backlog(pending/未 ack 的歷史),
      一次給完後第二次回空(模擬排空)。
    - ``xreadgroup(..., {key: '>'})``:回空(無新 live;讓 loop 在 stop 後退出)。
    """

    def __init__(self, key: str, backlog: list):
        self.key = key
        self._backlog = backlog
        self._gave_backlog = False
        self.acked: list[bytes] = []

    async def xgroup_create(self, *a, **k):
        return True

    async def xreadgroup(self, group, consumer, streams, count=100, block=1000):
        read_id = streams[self.key]
        if read_id == "0":
            if not self._gave_backlog:
                self._gave_backlog = True
                return [(self.key.encode(), list(self._backlog))]
            return []  # backlog 已排空
        # '>' live:無新訊息。
        await asyncio.sleep(0)
        return []

    async def xack(self, key, group, entry_id):
        self.acked.append(entry_id)


@pytest.mark.asyncio
async def test_consumer_drains_existing_backlog_on_start():
    key = "trader-X:abc:stream"
    backlog = [
        _entry("1-0", "data.bars.BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
               {"type": "Bar", "open": "1", "high": "1", "low": "1", "close": "1",
                "volume": "1", "ts_event": "1", "ts_init": "1"}),
        _entry("2-0", "events.fills.BTCUSDT-PERP.BINANCE",
               {"type": "OrderFilled", "instrument_id": "BTCUSDT-PERP.BINANCE"}),
        _entry("3-0", "events.position.EMACross-000",
               {"type": "PositionOpened", "position_id": "P-1"}),
    ]
    client = FakeBacklogRedis(key, backlog)

    seen: list[dict] = []

    async def publish(env):
        seen.append(env)

    stop = asyncio.Event()

    async def runner():
        await run_consumer(client, key, publish, stop_event=stop, block_ms=10)

    task = asyncio.create_task(runner())
    # 給 consumer 排空 backlog 的時間,然後停。
    for _ in range(50):
        if len(seen) >= 3:
            break
        await asyncio.sleep(0.01)
    stop.set()
    await asyncio.wait_for(task, timeout=2)

    channels = [e["channel"] for e in seen]
    assert "bars" in channels
    assert "fills" in channels
    assert "positions" in channels
    # backlog 三筆都 ack。
    assert len(client.acked) >= 3
