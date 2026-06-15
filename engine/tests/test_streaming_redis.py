"""卡 #5 — backtest 事件落地本機 Redis Streams 整合測試。

驗收(行為,不驗實作細節):
- 啟用 streaming MessageBus 設定跑小型 backtest 後,事件序列化寫入本機
  Redis Streams(REDIS_BUS_DB=0)。
- stream key = trader:{trader_id}:{instance_id}:{streams_prefix},可由外部
  redis-cli/redis-py XRANGE/XLEN 取得。
- 序列化(msgpack/json)可被下游反序列化,關鍵欄位(type/topic/payload)可讀。
- 預期事件序列出現 bar / order / fill / position 類型。

需要本機 docker redis(DB0)。測完清掉測試用 stream key 避免污染。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from jimq_engine.catalog.ingest import BAR_TYPE_1M, ingest_bars, query_bars
from jimq_engine.catalog.instruments import (
    BTCUSDT_PERP_BINANCE_ID,
    btcusdt_perp_binance,
)
from jimq_engine.strategies.ema_cross import EMACrossConfig
from jimq_engine.streaming.redis_bus import (
    build_streaming_engine,
    stream_key_for,
)
from jimq_core.constants import REDIS_BUS_DB

redis = pytest.importorskip("redis")

_BASE_MS = 1_700_000_000_000


def _redis_client():
    try:
        c = redis.Redis(host="localhost", port=6379, db=REDIS_BUS_DB)
        c.ping()
    except Exception:  # noqa: BLE001
        pytest.skip("本機 Redis(localhost:6379)未啟動,跳過串流整合測試")
    return c


def _golden_cross_klines() -> list[list]:
    down = [40000.0 - i * 20 for i in range(15)]
    up = [down[-1] + i * 120 for i in range(1, 20)]
    prices = down + up
    out = []
    for i, p in enumerate(prices):
        ot = _BASE_MS + i * 60_000
        out.append(
            [ot, f"{p}", f"{p + 5}", f"{p - 5}", f"{p}", "10.000",
             ot + 59_999, "0", 1, "0", "0", "0"]
        )
    return out


def _config():
    return EMACrossConfig(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        bar_type=BAR_TYPE_1M,
        fast_period=3,
        slow_period=8,
        trade_size=Decimal("0.100"),
        sl_pct=Decimal("0.01"),
        tp_pct=Decimal("0.02"),
    )


@pytest.fixture()
def ran_engine(tmp_path):
    from nautilus_trader.persistence.catalog import ParquetDataCatalog

    client = _redis_client()
    catalog = ParquetDataCatalog(path=str(tmp_path / "catalog"))
    instrument = btcusdt_perp_binance()
    catalog.write_data([instrument])
    ingest_bars(catalog, _golden_cross_klines(), instrument)
    bars = query_bars(catalog, bar_type=BAR_TYPE_1M)

    engine = build_streaming_engine(instrument, bars, _config())
    key = stream_key_for(engine)
    # Redis 寫入走獨立 Rust MPSC 執行緒;短輪詢等待 flush 落地避免時序 flake。
    import time

    for _ in range(50):
        if client.exists(key) and client.xlen(key) > 0:
            break
        time.sleep(0.05)
    try:
        yield engine, client, key
    finally:
        # 先 dispose 讓 Rust MPSC 寫入執行緒 drain 完,再刪 key,否則殘餘
        # flush 會在刪除後重建 key 造成 stream 污染。
        engine.dispose()
        import time

        time.sleep(0.2)
        client.delete(key)
        client.close()


def _entries(client, key):
    return client.xrange(key)


def test_stream_has_events(ran_engine):
    """跑完 backtest 後 stream key 存在且 XLEN > 0。"""
    _engine, client, key = ran_engine
    assert client.exists(key), f"stream key 不存在:{key}"
    assert client.xlen(key) > 0, "stream 應有事件"


def test_stream_key_structure(ran_engine):
    """stream key = trader-{trader_id}:{instance_id}:{prefix}。"""
    engine, _client, key = ran_engine
    assert key == f"trader-{engine.trader_id}:{engine.instance_id}:stream"


def _decode(v):
    return v.decode() if isinstance(v, bytes) else v


def _topic_payload_pairs(entries):
    """Nautilus stream entry 每筆有 ``topic`` 與 ``payload`` 兩個 field。"""
    for _id, fields in entries:
        fields = {_decode(k): v for k, v in fields.items()}
        yield _decode(fields["topic"]), fields["payload"]


def test_events_deserialize_and_cover_lifecycle(ran_engine):
    """每筆 entry 可反序列化(msgpack),且涵蓋 bar/order/fill/position 類型。"""
    import msgspec

    _engine, client, key = ran_engine
    entries = _entries(client, key)
    assert entries, "應有 stream entries"

    topics: list[str] = []
    types: list[str] = []
    for topic, raw_payload in _topic_payload_pairs(entries):
        topics.append(topic)
        obj = msgspec.msgpack.decode(raw_payload)
        assert isinstance(obj, dict)
        assert "type" in obj, f"payload 缺 type:{obj!r}"
        types.append(obj["type"])

    topic_blob = " ".join(topics).lower()
    type_blob = " ".join(types)
    assert "order" in topic_blob, f"缺 order 事件;topics={sorted(set(topics))}"
    assert "position" in topic_blob, f"缺 position 事件;topics={sorted(set(topics))}"
    assert "data.bar" in topic_blob or "bar" in topic_blob, (
        f"缺 bar 事件;topics={sorted(set(topics))}"
    )
    # 成交事件關鍵欄位可反序列化(下游 #7 consumer 依賴)。
    assert "OrderFilled" in type_blob, f"缺 OrderFilled;types={sorted(set(types))}"


def test_high_frequency_types_excluded(ran_engine):
    """types_filter 排除 QuoteTick/TradeTick:stream 不應出現 quote/trade tick。"""
    import msgspec

    _engine, client, key = ran_engine
    types = []
    for _topic, raw_payload in _topic_payload_pairs(_entries(client, key)):
        types.append(msgspec.msgpack.decode(raw_payload).get("type", ""))
    assert "QuoteTick" not in types, "QuoteTick 應被 types_filter 排除"
    assert "TradeTick" not in types, "TradeTick 應被 types_filter 排除"
