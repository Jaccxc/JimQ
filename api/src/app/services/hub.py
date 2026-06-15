"""卡 #7 — in-process pub/sub hub。

consumer 把正規化信封 ``{channel, seq, data}`` ``publish`` 到 hub;ws gateway 為
每條 WS 連線 ``subscribe`` 一組 channel,拿到一個**有界佇列**。hub 另保留:
- **快照狀態**:最近 bars(ring)、最新 pnl(last-value)、各 position 最新狀態、
  最近 orders/fills(ring),供新連線連上即推快照。
- **近期信封 ring**(依 seq):供 ``last_seq`` 重連補洞。

有界佇列溢出策略(本地決策):
- 預設 **drop-oldest**(滿了丟 queue 最舊一筆再塞新的)。
- ``coalesce_channels`` 指定的 channel(pnl/positions)用 **last-value-wins**:
  滿時把 queue 內同 channel 的舊信封換成新值,不增長 queue。

純 in-process、單 event loop;不跨行程。snapshot/backfill 為同步唯讀。
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable

Envelope = dict[str, Any]

# 預設快照 / 補洞容量(本地決策;bars 保留近 N 根,history 保留近 M 筆信封)。
DEFAULT_BARS_HISTORY = 500
DEFAULT_HISTORY = 2000
# 快照採 last-value-wins(只留最新)的 channel。
_LAST_VALUE_CHANNELS = frozenset({"pnl"})
# 快照採 per-key 最新(每個 key 留最新一筆)的 channel 與其 key 欄位。
_KEYED_CHANNELS = {"positions": "position_id"}
# 快照採 recent-ring 的 channel(保留近 N 筆,序保留)。
_RING_CHANNELS = frozenset({"bars", "orders", "fills"})


@dataclass(eq=False)
class Subscription:
    """一條 WS 連線的訂閱:一組 channel + 一個有界佇列。

    ``eq=False`` → 用 identity 比較/雜湊(每條連線一個訂閱物件)。
    """

    channels: frozenset[str]
    queue: asyncio.Queue
    coalesce_channels: frozenset[str] = field(default_factory=frozenset)

    def _coalesce_put(self, env: Envelope) -> None:
        """last-value-wins:把 queue 內同 channel 舊信封換成新值;否則 drop-oldest 塞入。"""
        channel = env["channel"]
        # 嘗試就地替換 queue 內同 channel 的最新一筆。
        buf = list(self.queue._queue)  # type: ignore[attr-defined]
        for i in range(len(buf) - 1, -1, -1):
            if buf[i]["channel"] == channel:
                buf[i] = env
                self.queue._queue = deque(buf)  # type: ignore[attr-defined]
                return
        # queue 內沒有同 channel → 一般有界塞入。
        self._bounded_put(env)

    def _bounded_put(self, env: Envelope) -> None:
        """drop-oldest:滿了先丟最舊一筆再塞新的。"""
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover
                pass
        try:
            self.queue.put_nowait(env)
        except asyncio.QueueFull:  # pragma: no cover
            pass

    def deliver(self, env: Envelope) -> None:
        if env["channel"] in self.coalesce_channels:
            self._coalesce_put(env)
        else:
            self._bounded_put(env)


class Hub:
    """in-process topic→subscriber 有界佇列 pub/sub + 快照 + last_seq 補洞。"""

    def __init__(
        self,
        *,
        bars_history: int = DEFAULT_BARS_HISTORY,
        history: int = DEFAULT_HISTORY,
    ) -> None:
        self._subs: set[Subscription] = set()
        self._history: deque[Envelope] = deque(maxlen=history)
        # 快照狀態。
        self._rings: dict[str, deque[Envelope]] = {
            ch: deque(maxlen=(bars_history if ch == "bars" else DEFAULT_BARS_HISTORY))
            for ch in _RING_CHANNELS
        }
        self._last_value: dict[str, Envelope] = {}  # channel → 最新信封(pnl)
        self._keyed: dict[str, dict[str, Envelope]] = {
            ch: {} for ch in _KEYED_CHANNELS
        }

    # --- 訂閱 ---------------------------------------------------------------
    def subscribe(
        self,
        channels: Iterable[str],
        *,
        maxsize: int = 256,
        coalesce_channels: Iterable[str] = (),
    ) -> Subscription:
        sub = Subscription(
            channels=frozenset(channels),
            queue=asyncio.Queue(maxsize=maxsize),
            coalesce_channels=frozenset(coalesce_channels),
        )
        self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        self._subs.discard(sub)

    # --- 發佈 ---------------------------------------------------------------
    async def publish(self, env: Envelope) -> None:
        self._record(env)
        channel = env["channel"]
        for sub in self._subs:
            if channel in sub.channels:
                sub.deliver(env)

    def _record(self, env: Envelope) -> None:
        """更新 history ring 與快照狀態。"""
        self._history.append(env)
        channel = env["channel"]
        if channel in _RING_CHANNELS:
            self._rings[channel].append(env)
        if channel in _LAST_VALUE_CHANNELS:
            self._last_value[channel] = env
        if channel in _KEYED_CHANNELS:
            key_field = _KEYED_CHANNELS[channel]
            key = str(env["data"].get(key_field, ""))
            self._keyed[channel][key] = env

    # --- 快照 ---------------------------------------------------------------
    def snapshot(self, channels: Iterable[str]) -> list[Envelope]:
        """回傳目前已知狀態的信封列表(供新連線連上即推)。"""
        wanted = set(channels)
        out: list[Envelope] = []
        for ch in _RING_CHANNELS:
            if ch in wanted:
                out.extend(self._rings[ch])
        for ch in _LAST_VALUE_CHANNELS:
            if ch in wanted and ch in self._last_value:
                out.append(self._last_value[ch])
        for ch in _KEYED_CHANNELS:
            if ch in wanted:
                out.extend(self._keyed[ch].values())
        return out

    # --- last_seq 補洞 ------------------------------------------------------
    def backfill_since(
        self, *, last_seq: int, channels: Iterable[str]
    ) -> list[Envelope]:
        """回補 ``(last_seq, latest]`` 缺口(只回訂閱的 channel,依 seq 排序)。"""
        wanted = set(channels)
        return [
            e
            for e in self._history
            if e["seq"] > last_seq and e["channel"] in wanted
        ]
