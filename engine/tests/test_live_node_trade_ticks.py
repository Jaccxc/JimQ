"""卡 B(Live 次秒 tick)— live 節點額外訂 TradeTick;策略維持只 1m bar。

⛔ 最高優先鐵律:tick 純視覺,絕不進策略。
- 策略決策只在 1m bar「收線」跑一次(EMACross.on_bar 不變);TradeTick 走獨立
  視覺串流,不餵進策略 → 下單次數只由 bar 收線驅動,與 tick 數無關。

行為驗收(透過 public builder/strategy interface,不連真網路):
1. ``build_live_data_node_config`` / ``build_live_trade_node_config`` 額外掛一個
   **data-only** TradeTick 訂閱 actor,且 message bus 放行 TradeTick
   (``include_trade_ticks=True``)→ 逐筆成交能序列化進 Redis 供前端視覺聚合。
2. 交易節點的**策略**訂閱維持只 1m bar(strategy config 的 bar_type 不變,
   策略路徑無 TradeTick)。
3. ⛔ 關鍵:灌大量 TradeTick 進引擎不會讓 EMACross 多下任何單 —— 下單/成交筆數
   與「只灌 bar」的 run 完全相同(tick 不觸發策略決策)。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from jimq_engine.nodes.live import (
    BINANCE,
    build_live_data_node_config,
    build_live_trade_node_config,
)


def _data_cfg():
    return build_live_data_node_config(api_key="TEST_KEY", api_secret="TEST_SECRET")


def _trade_cfg():
    return build_live_trade_node_config(api_key="TEST_KEY", api_secret="TEST_SECRET")


# --- (1) 節點額外訂 TradeTick + bus 放行 TradeTick -------------------------- #


def _actor_config_payloads(cfg) -> list[dict]:
    return [dict(a.config) for a in cfg.actors]


def test_data_node_subscribes_trade_ticks():
    """data 節點除 1m bar 外,額外掛一個訂 TradeTick 的 data-only actor。"""
    cfg = _data_cfg()
    payloads = _actor_config_payloads(cfg)
    has_trade_sub = any("trade_tick_instrument_id" in p for p in payloads)
    assert has_trade_sub, "live data 節點應額外掛訂 TradeTick 的 actor"
    # 視覺串流標的 = BTCUSDT-PERP.BINANCE(與 bar 同標的)。
    tick_payload = next(p for p in payloads if "trade_tick_instrument_id" in p)
    assert tick_payload["trade_tick_instrument_id"].startswith("BTCUSDT-PERP.BINANCE")


def test_data_node_bus_passes_trade_ticks():
    """data 節點 message bus 放行 TradeTick(include_trade_ticks → 只排 QuoteTick)。"""
    from nautilus_trader.model.data import QuoteTick, TradeTick

    mb = _data_cfg().message_bus
    assert TradeTick not in mb.types_filter, "live 節點應放行 TradeTick(視覺串流)"
    assert QuoteTick in mb.types_filter, "QuoteTick 仍排除控流量"


def test_trade_node_subscribes_trade_ticks():
    """交易節點同樣額外掛 TradeTick 視覺訂閱 actor + bus 放行。"""
    from nautilus_trader.model.data import TradeTick

    cfg = _trade_cfg()
    payloads = _actor_config_payloads(cfg)
    assert any("trade_tick_instrument_id" in p for p in payloads), (
        "live 交易節點應額外掛訂 TradeTick 的 actor"
    )
    assert TradeTick not in cfg.message_bus.types_filter


def test_trade_node_strategy_still_only_subscribes_1m_bar():
    """⛔ 策略訂閱維持只 1m bar:strategy config 的 bar_type 不含 tick。

    保住回測/live parity —— 策略只看正式收線 1m bar,TradeTick 不在策略路徑。
    """
    cfg = _trade_cfg()
    assert cfg.strategies, "交易節點應有策略"
    strat_cfg = dict(cfg.strategies[0].config)
    bar_type = strat_cfg["bar_type"]
    assert "MINUTE" in bar_type, "策略只訂 1 分鐘 bar"
    assert "TRADE" not in bar_type.upper() and "TICK" not in bar_type.upper(), (
        "策略 bar_type 不得是 tick(策略只看收線 bar)"
    )


# --- (3) ⛔ 關鍵:tick 不影響策略下單次數 ----------------------------------- #


def _instrument():
    from jimq_engine.catalog.instruments import btcusdt_perp_binance

    return btcusdt_perp_binance()


def _golden_then_death_klines(instrument):
    """造一段先黃金交叉(做多)再死亡交叉(做空)的 1m bar 序列,確保有下單。"""
    from nautilus_trader.model.data import Bar, BarType

    bar_type = BarType.from_str(
        "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"
    )
    base_ns = 1_700_000_000_000_000_000
    minute_ns = 60_000_000_000
    down = [40000.0 - i * 25 for i in range(12)]
    up = [down[-1] + i * 130 for i in range(1, 16)]
    back = [up[-1] - i * 130 for i in range(1, 16)]
    prices = down + up + back
    bars: list[Bar] = []
    for i, p in enumerate(prices):
        ts = base_ns + i * minute_ns
        bars.append(
            Bar(
                bar_type=bar_type,
                open=instrument.make_price(p),
                high=instrument.make_price(p + 5),
                low=instrument.make_price(p - 5),
                close=instrument.make_price(p),
                volume=instrument.make_qty(10),
                ts_event=ts,
                ts_init=ts,
            )
        )
    return bars


def _trade_ticks_between_bars(instrument, bars):
    """在每根 bar 之間灌大量 TradeTick(逐筆成交)模擬次秒級跳動。"""
    from nautilus_trader.model.data import TradeTick
    from nautilus_trader.model.enums import AggressorSide
    from nautilus_trader.model.identifiers import TradeId

    ticks: list[TradeTick] = []
    for b in bars:
        bar_ts = int(b.ts_init)
        close = b.close.as_double()
        # 每根 bar 之內塞 50 筆 tick(視覺次秒跳動),時間落在 bar 收線之前。
        for j in range(50):
            ts = bar_ts - 60_000_000_000 + j * 1_000_000_000
            px = close + (j % 5) * 2 - 4
            ticks.append(
                TradeTick(
                    instrument_id=instrument.id,
                    price=instrument.make_price(px),
                    size=instrument.make_qty(Decimal("0.01")),
                    aggressor_side=AggressorSide.BUYER,
                    trade_id=TradeId(f"T-{bar_ts}-{j}"),
                    ts_event=ts,
                    ts_init=ts,
                )
            )
    return ticks


def _run_emacross(data_list):
    """跑一個只裝 EMACross 的 backtest,回 (下單數, 成交數)。"""
    from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.currencies import USDT
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.objects import Money

    from jimq_engine.nodes.backtest import default_fill_model
    from jimq_engine.strategies.ema_cross import EMACross, EMACrossConfig

    instrument = _instrument()
    cfg = EMACrossConfig(
        instrument_id=instrument.id,
        bar_type=BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"),
        fast_period=3,
        slow_period=8,
        trade_size=Decimal("0.100"),
    )
    engine = BacktestEngine(
        config=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            logging=LoggingConfig(bypass_logging=True),
        )
    )
    engine.add_venue(
        venue=BINANCE,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USDT,
        starting_balances=[Money(Decimal("1_000_000"), USDT)],
        default_leverage=Decimal("10"),
        fill_model=default_fill_model(42),
    )
    engine.add_instrument(instrument)
    engine.add_data(data_list)
    engine.add_strategy(EMACross(config=cfg))
    engine.run()
    orders = engine.cache.orders()
    fills = [o for o in orders if o.filled_qty > 0]
    n_orders, n_fills = len(orders), len(fills)
    engine.dispose()
    return n_orders, n_fills


def test_trade_ticks_do_not_change_strategy_order_count():
    """⛔ 灌大量 TradeTick 不讓 EMACross 多下任何單:下單/成交數只由 bar 收線驅動。

    對照:
    - run A:只灌 1m bar。
    - run B:同一批 bar + 每根之間 50 筆 TradeTick(次秒跳動)。
    兩者下單數與成交數必須完全相同 → 證明 tick 不進策略決策路徑。
    """
    instrument = _instrument()
    bars = _golden_then_death_klines(instrument)
    ticks = _trade_ticks_between_bars(instrument, bars)

    # bar+tick 須按時間排序餵進引擎(Nautilus 要求 data 時序遞增)。
    bars_only = sorted(bars, key=lambda d: int(d.ts_init))
    mixed = sorted([*bars, *ticks], key=lambda d: int(d.ts_init))

    orders_a, fills_a = _run_emacross(bars_only)
    orders_b, fills_b = _run_emacross(mixed)

    assert orders_a > 0, "測試前提:bar 序列應觸發至少一次下單(否則無從對照)"
    assert orders_b == orders_a, (
        f"TradeTick 改變了下單次數!bar-only={orders_a} bar+tick={orders_b} "
        "—— tick 絕不可進策略決策路徑"
    )
    assert fills_b == fills_a, (
        f"TradeTick 改變了成交次數!bar-only={fills_a} bar+tick={fills_b}"
    )
