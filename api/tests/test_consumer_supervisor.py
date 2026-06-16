"""API consumer 熱重載 — ConsumerSupervisor 行為測試(非 gated)。

問題:api 在 lifespan 啟動時一次性解析 ``@latest``,consumer 綁死該 key,
engine 後起寫的新 key 不被認得 → 圖空白、需 ``make reload`` 重啟 api。

期望行為(只驗 public interface,不驗實作細節):
- ``LATEST_STREAM_KEY`` 從空→streamA:supervisor 起 consumer 消費 A,資料進 hub。
- 改成 streamB:supervisor 停 A、clear hub、起 B,之後只收到 B(不混 A 殘留)。
- key 被刪:supervisor 停 consumer + clear hub,hub 快照空且不崩,續輪詢等下一個 key。

用可控 sleep(asyncio 推進)+ 真 ``run_consumer`` 對 FakeBacklogStreamRedis,
測試快且確定性,不真等秒數。
"""

from __future__ import annotations

import asyncio

import msgspec
import pytest

from app.services.hub import Hub
from app.services.nautilus_consumer import run_consumer
from app.services.consumer_supervisor import ConsumerSupervisor
from app.ws.app_factory import LATEST_STREAM_KEY


def _entry(entry_id: str, topic: str, payload: dict):
    return (
        entry_id.encode(),
        {b"topic": topic.encode(), b"payload": msgspec.msgpack.encode(payload)},
    )


def _bar_entry(entry_id: str, close: str):
    return _entry(
        entry_id,
        "data.bars.BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        {
            "type": "Bar",
            "open": close, "high": close, "low": close, "close": close,
            "volume": "1", "ts_event": "1700000000000000000",
            "ts_init": "1700000000000000000",
        },
    )


class FakeBacklogStreamRedis:
    """多 stream + 可變 LATEST_STREAM_KEY 的 fake。

    - ``get(LATEST_STREAM_KEY)``:回目前指向的 stream key(或 None)。
    - ``xgroup_create`` / ``xack``:no-op 記帳。
    - ``xreadgroup(.., {key: '0'})``:回該 stream 的 backlog(一次給完,之後空)。
    - ``xreadgroup(.., {key: '>'})``:回空(live 無新訊息)。

    供測試用 ``set_latest`` 切換 LATEST_STREAM_KEY 指向。
    """

    def __init__(self, streams: dict[str, list]):
        self._streams = streams
        self._latest: str | None = None
        self._gave: dict[str, bool] = {}
        self.acked: list[bytes] = []

    # --- LATEST_STREAM_KEY 輪詢面 ---
    def set_latest(self, key: str | None) -> None:
        self._latest = key

    async def get(self, key):
        assert key == LATEST_STREAM_KEY
        return None if self._latest is None else self._latest.encode()

    # --- consumer 面 ---
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

    async def xack(self, key, group, entry_id):
        self.acked.append(entry_id)


class ImmediateSleep:
    """可控 sleep:不真等;記錄呼叫次數,並讓出 event loop 一次。

    supervisor 用它輪詢間隔;測試靠 ``advance``/實際 task 推進確定性收斂。
    """

    def __init__(self):
        self.calls = 0

    async def __call__(self, _seconds):
        self.calls += 1
        await asyncio.sleep(0)


async def _wait_for(pred, *, tries=500):
    for _ in range(tries):
        if pred():
            return True
        await asyncio.sleep(0.001)
    return False


@pytest.mark.asyncio
async def test_supervisor_starts_consumer_when_key_appears():
    """LATEST_STREAM_KEY 從空→streamA:supervisor 起 consumer,資料進 hub。"""
    client = FakeBacklogStreamRedis({"streamA": [_bar_entry("1-0", "111")]})
    hub = Hub()
    sup = ConsumerSupervisor(
        client=client, hub=hub, consumer_factory=run_consumer,
        poll_interval=0.0, sleep=ImmediateSleep(),
    )
    task = asyncio.create_task(sup.run())
    # 先沒 key:hub 應保持空。
    await asyncio.sleep(0.01)
    assert hub.snapshot({"bars"}) == []

    client.set_latest("streamA")
    assert await _wait_for(lambda: len(hub.snapshot({"bars"})) >= 1)
    assert [e["data"]["close"] for e in hub.snapshot({"bars"})] == ["111"]

    await sup.stop()
    await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_supervisor_switches_stream_and_clears_residue():
    """改成 streamB:停 A、clear hub、起 B,之後只收到 B(不混 A 殘留)。"""
    client = FakeBacklogStreamRedis({
        "streamA": [_bar_entry("1-0", "111")],
        "streamB": [_bar_entry("1-0", "222")],
    })
    hub = Hub()
    sup = ConsumerSupervisor(
        client=client, hub=hub, consumer_factory=run_consumer,
        poll_interval=0.0, sleep=ImmediateSleep(),
    )
    task = asyncio.create_task(sup.run())

    client.set_latest("streamA")
    assert await _wait_for(lambda: any(
        e["data"]["close"] == "111" for e in hub.snapshot({"bars"})
    ))

    client.set_latest("streamB")
    # 換 run 後快照只剩 B 的 bar,A 的殘留被 clear。
    assert await _wait_for(lambda: hub.snapshot({"bars"}) and all(
        e["data"]["close"] == "222" for e in hub.snapshot({"bars"})
    ))
    closes = [e["data"]["close"] for e in hub.snapshot({"bars"})]
    assert "111" not in closes
    assert closes == ["222"]

    await sup.stop()
    await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_supervisor_stops_and_clears_when_key_deleted():
    """key 被刪(engine 停):停 consumer + clear hub,快照空且不崩,續輪詢。"""
    client = FakeBacklogStreamRedis({"streamA": [_bar_entry("1-0", "111")]})
    hub = Hub()
    sup = ConsumerSupervisor(
        client=client, hub=hub, consumer_factory=run_consumer,
        poll_interval=0.0, sleep=ImmediateSleep(),
    )
    task = asyncio.create_task(sup.run())

    client.set_latest("streamA")
    assert await _wait_for(lambda: len(hub.snapshot({"bars"})) >= 1)

    client.set_latest(None)  # engine 停,key 被刪。
    assert await _wait_for(lambda: hub.snapshot({"bars"}) == [])

    # supervisor 仍活著輪詢,沒崩 → 還能再接下一個 key。
    assert not task.done()

    await sup.stop()
    await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_supervisor_clean_shutdown_cancels_child_consumer():
    """stop() 乾淨關閉:supervisor 與 child consumer 都收尾,task 正常結束。"""
    client = FakeBacklogStreamRedis({"streamA": [_bar_entry("1-0", "111")]})
    hub = Hub()
    sup = ConsumerSupervisor(
        client=client, hub=hub, consumer_factory=run_consumer,
        poll_interval=0.0, sleep=ImmediateSleep(),
    )
    task = asyncio.create_task(sup.run())
    client.set_latest("streamA")
    assert await _wait_for(lambda: len(hub.snapshot({"bars"})) >= 1)

    await sup.stop()
    await asyncio.wait_for(task, timeout=2)
    assert task.done() and not task.cancelled()


@pytest.mark.asyncio
async def test_supervisor_stop_interrupts_long_poll_interval():
    """stop() 在長輪詢間隔中也能立即關閉,不空等整個間隔(真 asyncio.sleep)。"""
    client = FakeBacklogStreamRedis({"streamA": [_bar_entry("1-0", "111")]})
    hub = Hub()
    # 故意給很長的真 sleep(預設 asyncio.sleep);若關閉不中斷睡眠就會 timeout。
    sup = ConsumerSupervisor(
        client=client, hub=hub, consumer_factory=run_consumer,
        poll_interval=30.0,
    )
    task = asyncio.create_task(sup.run())
    client.set_latest("streamA")
    assert await _wait_for(lambda: len(hub.snapshot({"bars"})) >= 1)

    await sup.stop()
    # 若 stop 沒中斷 30s 睡眠,這會 timeout。
    await asyncio.wait_for(task, timeout=2)
