"""卡 #29 (P2-S3) — 風控在真 testnet 上的 gated smoke 整合測試。

需要:外網可達 Binance testnet + ``.env.afk`` 金鑰 + 本機 Redis(DB0)。
預設 **skip**;設 ``JIMQ_RUN_TESTNET=1`` 才跑。

驗收(gated smoke):帶**風控 config**(max_notional_per_order + max_order_submit_rate)
的 live 交易節點能成功 ``build()``(連 testnet、載入 instrument、掛 RiskEngine)並
跑起來,證明風控設定不破壞真實連線啟動路徑。

⚠️ 為何只做 smoke、不在 testnet 上斷言「超名目單被 deny」:
- nautilus_trader 1.228.0 的 RiskEngine 名目風控對 **MARGIN 帳戶 early-return**
  (見 test_risk_engine_deny.py 模組 docstring),Binance USDT-M Futures = MARGIN,
  故 testnet 上 max_notional_per_order **不會**觸發 OrderDenied —— 在 testnet 上斷言
  deny 會永遠失敗,是錯誤的測試。名目風控的真實攔截行為已用 spot+CASH backtest
  (test_risk_engine_deny.py)確定性驗證。
- 在 testnet 上**會生效**的 native 風控是 max_order_submit_rate(throttler)與
  kill switch;rate limit 需高頻連發才觸發,難在 smoke 中穩定造出,故此處只驗
  「帶風控 config 的節點成功啟動連線」。

⛔ testnet-only:節點硬性 BinanceEnvironment.TESTNET;本測試亦驗 exec client 為 testnet。
"""

from __future__ import annotations

import os
import threading
import time

import pytest

redis = pytest.importorskip("redis")

pytestmark = pytest.mark.skipif(
    os.environ.get("JIMQ_RUN_TESTNET") != "1",
    reason="gated:設 JIMQ_RUN_TESTNET=1 並具外網+金鑰才跑帶風控的真 testnet 啟動 smoke",
)


def test_live_node_with_risk_config_builds_and_connects_testnet():
    from dotenv import load_dotenv

    from nautilus_trader.adapters.binance import (
        BinanceLiveDataClientFactory,
        BinanceLiveExecClientFactory,
    )
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment
    from nautilus_trader.live.node import TradingNode

    from jimq_core.constants import REDIS_BUS_DB
    from jimq_engine.nodes.live import (
        BINANCE,
        build_live_trade_node_config,
        credentials_from_env,
    )

    load_dotenv(".env.afk")
    api_key, api_secret = credentials_from_env()

    client = redis.Redis(host="localhost", port=6379, db=REDIS_BUS_DB)
    client.ping()

    # 帶顯式風控旗標(保守名目 200 USDT、下單頻率 10/秒)。
    config = build_live_trade_node_config(
        api_key=api_key,
        api_secret=api_secret,
        max_notional=200,
        max_order_submit_rate="10/00:00:01",
    )
    # ⛔ exec client 確為 testnet(非真錢)。
    assert config.exec_clients[str(BINANCE)].environment == BinanceEnvironment.TESTNET
    # 風控 config 確實掛上(同 build_live_trade_node_config 單元測試)。
    assert config.risk_engine is not None
    assert config.risk_engine.bypass is False
    assert config.risk_engine.max_order_submit_rate == "10/00:00:01"
    from jimq_engine.catalog.instruments import BTCUSDT_PERP_BINANCE_ID

    assert int(
        config.risk_engine.max_notional_per_order[str(BTCUSDT_PERP_BINANCE_ID)]
    ) == 200

    node = TradingNode(config=config)
    node.add_data_client_factory(BINANCE.value, BinanceLiveDataClientFactory)
    node.add_exec_client_factory(BINANCE.value, BinanceLiveExecClientFactory)
    # build() 會連 testnet、載入 instrument、組裝含 RiskEngine 的引擎。
    node.build()

    t = threading.Thread(target=node.run, daemon=True)
    t.start()
    try:
        # 跑短時間確認節點連線啟動穩定(不下單斷言;見模組 docstring)。
        time.sleep(20)
        assert t.is_alive(), "帶風控 config 的 live 節點應成功啟動並持續運行"
    finally:
        node.stop()
        time.sleep(1)
        node.dispose()
        client.close()
