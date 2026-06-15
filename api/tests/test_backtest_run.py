"""S4 — backtest_run application model + FastCRUD (TDD slice 2).

Behaviour through public interfaces:
- BacktestStatus app-level enum maps to/from the DB VARCHAR via TypeDecorator
  (no DB-native enum — 鐵律 11);
- the FastCRUD instance round-trips a row against the real localhost Postgres
  with the Alembic-applied schema (no FK, timestamptz, NUMERIC metrics — 鐵律
  2/10/12).

The DB round-trip is opt-in (RUN_DB_TESTS=1) so the offline unit slice stays
fast; CI/local with infra up runs the full slice.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest


def test_status_enum_has_uppercase_contract_literals():
    from app.models.backtest_run import BacktestStatus

    assert {s.value for s in BacktestStatus} == {
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
    }


def test_status_typedecorator_roundtrips_enum_and_varchar():
    """TypeDecorator stores the uppercase literal and rehydrates the enum."""
    from app.models.backtest_run import BacktestStatus, BacktestStatusType

    td = BacktestStatusType()
    bound = td.process_bind_param(BacktestStatus.RUNNING, dialect=None)
    assert bound == "RUNNING"  # stored as plain VARCHAR

    result = td.process_result_value("COMPLETED", dialect=None)
    assert result is BacktestStatus.COMPLETED


def test_backtest_run_table_has_no_foreign_keys():
    from app.models.backtest_run import BacktestRun

    assert len(BacktestRun.__table__.foreign_keys) == 0  # 鐵律 12


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)
@pytest.mark.anyio
async def test_crud_roundtrips_backtest_run():
    from app.core.db.database import async_engine, local_session
    from app.crud.crud_backtest_run import crud_backtest_runs
    from app.models.backtest_run import BacktestStatus
    from app.schemas.backtest_run import BacktestRunCreate, BacktestRunRead

    async with local_session() as db:
        created = await crud_backtest_runs.create(
            db=db,
            object=BacktestRunCreate(
                strategy_name="ema_cross",
                instrument_id="BTCUSDT-PERP.BINANCE",
                bar_type="BTCUSDT-PERP.BINANCE-1-HOUR-LAST-EXTERNAL",
                timeframe="1H",
                start_time=datetime(2024, 1, 1, tzinfo=UTC),
                end_time=datetime(2024, 2, 1, tzinfo=UTC),
                params={"fast": 10, "slow": 30},
            ),
            schema_to_select=BacktestRunRead,
            return_as_model=True,
        )
        run_id = created.id

        fetched = await crud_backtest_runs.get(db=db, id=run_id)
        assert fetched is not None
        assert fetched["strategy_name"] == "ema_cross"
        assert fetched["instrument_id"] == "BTCUSDT-PERP.BINANCE"
        assert fetched["params"] == {"fast": 10, "slow": 30}
        # default status is PENDING and metrics are nullable until completion
        assert fetched["status"] == BacktestStatus.PENDING
        assert fetched["sharpe"] is None
        assert fetched["created_at"].tzinfo is not None  # timestamptz

        # complete the run with NUMERIC metrics
        await crud_backtest_runs.update(
            db=db,
            object={
                "status": BacktestStatus.COMPLETED.value,
                "total_return": Decimal("0.1234"),
                "sharpe": Decimal("1.55"),
                "max_drawdown": Decimal("0.0789"),
                "num_trades": 42,
                "final_balance": Decimal("11234.56"),
            },
            id=run_id,
        )

        done = await crud_backtest_runs.get(db=db, id=run_id)
        assert done["status"] == BacktestStatus.COMPLETED
        assert done["num_trades"] == 42
        assert Decimal(str(done["final_balance"])) == Decimal("11234.56")

        await crud_backtest_runs.db_delete(db=db, id=run_id)

    # Dispose the shared async engine so its asyncpg connections aren't reused
    # across event loops by later TestClient-based tests (test isolation only;
    # production runs a single loop).
    await async_engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
