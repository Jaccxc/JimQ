"""卡 #27 (P2-S1) — Binance testnet live 資料節點**真連線**整合測試(gated)。

需要:外網可達 Binance testnet + ``.env.afk`` 金鑰 + 本機 Redis(DB0)。
預設 **skip**;設 ``JIMQ_RUN_TESTNET=1`` 才跑(避免 CI/離線環境失敗)。

驗收(行為):連 testnet 訂閱 BTCUSDT-PERP bar 後,事件落地本機 Redis Streams,
且出現 ``data.bars.<INSTRUMENT>`` topic 的**真 Bar**(payload type==Bar 且帶可解析的
OHLC,high>=low、close 在 [low,high]),而非只 ``xlen>0``(否則 ComponentStateChanged
等生命週期雜訊即可讓測試通過,無法證明真市場資料流動)。
"""

from __future__ import annotations

import os
import time

import pytest

redis = pytest.importorskip("redis")

pytestmark = pytest.mark.skipif(
    os.environ.get("JIMQ_RUN_TESTNET") != "1",
    reason="gated:設 JIMQ_RUN_TESTNET=1 並具外網+金鑰才跑真 testnet 連線測試",
)


def _decode(v):
    return v.decode() if isinstance(v, (bytes, bytearray)) else v


def _scan_real_bars(client, key):
    """掃 stream key,回傳所有「真 Bar」entry:(topic, payload_dict)。

    真 Bar 判定(行為,非實作細節):
    - topic 以 ``data.bars.`` 起頭(下游 #7 consumer 映射到 bars channel);
    - payload 反序列化為 dict,``type == "Bar"``;
    - 帶 OHLC 欄位且可轉 float,滿足 high>=low 且 low<=close<=high(真市場 K 線不變式)。

    ComponentStateChanged / ProcessId 等生命週期事件不符此判定,故無法蒙混。
    """
    import msgspec

    real_bars = []
    if not client.exists(key):
        return real_bars
    for _id, fields in client.xrange(key):
        fields = {_decode(k): v for k, v in fields.items()}
        topic = _decode(fields.get("topic"))
        if not topic or not topic.startswith("data.bars."):
            continue
        try:
            payload = msgspec.msgpack.decode(fields.get("payload"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(payload, dict) or payload.get("type") != "Bar":
            continue
        try:
            o = float(payload["open"])
            h = float(payload["high"])
            low = float(payload["low"])
            c = float(payload["close"])
        except (KeyError, TypeError, ValueError):
            continue
        # 真市場 K 線不變式(雜訊事件無 OHLC,無法偽造）。
        if h >= low and low <= c <= h and low <= o <= h:
            real_bars.append((topic, payload))
    return real_bars


def test_testnet_live_bars_land_in_redis():
    import threading

    from dotenv import load_dotenv

    from nautilus_trader.adapters.binance import BinanceLiveDataClientFactory
    from nautilus_trader.live.node import TradingNode

    from jimq_engine.nodes.live import (
        BINANCE,
        build_live_data_node_config,
        credentials_from_env,
    )
    from scripts.run_live_data import _stream_key_for_node
    from jimq_core.constants import REDIS_BUS_DB

    load_dotenv(".env.afk")
    api_key, api_secret = credentials_from_env()

    client = redis.Redis(host="localhost", port=6379, db=REDIS_BUS_DB)
    client.ping()

    config = build_live_data_node_config(api_key=api_key, api_secret=api_secret)
    node = TradingNode(config=config)
    node.add_data_client_factory(BINANCE.value, BinanceLiveDataClientFactory)
    node.build()
    key = _stream_key_for_node(node)
    client.delete(key)

    t = threading.Thread(target=node.run, daemon=True)
    t.start()
    try:
        # 真 1m bar 要等整分鐘收盤,最久 ~120s 讓至少一根真 bar 聚合落地。
        deadline = time.time() + 130
        real_bars = []
        while time.time() < deadline:
            real_bars = _scan_real_bars(client, key)
            if real_bars:
                break
            time.sleep(2)
        # RED-first 強化:不再只看 xlen>0(雜訊即過),要求真 Bar(帶 OHLC)。
        assert real_bars, (
            f"未在 Redis stream {key} 看到真 data.bars. Bar(含 OHLC);"
            "ComponentStateChanged 等生命週期雜訊不算真市場資料"
        )
        topic, bar = real_bars[0]
        assert topic.startswith("data.bars.BTCUSDT-PERP.BINANCE"), topic
        assert float(bar["high"]) >= float(bar["low"]) > 0, bar
    finally:
        node.stop()
        time.sleep(1)
        node.dispose()
        client.delete(key)
        client.close()
