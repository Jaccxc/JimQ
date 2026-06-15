"""卡 #15 — 共用 BacktestRunSummary DTO(jimq_core.schemas）。

行為層測試(public interface):
- BacktestRunSummary 是 Pydantic v2 模型,攜帶一次 backtest run 的身份
  (strategy/instrument/bar_type/timeframe/區間/params)與結果指標
  (total_return / sharpe / max_drawdown / num_trades / final_balance)。
- 為 engine / research / api 共用契約,放在 jimq_core(純 Pydantic,不依賴
  nautilus 或 sqlalchemy 即可驗證)。
- 金額/比率以 Decimal 保留精度(對齊 DB 端 NUMERIC,鐵律 10);params 為任意
  策略參數(本質非結構化 payload)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from jimq_core.schemas import BacktestRunSummary


def _summary(**overrides):
    base = dict(
        strategy_name="ema_cross",
        instrument_id="BTCUSDT-PERP.BINANCE",
        bar_type="BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        timeframe="1m",
        start_time=datetime(2024, 1, 1, tzinfo=UTC),
        end_time=datetime(2024, 1, 2, tzinfo=UTC),
        params={"fast_period": 10, "slow_period": 20},
        total_return=Decimal("0.0123"),
        sharpe=Decimal("1.45"),
        max_drawdown=Decimal("-0.05"),
        num_trades=7,
        final_balance=Decimal("1012300.00000000"),
    )
    base.update(overrides)
    return BacktestRunSummary(**base)


def test_summary_carries_run_identity_and_metrics():
    s = _summary()
    assert s.strategy_name == "ema_cross"
    assert s.instrument_id == "BTCUSDT-PERP.BINANCE"
    assert s.params == {"fast_period": 10, "slow_period": 20}
    assert s.num_trades == 7


def test_summary_metrics_are_decimal_for_numeric_precision():
    s = _summary(final_balance=Decimal("999999.99999999"))
    # 金額/比率以 Decimal 保留精度,對齊 DB NUMERIC(鐵律 10)。
    assert isinstance(s.final_balance, Decimal)
    assert isinstance(s.total_return, Decimal)
    assert s.final_balance == Decimal("999999.99999999")


def test_summary_optional_run_group_for_grid_cohort():
    # 一次參數網格批跑的多筆 run 用同一 run_group 標記,便於查詢/比較。
    s = _summary(run_group="grid-abc")
    assert s.run_group == "grid-abc"
    # 不給時為 None(單跑情境)。
    assert _summary().run_group is None
