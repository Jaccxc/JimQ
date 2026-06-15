"""卡 #15 — 批量 backtest run 摘要持久化到 Postgres backtest_run。

行為驗證(透過 public interface,連 localhost Postgres):
- ``persist_summaries`` 用 SQLAlchemy(app 級 INSERT,非手動 DDL/DML)把每個
  ``BacktestRunSummary`` 寫入既有 ``backtest_run`` 表,回傳新增列的 id。
- ``query_runs`` 依 ``run_group`` 查回多筆 run 結果供比較(SQLAlchemy SELECT)。
- 一個小參數網格 → 產生對應數量的 run 且持久化、可查詢比較。

DB round-trip 為 opt-in(``RUN_DB_TESTS=1``)以保持離線單元切片快速,沿用 api
測試慣例。連線只連 localhost(鐵律 4),測試自行清掉自己寫入的列。
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest

from jimq_core.schemas import BacktestRunSummary
from jimq_engine.catalog.ingest import BAR_TYPE_1M, ingest_bars
from jimq_engine.catalog.instruments import btcusdt_perp_binance
from nautilus_trader.persistence.catalog import ParquetDataCatalog

_DB = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)

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


@_DB
def test_persist_and_query_grid_runs(tmp_path):
    from jimq_research.training import run_grid
    from jimq_research.training.store import (
        delete_run_group,
        local_engine_url,
        persist_summaries,
        query_runs,
    )

    catalog = _catalog(tmp_path)
    run_group = f"test-{uuid.uuid4().hex[:8]}"
    grid = {"fast_period": [3, 4], "slow_period": [8]}

    summaries = run_grid(
        catalog,
        param_grid=grid,
        bar_type=BAR_TYPE_1M,
        timeframe="1m",
        run_group=run_group,
    )
    assert len(summaries) == 2

    url = local_engine_url()
    try:
        ids = persist_summaries(summaries, engine_url=url)
        assert len(ids) == 2
        assert all(isinstance(i, int) for i in ids)

        rows = query_runs(url, run_group=run_group)
        # 產生對應數量的 run 且可查詢比較。
        assert len(rows) == 2
        assert {r["run_group"] for r in rows} == {run_group}
        assert {r["strategy_name"] for r in rows} == {"ema_cross"}
        # 指標已持久化(COMPLETED + NUMERIC final_balance)。
        for r in rows:
            assert r["status"] == "COMPLETED"
            assert r["final_balance"] is not None
            assert Decimal(str(r["final_balance"])) > Decimal("0")
            assert r["num_trades"] is not None
        # 可比較:兩組 fast_period 各一筆。
        fasts = sorted(r["params"]["fast_period"] for r in rows)
        assert fasts == [3, 4]
    finally:
        delete_run_group(url, run_group)
        # 清理後查不到。
        assert query_runs(url, run_group=run_group) == []


@_DB
def test_persist_single_summary_roundtrip(tmp_path):
    from jimq_research.training.store import (
        delete_run_group,
        local_engine_url,
        persist_summaries,
        query_runs,
    )
    from datetime import UTC, datetime

    rg = f"test-{uuid.uuid4().hex[:8]}"
    s = BacktestRunSummary(
        strategy_name="ema_cross",
        instrument_id="BTCUSDT-PERP.BINANCE",
        bar_type="BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        timeframe="1m",
        start_time=datetime(2024, 1, 1, tzinfo=UTC),
        end_time=datetime(2024, 1, 2, tzinfo=UTC),
        params={"fast_period": 5, "slow_period": 13},
        total_return=Decimal("0.01"),
        sharpe=Decimal("1.2"),
        max_drawdown=Decimal("-0.03"),
        num_trades=4,
        final_balance=Decimal("1010000.00000000"),
        run_group=rg,
    )
    url = local_engine_url()
    try:
        ids = persist_summaries([s], engine_url=url)
        assert len(ids) == 1
        rows = query_runs(url, run_group=rg)
        assert len(rows) == 1
        r = rows[0]
        assert r["params"] == {"fast_period": 5, "slow_period": 13}
        assert Decimal(str(r["final_balance"])) == Decimal("1010000.00000000")
        assert r["num_trades"] == 4
        assert r["created_at"].tzinfo is not None  # timestamptz
    finally:
        delete_run_group(url, rg)
