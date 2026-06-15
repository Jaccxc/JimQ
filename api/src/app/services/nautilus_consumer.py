"""卡 #7 — Nautilus Redis Streams consumer → 正規化 DTO 信封。

職責:
1. ``StreamNormalizer``:把一筆 Nautilus stream entry(``topic`` + msgpack
   ``payload``)反序列化並正規化為 jimq_core DTO 信封 ``{channel, seq, data}``。
   channel 依 topic 前綴映射;未知/被 filter 的 topic 安全略過(回 None)。
   seq 由 normalizer 單調遞增,只給真正發出的信封。
2. ``run_consumer``:lifespan 啟動的 asyncio task,以 ``XREADGROUP`` 非阻塞讀
   Nautilus 寫在 Redis Streams DB0(bus)的聚合 stream,逐筆 normalize 後
   publish 到 in-process hub。

設計(本地決策):
- **stream 格式**沿用 #5:單一聚合 stream key,每筆 entry 兩個 field
  ``topic``(str)與 ``payload``(msgpack dict,帶 ``type``)。
- **channel 映射**(topic 前綴 → channel):
  ``data.bars.`` → bars、``events.order.`` → orders、``events.fills.`` → fills、
  ``events.position.`` → positions、``events.account.`` → pnl。其餘略過。
- **seq 來源**:consumer 端單調整數,從 1 起,每發出一個信封 +1。被略過的
  entry 不消耗 seq(gapless 給 last_seq 補洞用)。
- 只連 localhost DB0(bus),read 路徑非阻塞(asyncio + XREADGROUP block)。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping, Sequence

import msgspec

from jimq_core.schemas import bar_event_data

logger = logging.getLogger(__name__)

# topic 前綴 → 對外 channel 名稱。順序不重要(前綴互斥)。
_TOPIC_PREFIX_TO_CHANNEL: tuple[tuple[str, str], ...] = (
    ("data.bars.", "bars"),
    ("events.order.", "orders"),
    ("events.fills.", "fills"),
    ("events.position.", "positions"),
    ("events.account.", "pnl"),
)


def _decode(v: Any) -> Any:
    return v.decode() if isinstance(v, (bytes, bytearray)) else v


def _channel_for_topic(topic: str) -> str | None:
    """topic 前綴 → channel;未知回 None。"""
    for prefix, channel in _TOPIC_PREFIX_TO_CHANNEL:
        if topic.startswith(prefix):
            return channel
    return None


def _normalize_data(channel: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """依 channel 把 Nautilus payload 正規化為前端友善 data。

    bars 沿用 BarDTO 風格(time epoch 秒 + OHLCV 字串);其餘事件目前直接帶
    Nautilus payload(已是純量 dict),保留 ``type`` 供 client 分辨子型別。
    """
    data = dict(payload)
    if channel == "bars":
        data.update(bar_event_data(payload))
    return data


class StreamNormalizer:
    """把 Nautilus stream entry 正規化為 ``{channel, seq, data}`` 信封。

    有狀態:持有單調 seq 計數器(每發出一個信封 +1)。
    """

    def __init__(self, *, start_seq: int = 0) -> None:
        self._seq = start_seq

    def normalize_entry(
        self, entry: tuple[Any, Mapping[Any, Any]]
    ) -> dict[str, Any] | None:
        """正規化單筆 stream entry。未知/被 filter 的 topic 回 None。"""
        _entry_id, fields = entry
        fields = {_decode(k): v for k, v in fields.items()}
        topic = _decode(fields.get("topic"))
        if topic is None:
            return None
        channel = _channel_for_topic(topic)
        if channel is None:
            return None  # 未知/被 filter 型別,安全略過,不消耗 seq。

        raw_payload = fields.get("payload")
        try:
            payload = msgspec.msgpack.decode(raw_payload)
        except (msgspec.DecodeError, TypeError, ValueError):
            logger.warning("無法反序列化 payload(topic=%s),略過", topic)
            return None
        if not isinstance(payload, dict):
            return None

        self._seq += 1
        return {
            "channel": channel,
            "seq": self._seq,
            "data": _normalize_data(channel, payload),
        }


# --- consumer task(lifespan 啟動)------------------------------------------

# Redis consumer group / consumer 名稱(本卡固定;多 worker 時 consumer 名可帶 pid)。
CONSUMER_GROUP = "jimq-api"
CONSUMER_NAME = "consumer-1"


async def _ensure_group(client: Any, stream_key: str, group: str) -> None:
    """建立 consumer group(從頭 ``0`` 讀;已存在則忽略)。"""
    try:
        await client.xgroup_create(stream_key, group, id="0", mkstream=True)
    except Exception as exc:  # noqa: BLE001 — BUSYGROUP = 已存在,正常。
        if "BUSYGROUP" not in str(exc):
            raise


async def run_consumer(
    client: Any,
    stream_key: str,
    publish: Any,
    *,
    group: str = CONSUMER_GROUP,
    consumer: str = CONSUMER_NAME,
    block_ms: int = 1000,
    count: int = 100,
    stop_event: asyncio.Event | None = None,
) -> None:
    """非阻塞 consumer loop:XREADGROUP → normalize → publish 到 hub。

    ``publish`` 為協程函式 ``async (envelope) -> None``(通常是 ``hub.publish``)。
    讀 localhost DB0 bus;``stop_event`` set 時優雅退出。
    """
    normalizer = StreamNormalizer()
    await _ensure_group(client, stream_key, group)
    while stop_event is None or not stop_event.is_set():
        try:
            resp: Sequence[Any] = await client.xreadgroup(
                group, consumer, {stream_key: ">"}, count=count, block=block_ms
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("XREADGROUP 失敗;短暫退避後重試")
            await asyncio.sleep(0.5)
            continue
        if not resp:
            continue
        for _key, entries in resp:
            for entry in entries:
                env = normalizer.normalize_entry(entry)
                entry_id = entry[0]
                if env is not None:
                    await publish(env)
                # ack 不論是否發出(被 filter 的也算已處理)。
                try:
                    await client.xack(stream_key, group, entry_id)
                except Exception:  # noqa: BLE001
                    logger.debug("xack 失敗(entry=%s)", entry_id)
