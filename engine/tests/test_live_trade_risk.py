"""卡 #29 (P2-S3) — live 交易節點**風控設定**(單元測試,RED→GREEN)。

驗收(行為,透過 public builder interface,不連真網路):
- ``build_live_trade_node_config`` 產出的 TradingNodeConfig 帶一個
  Nautilus 原生 **LiveRiskEngineConfig**(走 Nautilus RiskEngine,不自造平行風控):
  * ``max_notional_per_order``:對 BTCUSDT-PERP.BINANCE 設名目上限(預設保守值),
    超過上限的單會被 RiskEngine DENIED,不送到 venue。
  * ``max_order_submit_rate``:保守下單頻率上限(throttler),預設 "10/00:00:01"。
- 上限與頻率為 builder 參數(可由 run_live_trade.py 旗標覆寫)。

風控攔截的**真實行為**(超限單被 deny)以 backtest 引擎不連網驗證
(test_risk_engine_denies_oversized_order),確認用的是 Nautilus 原生 RiskEngine。
"""

from __future__ import annotations

from jimq_engine.catalog.instruments import BTCUSDT_PERP_BINANCE_ID
from jimq_engine.nodes.live import (
    BINANCE,
    DEFAULT_MAX_NOTIONAL_USDT,
    DEFAULT_MAX_ORDER_SUBMIT_RATE,
    build_live_trade_node_config,
)

_INSTR = str(BTCUSDT_PERP_BINANCE_ID)


def _cfg(**kw):
    return build_live_trade_node_config(api_key="K", api_secret="S", **kw)


def test_risk_engine_config_present():
    """節點帶 Nautilus 原生 risk_engine 設定(非自造平行風控)。"""
    cfg = _cfg()
    assert cfg.risk_engine is not None


def test_default_max_notional_per_order_set_for_btc():
    """預設對 BTCUSDT-PERP 設保守名目上限(超限單將被 RiskEngine deny)。"""
    cfg = _cfg()
    mnpo = cfg.risk_engine.max_notional_per_order
    assert _INSTR in mnpo
    assert int(mnpo[_INSTR]) == DEFAULT_MAX_NOTIONAL_USDT
    # 保守:預設名目上限應為數百 USDT 等級(0.001 BTC 安全範圍 + buffer)。
    assert 0 < int(mnpo[_INSTR]) <= 1000


def test_max_notional_override_param():
    cfg = _cfg(max_notional=250)
    assert int(cfg.risk_engine.max_notional_per_order[_INSTR]) == 250


def test_default_order_submit_rate_conservative():
    cfg = _cfg()
    assert cfg.risk_engine.max_order_submit_rate == DEFAULT_MAX_ORDER_SUBMIT_RATE
    # 保守:預設頻率上限不應是 Nautilus 預設的 100/秒。
    assert cfg.risk_engine.max_order_submit_rate != "100/00:00:01"


def test_order_submit_rate_override_param():
    cfg = _cfg(max_order_submit_rate="5/00:00:01")
    assert cfg.risk_engine.max_order_submit_rate == "5/00:00:01"


def test_risk_engine_not_bypassed():
    """⛔ 風控不可被 bypass(否則名目/頻率上限形同虛設)。"""
    cfg = _cfg()
    assert cfg.risk_engine.bypass is False
