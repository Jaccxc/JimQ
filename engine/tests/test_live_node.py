"""卡 #27 (P2-S1) — Binance testnet live 資料節點組裝(單元測試)。

驗收(行為,透過 public builder interface,不連真網路):
- ``build_live_data_node_config`` 產出的 TradingNodeConfig:
  * environment = LIVE(TradingNode 走 live engine)。
  * 帶一個 BINANCE data client,設 TESTNET 環境 + USDT_FUTURES 帳戶型別 +
    HMAC 金鑰(由參數注入,實務由 env 讀;絕不 commit)。
  * message_bus 用 #5 的可重用 streaming 設定(Redis Streams DB0,排高頻 tick)。
  * **無** exec client(本卡只接資料,不下單)。
- ``btcusdt_perp_bar_type`` / 訂閱規格:BTCUSDT-PERP.BINANCE 1分 LAST EXTERNAL,
  對應下游 consumer 的 ``data.bars.`` channel 映射。
- 金鑰未硬編(builder 不含預設金鑰字面值)。
"""

from __future__ import annotations

import pytest

from jimq_engine.nodes.live import (
    BINANCE,
    LIVE_TRADER_ID,
    btcusdt_perp_bar_type,
    build_live_data_node_config,
)


def _cfg():
    return build_live_data_node_config(
        api_key="TEST_KEY",
        api_secret="TEST_SECRET",
    )


def test_node_environment_is_live():
    from nautilus_trader.common import Environment

    cfg = _cfg()
    assert cfg.environment == Environment.LIVE
    assert str(cfg.trader_id) == LIVE_TRADER_ID


def test_has_binance_testnet_usdt_futures_data_client():
    from nautilus_trader.adapters.binance.common.enums import (
        BinanceAccountType,
        BinanceEnvironment,
        BinanceKeyType,
    )

    cfg = _cfg()
    assert str(BINANCE) in cfg.data_clients, "應註冊 BINANCE data client"
    dc = cfg.data_clients[str(BINANCE)]
    assert dc.environment == BinanceEnvironment.TESTNET
    assert dc.account_type == BinanceAccountType.USDT_FUTURES
    assert dc.key_type == BinanceKeyType.HMAC
    assert dc.api_key == "TEST_KEY"
    assert dc.api_secret == "TEST_SECRET"


def test_no_exec_client_data_only():
    # 鐵律:本卡只接 live 資料(read-only),不下任何單 → 不得有 exec client。
    cfg = _cfg()
    assert not cfg.exec_clients, "data-only 節點不應有 exec client(不下單)"


def test_streaming_message_bus_reused():
    # 復用 #5 的串流脊椎:message bus 落地 Redis Streams,排高頻 tick。
    cfg = _cfg()
    mb = cfg.message_bus
    assert mb is not None
    assert mb.database is not None
    assert mb.database.host == "localhost"  # 鐵律 4:localhost only
    assert mb.stream_per_topic is False
    # 高頻型別被排除(types_filter 非空)。
    assert mb.types_filter, "應排除高頻 tick 型別"


def test_bar_type_matches_consumer_channel():
    bt = btcusdt_perp_bar_type()
    s = str(bt)
    assert s.startswith("BTCUSDT-PERP.BINANCE")
    assert "MINUTE" in s
    # 下游 consumer 以 ``data.bars.{bar_type}`` topic 前綴映射到 bars channel。


def test_no_hardcoded_credentials_in_source():
    import inspect

    import jimq_engine.nodes.live as live_mod

    src = inspect.getsource(live_mod)
    # 不得出現硬編金鑰/密碼(issue #25 + 絕不 commit 金鑰)。
    assert "1234" not in src
    assert "BINANCE_TESTNET_KEY" in src or "api_key" in src  # 由 env/參數讀
