"""API consumer 熱重載 — ConsumerSupervisor。

問題:api 在 lifespan 啟動時**一次性**解析 ``JIMQ_STREAM_KEY=@latest``(讀
``LATEST_STREAM_KEY`` 得實際 key),consumer task 綁死該 key,之後不再監看 →
engine 後起寫的新 key 不被認得,圖空白、需手動 ``make reload``(restart api)。

解法:一個 async supervisor task,**只在 @latest 模式啟動**(字面 key 模式維持
釘死、不監看)。它輪詢 ``LATEST_STREAM_KEY``,當解析到的 key 與「目前正在消費的
key」不同時(無→有 / A→B / 有→無):停掉當前 consumer、``hub.clear()``、若新 key
非空再以新 key 起一個新 consumer。全程非阻塞;lifespan 結束時乾淨關閉。

可測:依賴(redis client / hub / consumer factory / sleep)全注入,邏輯不埋進
lifespan。``run`` 是 supervisor loop,``stop`` 觸發乾淨關閉。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from .hub import Hub

logger = logging.getLogger(__name__)

# engine 寫實際 stream key 的已知 Redis key(與 app_factory.LATEST_STREAM_KEY 同值;
# 此處本地定義避免 services→ws 反向 import 造成循環)。可由建構子覆寫。
LATEST_STREAM_KEY = "jimq:latest_stream_key"

# consumer factory:(client, stream_key, publish, *, stop_event) -> coroutine。
# 預設由呼叫端注入 ``run_consumer``(其簽名相容)。
ConsumerFactory = Callable[..., Awaitable[None]]
SleepFn = Callable[[float], Awaitable[None]]

# 預設輪詢間隔(秒)。可被 stop_event 經 sleep 中斷(此處用 asyncio.sleep)。
DEFAULT_POLL_INTERVAL = 1.0


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


class ConsumerSupervisor:
    """監看 ``LATEST_STREAM_KEY`` 變更並熱重載 Nautilus consumer。

    當前 key 變更時:停當前 consumer(set stop_event + await 收尾)→ ``hub.clear()``
    → 若新 key 非空則起新 consumer。全程非阻塞;``stop()`` 乾淨關閉(child consumer
    也 cancel/await)。
    """

    def __init__(
        self,
        *,
        client: Any,
        hub: Hub,
        consumer_factory: ConsumerFactory,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        sleep: SleepFn | None = None,
        latest_key: str = LATEST_STREAM_KEY,
    ) -> None:
        self._client = client
        self._hub = hub
        self._consumer_factory = consumer_factory
        self._poll_interval = poll_interval
        self._latest_key = latest_key
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        self._stop = asyncio.Event()
        # 目前正在消費的 key 與其 consumer task / stop event。
        self._current_key: str | None = None
        self._child_task: asyncio.Task | None = None
        self._child_stop: asyncio.Event | None = None

    async def _read_latest(self) -> str | None:
        """讀 LATEST_STREAM_KEY;讀失敗視為「無 key」(不崩 supervisor)。"""
        try:
            return _as_str(await self._client.get(self._latest_key))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("讀 LATEST_STREAM_KEY 失敗;視為無 key")
            return None

    async def _stop_child(self) -> None:
        """停當前 consumer:set stop_event → cancel → await 收尾。"""
        if self._child_task is None:
            return
        if self._child_stop is not None:
            self._child_stop.set()
        self._child_task.cancel()
        try:
            await self._child_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        self._child_task = None
        self._child_stop = None
        self._current_key = None

    def _start_child(self, key: str) -> None:
        """以 ``key`` 起新 consumer task。"""
        stop = asyncio.Event()
        task = asyncio.create_task(
            self._consumer_factory(
                self._client, key, self._hub.publish, stop_event=stop
            )
        )
        self._child_stop = stop
        self._child_task = task
        self._current_key = key

    async def _reconcile(self, latest: str | None) -> None:
        """把實際消費中的 key 對齊到 ``latest``(熱重載核心)。"""
        if latest == self._current_key:
            return  # 無變更。
        # key 變了(無→有 / A→B / 有→無):停舊 → clear 快照 → 起新(若非空)。
        logger.info("stream key 變更:%s → %s;熱重載 consumer", self._current_key, latest)
        await self._stop_child()
        self._hub.clear()
        if latest:
            self._start_child(latest)

    async def _interruptible_sleep(self, seconds: float) -> None:
        """睡 ``seconds`` 但可被 stop 立即中斷(關閉時不空等整個輪詢間隔)。

        注入的 ``sleep`` 仍被呼叫(測試可控/計數);其結束或 stop 任一先發生即返回。
        """
        sleep_task = asyncio.ensure_future(self._sleep(seconds))
        stop_task = asyncio.ensure_future(self._stop.wait())
        try:
            await asyncio.wait(
                {sleep_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for t in (sleep_task, stop_task):
                if not t.done():
                    t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass

    async def run(self) -> None:
        """supervisor loop:輪詢 LATEST_STREAM_KEY,變更即熱重載。"""
        try:
            while not self._stop.is_set():
                latest = await self._read_latest()
                await self._reconcile(latest)
                if self._stop.is_set():
                    break
                await self._interruptible_sleep(self._poll_interval)
        finally:
            await self._stop_child()

    async def stop(self) -> None:
        """乾淨關閉:停輪詢並收尾 child consumer。"""
        self._stop.set()
