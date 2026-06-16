"""卡 #7 — consumer→hub 正規化轉換 deep module 測試。

行為級驗收(只驗 public interface,不驗實作細節):
- 給定 Nautilus stream entry(``topic`` + msgpack ``payload``),
  ``normalize_entry`` 反序列化並正規化為 DTO 信封 ``{channel, seq, data}``。
- channel 依 topic 前綴正確映射:
  data.bars.* → bars、events.order.* → orders、events.fills.* → fills、
  events.position.* → positions、events.account.* → pnl。
- 未知/被 filter 的 topic(events.system.*、data.instrument.*、events.cancels.*)
  安全略過(回 None),不丟例外。
- seq 由 consumer 單調遞增(同一 consumer 連續 normalize 遞增,不重複)。

payload 取自真實 #5 backtest stream(msgpack dict,帶 ``type`` 欄位)。
"""

from __future__ import annotations

import msgspec
import pytest

from app.services.nautilus_consumer import StreamNormalizer


def _entry(topic: str, payload: dict) -> tuple[bytes, dict[bytes, bytes]]:
    """組一筆 Nautilus stream entry(id, {topic, payload})。"""
    return (
        b"1700000000000-0",
        {b"topic": topic.encode(), b"payload": msgspec.msgpack.encode(payload)},
    )


# --- 真實 payload(取自 #5 backtest stream)---

BAR_PAYLOAD = {
    "type": "Bar",
    "bar_type": "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
    "open": "40000.0",
    "high": "40005.0",
    "low": "39995.0",
    "close": "40000.0",
    "volume": "10.000",
    "ts_event": "1700000000000000000",
    "ts_init": "1700000000000000000",
}

ORDER_FILLED_PAYLOAD = {
    "type": "OrderFilled",
    "trader_id": "BACKTESTER-001",
    "strategy_id": "EMACross-000",
    "instrument_id": "BTCUSDT-PERP.BINANCE",
    "client_order_id": "O-20231114-222920-001-000-1",
    "venue_order_id": "BINANCE-1-001",
    "account_id": "BINANCE-001",
    "trade_id": "T-9c541fd800ea6de1-069",
    "position_id": "BTCUSDT-PERP.BINANCE-EMACross-000",
    "order_side": "BUY",
    "order_type": "MARKET",
    "last_qty": "0.100",
    "last_px": "39960.0",
    "currency": "USDT",
    "commission": "1.59840000 USDT",
    "liquidity_side": "TAKER",
    "event_id": "33ad755c-4941-40e4-a6a9-90c580109251",
    "ts_event": "1700000960000000000",
    "ts_init": "1700000960000000000",
    "info": {},
    "reconciliation": False,
}

ORDER_INIT_PAYLOAD = {
    "type": "OrderInitialized",
    "trader_id": "BACKTESTER-001",
    "strategy_id": "EMACross-000",
    "instrument_id": "BTCUSDT-PERP.BINANCE",
    "client_order_id": "O-20231114-222920-001-000-1",
    "order_side": "BUY",
    "order_type": "MARKET",
    "quantity": "0.100",
    "time_in_force": "GTC",
    "event_id": "286131bc-2b7a-42ad-b5d3-35b67588eccb",
    "ts_init": "1700000960000000000",
    "ts_event": "1700000960000000000",
}

POSITION_OPENED_PAYLOAD = {
    "type": "PositionOpened",
    "trader_id": "BACKTESTER-001",
    "strategy_id": "EMACross-000",
    "instrument_id": "BTCUSDT-PERP.BINANCE",
    "position_id": "BTCUSDT-PERP.BINANCE-EMACross-000",
    "account_id": "BINANCE-001",
    "entry": "BUY",
    "side": "LONG",
    "signed_qty": 0.1,
    "quantity": "0.100",
    "last_px": "39960.0",
    "avg_px_open": 39960.0,
    "realized_pnl": "-1.59840000 USDT",
    "event_id": "55147b18-f84f-4dd5-a6f9-c531f2ba5c45",
    "ts_event": "1700000960000000000",
    "ts_init": "1700000960000000000",
}

ACCOUNT_STATE_PAYLOAD = {
    "type": "AccountState",
    "account_id": "BINANCE-001",
    "account_type": "MARGIN",
    "base_currency": "USDT",
    "balances": [
        {
            "type": "AccountBalance",
            "total": "1000000.00000000",
            "locked": "0.00000000",
            "free": "1000000.00000000",
            "currency": "USDT",
        }
    ],
    "margins": [],
    "reported": True,
    "info": {},
    "event_id": "630e8b84-0059-4a98-92f1-30548110168e",
    "ts_event": "1700000000000000000",
    "ts_init": "1700000000000000000",
}


# 卡 B(Live 次秒 tick)— Binance TradeTick 串流 payload(取自 nodes/live.py
# TradeTickSubscriberActor 訂閱、bus 序列化)。topic = data.trades.{venue}.{symbol}。
TRADE_TICK_PAYLOAD = {
    "type": "TradeTick",
    "instrument_id": "BTCUSDT-PERP.BINANCE",
    "price": "40001.5",
    "size": "0.010",
    "aggressor_side": "BUYER",
    "trade_id": "T-123",
    "ts_event": "1700000005000000000",
    "ts_init": "1700000005000000000",
}


@pytest.mark.parametrize(
    ("topic", "payload", "expected_channel"),
    [
        ("data.bars.BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL", BAR_PAYLOAD, "bars"),
        ("data.trades.BINANCE.BTCUSDT-PERP", TRADE_TICK_PAYLOAD, "trades"),
        ("events.order.EMACross-000", ORDER_INIT_PAYLOAD, "orders"),
        ("events.fills.BTCUSDT-PERP.BINANCE", ORDER_FILLED_PAYLOAD, "fills"),
        ("events.position.EMACross-000", POSITION_OPENED_PAYLOAD, "positions"),
        ("events.account.BINANCE-001", ACCOUNT_STATE_PAYLOAD, "pnl"),
    ],
)
def test_normalize_maps_topic_to_channel(topic, payload, expected_channel):
    """已知 topic 正規化為對應 channel 的信封 {channel, seq, data}。"""
    norm = StreamNormalizer()
    env = norm.normalize_entry(_entry(topic, payload))
    assert env is not None
    assert env["channel"] == expected_channel
    assert isinstance(env["seq"], int)
    assert env["data"]["type"] == payload["type"]


@pytest.mark.parametrize(
    "topic",
    [
        "events.system.DataEngine",
        "events.system.BINANCE",
        "data.instrument.BINANCE.BTCUSDT-PERP",
        "events.cancels.BTCUSDT-PERP.BINANCE",
    ],
)
def test_normalize_skips_unknown_topics(topic):
    """未知/被 filter 的 topic 安全略過(回 None,不丟例外)。"""
    norm = StreamNormalizer()
    env = norm.normalize_entry(_entry(topic, {"type": "ComponentStateChanged"}))
    assert env is None


def test_seq_is_monotonic_per_normalizer():
    """同一 normalizer 連續發出的信封 seq 單調遞增、不重複。"""
    norm = StreamNormalizer()
    seqs = []
    for _ in range(3):
        env = norm.normalize_entry(
            _entry("data.bars.X", BAR_PAYLOAD)
        )
        seqs.append(env["seq"])
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)


def test_skipped_entries_do_not_consume_seq():
    """被略過的 entry 不消耗 seq(seq 只給真正發出的信封)。"""
    norm = StreamNormalizer()
    first = norm.normalize_entry(_entry("data.bars.X", BAR_PAYLOAD))
    norm.normalize_entry(_entry("events.system.X", {"type": "ComponentStateChanged"}))
    second = norm.normalize_entry(_entry("data.bars.X", BAR_PAYLOAD))
    assert second["seq"] == first["seq"] + 1


def test_bar_data_carries_normalized_dto_fields():
    """bars channel 的 data 帶可供前端用的正規化欄位(time/ohlcv)。"""
    norm = StreamNormalizer()
    env = norm.normalize_entry(
        _entry("data.bars.BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL", BAR_PAYLOAD)
    )
    data = env["data"]
    # 沿用 BarDTO 風格:time(epoch 秒)+ OHLCV 字串保留精度。
    assert data["time"] == 1700000000
    assert data["close"] == "40000.0"


def test_trade_tick_normalized_to_trades_channel_with_time_and_price():
    """卡 B:TradeTick → trades channel,data 帶前端視覺聚合用的 time(秒)+ price。

    前端用每筆成交的 time(epoch 秒,對齊 LWC UTCTimestamp)+ price 聚合到
    形成中那根 1m K 線(更新 high/low/close)。price 維持字串保留交易所精度。
    """
    norm = StreamNormalizer()
    env = norm.normalize_entry(
        _entry("data.trades.BINANCE.BTCUSDT-PERP", TRADE_TICK_PAYLOAD)
    )
    assert env is not None
    assert env["channel"] == "trades"
    data = env["data"]
    assert data["time"] == 1700000005  # ts_init 奈秒 → epoch 秒
    assert data["price"] == "40001.5"  # 字串保留精度
