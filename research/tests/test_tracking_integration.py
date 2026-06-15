"""卡 #16 — 批量 backtest runner ↔ MLflow 整合(行為驗證,離線 sqlite)。

每次 backtest run 自動記錄成一個 MLflow run:params = 策略參數(+ run 身份),
metrics = 績效(報酬 / Sharpe / 回撤 / 成交數 / 最終餘額)。透過 public interface
``log_summary_to_mlflow`` / ``track_summaries`` 驗證,記錄後由 ``MlflowClient`` 查回。

離線:臨時 sqlite tracking backend,不需 docker、不打網路。合成黃金交叉資料寫進
臨時 catalog 確保有成交與非平凡指標(沿用 #15 測試慣例)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from jimq_core.schemas import BacktestRunSummary
from jimq_engine.catalog.ingest import BAR_TYPE_1M, ingest_bars
from jimq_engine.catalog.instruments import btcusdt_perp_binance
from mlflow.tracking import MlflowClient
from nautilus_trader.persistence.catalog import ParquetDataCatalog

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


def _local_uri(tmp_path) -> tuple[str, str]:
    return f"sqlite:///{tmp_path / 'mlflow.db'}", f"file://{tmp_path / 'artifacts'}"


def test_log_single_summary_as_mlflow_run(tmp_path):
    from jimq_research.training.tracking import log_summary_to_mlflow

    uri, art = _local_uri(tmp_path)
    summary = BacktestRunSummary(
        strategy_name="ema_cross",
        instrument_id="BTCUSDT-PERP.BINANCE",
        bar_type="BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        timeframe="1m",
        start_time=datetime(2024, 1, 1, tzinfo=UTC),
        end_time=datetime(2024, 1, 2, tzinfo=UTC),
        params={"fast_period": 5, "slow_period": 13},
        total_return=Decimal("0.0123"),
        sharpe=Decimal("1.20"),
        max_drawdown=Decimal("-0.0300"),
        num_trades=4,
        final_balance=Decimal("1012300.00000000"),
        run_group="rg-x",
    )

    run_id = log_summary_to_mlflow(
        summary, experiment="backtest", tracking_uri=uri, artifact_location=art
    )

    client = MlflowClient(tracking_uri=uri)
    run = client.get_run(run_id)
    # params = 策略參數 + run 身份。
    assert run.data.params["fast_period"] == "5"
    assert run.data.params["slow_period"] == "13"
    assert run.data.params["strategy_name"] == "ema_cross"
    assert run.data.params["run_group"] == "rg-x"
    # metrics = 績效。
    assert run.data.metrics["total_return"] == 0.0123
    assert run.data.metrics["sharpe"] == 1.2
    assert run.data.metrics["max_drawdown"] == -0.03
    assert run.data.metrics["num_trades"] == 4.0
    assert run.data.metrics["final_balance"] == 1012300.0
    # 掛在指定 experiment 下。
    assert client.get_experiment(run.info.experiment_id).name == "backtest"


def test_track_grid_summaries_one_run_each(tmp_path):
    from jimq_research.training import run_grid
    from jimq_research.training.tracking import track_summaries

    uri, art = _local_uri(tmp_path)
    catalog = _catalog(tmp_path)
    grid = {"fast_period": [3, 4], "slow_period": [8]}
    summaries = run_grid(
        catalog, param_grid=grid, bar_type=BAR_TYPE_1M, timeframe="1m", run_group="grid-1"
    )
    assert len(summaries) == 2

    run_ids = track_summaries(
        summaries, experiment="grid-exp", tracking_uri=uri, artifact_location=art
    )
    assert len(run_ids) == 2

    client = MlflowClient(tracking_uri=uri)
    exp = client.get_experiment_by_name("grid-exp")
    runs = client.search_runs([exp.experiment_id])
    # 每組參數 = 一個 MLflow run。
    assert len(runs) == 2
    fasts = sorted(int(r.data.params["fast_period"]) for r in runs)
    assert fasts == [3, 4]
    for r in runs:
        assert "final_balance" in r.data.metrics
        assert r.data.params["run_group"] == "grid-1"
