"""卡 #15 — 批量 backtest runner(參數網格 → BacktestRunSummary)。

行為驗證(透過 public interface):
- ``run_grid`` 對策略參數網格(以 Phase 1 的 EMA 策略為示範對象)在指定 catalog
  上批量跑 backtest,每組參數產出一個 ``BacktestRunSummary``。
- 網格筆數 = 各參數軸的笛卡兒積;每筆 summary 攜帶該組 params 與結果指標
  (報酬 / Sharpe / 最大回撤 / 成交筆數 / 最終餘額)。
- 復用 engine 的 ``build_engine``(BacktestNode 路徑),串流關閉純取報表。
- 確定性:同輸入(含 seed)同結果。

合成黃金交叉資料寫進臨時 catalog(不打網路),確保有成交與非平凡指標。
"""

from __future__ import annotations

from decimal import Decimal

from jimq_core.schemas import BacktestRunSummary
from jimq_engine.catalog.ingest import BAR_TYPE_1M, ingest_bars
from jimq_engine.catalog.instruments import btcusdt_perp_binance
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from jimq_research.training import run_grid

_BASE_MS = 1_700_000_000_000


def _golden_cross_klines() -> list[list]:
    down = [40000.0 - i * 20 for i in range(15)]
    up = [down[-1] + i * 120 for i in range(1, 20)]
    prices = down + up
    out = []
    for i, p in enumerate(prices):
        ot = _BASE_MS + i * 60_000
        out.append(
            [ot, f"{p}", f"{p + 5}", f"{p - 5}", f"{p}", "10.000",
             ot + 59_999, "0", 1, "0", "0", "0"]
        )
    return out


def _catalog(tmp_path) -> ParquetDataCatalog:
    cat = ParquetDataCatalog(path=str(tmp_path / "catalog"))
    inst = btcusdt_perp_binance()
    cat.write_data([inst])
    ingest_bars(cat, _golden_cross_klines(), inst)
    return cat


def test_grid_produces_one_summary_per_param_combo(tmp_path):
    catalog = _catalog(tmp_path)
    # 2 x 1 grid -> 2 runs.
    grid = {"fast_period": [3, 4], "slow_period": [8]}

    summaries = run_grid(
        catalog,
        param_grid=grid,
        bar_type=BAR_TYPE_1M,
        timeframe="1m",
    )

    assert len(summaries) == 2
    assert all(isinstance(s, BacktestRunSummary) for s in summaries)
    combos = {(s.params["fast_period"], s.params["slow_period"]) for s in summaries}
    assert combos == {(3, 8), (4, 8)}


def test_summary_metrics_populated(tmp_path):
    catalog = _catalog(tmp_path)
    summaries = run_grid(
        catalog,
        param_grid={"fast_period": [3], "slow_period": [8]},
        bar_type=BAR_TYPE_1M,
        timeframe="1m",
    )
    s = summaries[0]
    # 有成交,最終餘額為正,筆數 >= 1。
    assert s.num_trades is not None and s.num_trades >= 1
    assert s.final_balance is not None and s.final_balance > Decimal("0")
    assert s.total_return is not None
    assert s.max_drawdown is not None
    assert s.strategy_name == "ema_cross"
    assert s.instrument_id == "BTCUSDT-PERP.BINANCE"


def test_grid_deterministic_same_input_same_result(tmp_path):
    g = {"fast_period": [3], "slow_period": [8]}
    a = run_grid(_catalog(tmp_path / "a"), param_grid=g, bar_type=BAR_TYPE_1M, timeframe="1m")
    b = run_grid(_catalog(tmp_path / "b"), param_grid=g, bar_type=BAR_TYPE_1M, timeframe="1m")
    assert a[0].final_balance == b[0].final_balance
    assert a[0].total_return == b[0].total_return
    assert a[0].num_trades == b[0].num_trades
