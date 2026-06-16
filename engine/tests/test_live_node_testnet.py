"""卡 #27 (P2-S1) — Binance testnet live 資料節點**真連線**整合測試(gated)。

需要:外網可達 Binance testnet + ``.env.afk`` 金鑰 + 本機 Redis(DB0)。
預設 **skip**;設 ``JIMQ_RUN_TESTNET=1`` 才跑(避免 CI/離線環境失敗)。

驗收(行為):連 testnet 訂閱 BTCUSDT-PERP bar 後,事件落地本機 Redis Streams,
且出現 ``data.bars.`` topic(下游 consumer 映射到 bars channel)。
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
        # 等待最多 ~90s 讓 1m bar 聚合落地(或 top-of-book)。
        deadline = time.time() + 90
        xlen = 0
        while time.time() < deadline:
            if client.exists(key):
                xlen = client.xlen(key)
                if xlen > 0:
                    break
            time.sleep(1)
        assert xlen > 0, "testnet live 事件未落地 Redis stream"
    finally:
        node.stop()
        time.sleep(1)
        node.dispose()
        client.delete(key)
        client.close()
