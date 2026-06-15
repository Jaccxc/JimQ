"""卡 #15 — 批量 backtest runner(參數網格 → BacktestRunSummary)。

research 是實驗編排層:匯入 jimq_engine(允許,research 為上層)復用 Phase 1 的
``build_engine``(BacktestNode 路徑)與 EMA 策略,對策略參數網格在指定區間批量跑
backtest,每組產出一個共用 ``BacktestRunSummary``(jimq_core.schemas)。串流關閉,
純取 nautilus 報表計算指標。

指標來源:
- ``final_balance`` = venue 帳戶 USDT total balance。
- ``total_return`` = (final - starting) / starting。
- ``num_trades`` = 已平倉部位數。
- ``sharpe`` = nautilus ``PortfolioAnalyzer`` 的 "Sharpe Ratio (252 days)"。
- ``max_drawdown`` = 由已實現 PnL 權益曲線(starting + 累計 realized_pnl,依平倉
  時間排序)算出的最大峰谷回撤(分數,<= 0)。

確定性:FillModel 固定 ``random_seed``,同輸入同結果。
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Sequence

from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from jimq_core.schemas import BacktestRunSummary
from jimq_engine.catalog.ingest import BAR_TYPE_1M, query_bars
from jimq_engine.catalog.instruments import (
    BTCUSDT_PERP_BINANCE_ID,
    btcusdt_perp_binance,
)
from jimq_engine.nodes.backtest import build_engine
from jimq_engine.strategies.ema_cross import EMACrossConfig

_BINANCE = Venue("BINANCE")
_NS_PER_SEC = 1_000_000_000

# Phase 1 EMA 策略的固定示範參數(網格只掃 fast/slow,其餘維持簡單預設)。
_DEFAULT_TRADE_SIZE = Decimal("0.100")
_DEFAULT_SL_PCT = Decimal("0.01")
_DEFAULT_TP_PCT = Decimal("0.02")


def expand_grid(param_grid: dict[str, Sequence[Any]]) -> list[dict[str, Any]]:
    """把 ``{axis: [values...]}`` 展開成參數組的笛卡兒積(穩定順序)。"""
    if not param_grid:
        return [{}]
    keys = list(param_grid.keys())
    return [
        dict(zip(keys, combo))
        for combo in itertools.product(*(param_grid[k] for k in keys))
    ]


def _max_drawdown_from_engine(engine) -> Decimal:
    """由已平倉部位的 realized_pnl 權益曲線算最大峰谷回撤(分數,<= 0)。"""
    account = engine.cache.account_for_venue(_BINANCE)
    starting = Decimal(str(account.starting_balances()[USDT].as_decimal()))

    closed = sorted(engine.cache.positions_closed(), key=lambda p: p.ts_closed)
    equity = starting
    peak = starting
    max_dd = Decimal("0")
    for pos in closed:
        equity += Decimal(str(pos.realized_pnl.as_decimal()))
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (equity - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return max_dd


def summarize_engine(
    engine,
    *,
    strategy_name: str,
    instrument_id: str,
    bar_type: str,
    timeframe: str,
    start_time: datetime,
    end_time: datetime,
    params: dict[str, Any],
    run_group: str | None = None,
) -> BacktestRunSummary:
    """從已 run 完的 ``BacktestEngine`` 萃取指標,組成共用 summary DTO。"""
    account = engine.cache.account_for_venue(_BINANCE)
    starting = Decimal(str(account.starting_balances()[USDT].as_decimal()))
    final_balance = Decimal(str(account.balance_total(USDT).as_decimal()))

    total_return = (
        (final_balance - starting) / starting if starting > 0 else Decimal("0")
    )

    num_trades = len(engine.cache.positions_closed())

    stats = engine.portfolio.analyzer.get_performance_stats_returns()
    sharpe_raw = stats.get("Sharpe Ratio (252 days)") if stats else None
    sharpe = (
        Decimal(str(sharpe_raw))
        if sharpe_raw is not None and sharpe_raw == sharpe_raw  # filter NaN
        else None
    )

    max_drawdown = _max_drawdown_from_engine(engine)

    return BacktestRunSummary(
        strategy_name=strategy_name,
        instrument_id=instrument_id,
        bar_type=bar_type,
        timeframe=timeframe,
        start_time=start_time,
        end_time=end_time,
        params=params,
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        num_trades=num_trades,
        final_balance=final_balance,
        run_group=run_group,
    )


def run_single(
    catalog: ParquetDataCatalog,
    params: dict[str, Any],
    *,
    bar_type=BAR_TYPE_1M,
    timeframe: str = "1m",
    start: int | None = None,
    end: int | None = None,
    random_seed: int = 42,
    run_group: str | None = None,
) -> BacktestRunSummary:
    """單組參數跑一次 backtest 並回傳 summary(復用 engine.build_engine）。"""
    instrument = btcusdt_perp_binance()
    bars = query_bars(catalog, bar_type=bar_type, start=start, end=end)
    if not bars:
        raise ValueError(
            f"catalog 無 {bar_type} bars(start={start}, end={end});先 ingest 或調整區間。"
        )

    config = EMACrossConfig(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        bar_type=bar_type,
        fast_period=int(params["fast_period"]),
        slow_period=int(params["slow_period"]),
        trade_size=Decimal(str(params.get("trade_size", _DEFAULT_TRADE_SIZE))),
        sl_pct=Decimal(str(params.get("sl_pct", _DEFAULT_SL_PCT))),
        tp_pct=Decimal(str(params.get("tp_pct", _DEFAULT_TP_PCT))),
    )

    engine = build_engine(instrument, bars, config, random_seed=random_seed)
    try:
        start_dt = datetime.fromtimestamp(bars[0].ts_init / _NS_PER_SEC, tz=UTC)
        end_dt = datetime.fromtimestamp(bars[-1].ts_init / _NS_PER_SEC, tz=UTC)
        return summarize_engine(
            engine,
            strategy_name="ema_cross",
            instrument_id=str(BTCUSDT_PERP_BINANCE_ID),
            bar_type=str(bar_type),
            timeframe=timeframe,
            start_time=start_dt,
            end_time=end_dt,
            params=params,
            run_group=run_group,
        )
    finally:
        engine.dispose()


def run_grid(
    catalog: ParquetDataCatalog,
    *,
    param_grid: dict[str, Sequence[Any]],
    bar_type=BAR_TYPE_1M,
    timeframe: str = "1m",
    start: int | None = None,
    end: int | None = None,
    random_seed: int = 42,
    run_group: str | None = None,
) -> list[BacktestRunSummary]:
    """對參數網格批量跑 backtest,回傳每組對應的 ``BacktestRunSummary`` 清單。"""
    return [
        run_single(
            catalog,
            params,
            bar_type=bar_type,
            timeframe=timeframe,
            start=start,
            end=end,
            random_seed=random_seed,
            run_group=run_group,
        )
        for params in expand_grid(param_grid)
    ]
