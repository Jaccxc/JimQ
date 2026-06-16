"""卡 #28 (P2-S2) — Binance testnet **live 交易節點**組裝(單元測試,RED→GREEN)。

驗收(行為,透過 public builder interface,不連真網路):
- ``build_live_trade_node_config`` 產出的 TradingNodeConfig:
  * environment = LIVE。
  * 帶一個 BINANCE **data** client(TESTNET / USDT_FUTURES / HMAC)。
  * 帶一個 BINANCE **exec** client(TESTNET / USDT_FUTURES / HMAC) —— 本卡核心:
    與 #27 data-only 不同,P2-S2 要下 paper 單,故同時掛 exec client。
  * LiveExecEngineConfig 開 **reconciliation**(重啟對帳;研究凍結契約要求)。
  * message_bus 用 #5 的可重用 streaming 設定(Redis Streams DB0,排高頻 tick),
    使訂單/成交/部位/PnL 事件落地 Redis → consumer → WS → Live 頁面板。
  * 掛上 ema_cross 策略(復用 backtest 同碼;只換 adapter/設定 → research↔live parity)。

⛔ 最高優先安全(硬性 testnet-only):
- exec / data client 一律 ``BinanceEnvironment.TESTNET``;``assert_testnet_only``
  對任何非 TESTNET 環境(LIVE / DEMO)拋例外 —— 程式硬性阻擋真錢 mainnet。
- 原始碼不得出現 mainnet base url(binance.com fapi 等真盤端點)、不得硬編金鑰。
"""

from __future__ import annotations

import pytest

from jimq_engine.nodes.live import (
    BINANCE,
    LIVE_TRADER_ID,
    assert_testnet_only,
    build_live_trade_node_config,
)


def _cfg():
    return build_live_trade_node_config(
        api_key="TEST_KEY",
        api_secret="TEST_SECRET",
    )


def test_trade_node_environment_is_live():
    from nautilus_trader.common import Environment

    cfg = _cfg()
    assert cfg.environment == Environment.LIVE
    assert str(cfg.trader_id) == LIVE_TRADER_ID


def test_has_binance_testnet_data_client():
    from nautilus_trader.adapters.binance.common.enums import (
        BinanceAccountType,
        BinanceEnvironment,
        BinanceKeyType,
    )

    cfg = _cfg()
    assert str(BINANCE) in cfg.data_clients
    dc = cfg.data_clients[str(BINANCE)]
    assert dc.environment == BinanceEnvironment.TESTNET
    assert dc.account_type == BinanceAccountType.USDT_FUTURES
    assert dc.key_type == BinanceKeyType.HMAC


def test_has_binance_testnet_exec_client():
    """本卡核心:同時掛 **exec** client(testnet)才能下 paper 單。"""
    from nautilus_trader.adapters.binance.common.enums import (
        BinanceAccountType,
        BinanceEnvironment,
        BinanceKeyType,
    )

    cfg = _cfg()
    assert cfg.exec_clients, "live 交易節點必須有 exec client(下 paper 單)"
    assert str(BINANCE) in cfg.exec_clients
    ec = cfg.exec_clients[str(BINANCE)]
    assert ec.environment == BinanceEnvironment.TESTNET, "⛔ exec 必須 testnet"
    assert ec.account_type == BinanceAccountType.USDT_FUTURES
    assert ec.key_type == BinanceKeyType.HMAC
    assert ec.api_key == "TEST_KEY"
    assert ec.api_secret == "TEST_SECRET"


def test_exec_engine_reconciliation_enabled():
    cfg = _cfg()
    assert cfg.exec_engine is not None
    assert cfg.exec_engine.reconciliation is True, "重啟對帳須開啟"


def test_streaming_message_bus_reused():
    cfg = _cfg()
    mb = cfg.message_bus
    assert mb is not None and mb.database is not None
    assert mb.database.host == "localhost"  # 鐵律 4:localhost only
    assert mb.stream_per_topic is False
    assert mb.types_filter, "應排除高頻 tick 型別"


def test_strategy_attached_shared_with_backtest():
    """掛上 ema_cross 策略(與 backtest 共用同一策略碼 → parity)。"""
    cfg = _cfg()
    assert cfg.strategies, "live 交易節點須掛策略下單"
    # ImportableStrategyConfig 指向 EMACross(與 backtest 同碼)。
    paths = [str(s.strategy_path) for s in cfg.strategies]
    assert any("EMACross" in p for p in paths), paths


# --- ⛔ testnet-only 安全閘 ------------------------------------------------- #


def test_assert_testnet_only_passes_for_testnet():
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

    # 不拋例外即通過。
    assert_testnet_only(BinanceEnvironment.TESTNET)


def test_assert_testnet_only_blocks_mainnet_live():
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

    with pytest.raises(Exception) as exc:
        assert_testnet_only(BinanceEnvironment.LIVE)
    assert "testnet" in str(exc.value).lower() or "mainnet" in str(exc.value).lower()


def test_assert_testnet_only_blocks_demo():
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

    with pytest.raises(Exception):
        assert_testnet_only(BinanceEnvironment.DEMO)


def test_builder_rejects_non_testnet_environment():
    """builder 提供環境覆寫時,非 testnet 一律拒絕(硬性阻擋真錢)。"""
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

    with pytest.raises(Exception):
        build_live_trade_node_config(
            api_key="K",
            api_secret="S",
            environment=BinanceEnvironment.LIVE,
        )


def test_no_mainnet_base_url_or_hardcoded_credentials():
    import inspect

    import jimq_engine.nodes.live as live_mod

    src = inspect.getsource(live_mod)
    # 不得出現 mainnet 真盤端點(只允許 testnet 域)。
    assert "fapi.binance.com" not in src
    assert "api.binance.com" not in src
    # 不得硬編金鑰。
    assert "1234" not in src
