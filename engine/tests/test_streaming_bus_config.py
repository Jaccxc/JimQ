"""卡 B(Live 次秒 tick)— ``streaming_message_bus_config`` 的 types_filter 行為。

行為驗收(透過 public builder interface,不連 Redis、不驗實作細節):
- 預設(backtest 路徑):``types_filter`` 同時排除 QuoteTick + TradeTick
  → backtest scope 不灌任何 tick(保持 Live 圖權威蠟燭與 backtest 隔離,
  backtest scope 無 trades 噪音)。
- ``include_trade_ticks=True``(live 路徑):**放行 TradeTick**(只排 QuoteTick)
  → live 節點的逐筆成交可序列化進 Redis Streams 供前端視覺聚合。

⛔ 設計鐵律:TradeTick 純視覺串流;它能進 stream 不代表進策略 ——
策略訂閱維持只 1m bar(見 test_live_node_trade_ticks.py)。
"""

from __future__ import annotations

from nautilus_trader.model.data import QuoteTick, TradeTick

from jimq_engine.streaming.redis_bus import streaming_message_bus_config


def test_default_excludes_both_tick_types_for_backtest():
    """預設(backtest):types_filter 同排 QuoteTick + TradeTick(無 tick 噪音)。"""
    mb = streaming_message_bus_config()
    assert QuoteTick in mb.types_filter
    assert TradeTick in mb.types_filter


def test_include_trade_ticks_passes_trade_tick_only():
    """include_trade_ticks=True(live):放行 TradeTick,仍排 QuoteTick 控流量。"""
    mb = streaming_message_bus_config(include_trade_ticks=True)
    assert TradeTick not in mb.types_filter, "live 路徑應放行 TradeTick(逐筆成交視覺串流)"
    assert QuoteTick in mb.types_filter, "QuoteTick 仍排除以控流量(testnet 不需要)"
