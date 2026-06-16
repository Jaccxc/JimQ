"""卡 #21 (W2) — backtest_trade application model + FastCRUD roundtrip.

Behaviour through public interfaces:
- ``TradeSide`` app-level enum maps to/from the DB VARCHAR(32) via a
  TypeDecorator (no DB-native enum — 鐵律 11);
- the table has **no foreign keys** — ``run_id`` is a plain indexed column
  (鐵律 12);
- a row round-trips against the real localhost Postgres with the
  Alembic-applied schema (timestamptz opened_at/closed_at, NUMERIC prices —
  鐵律 2/10/12).

The DB round-trip is opt-in (RUN_DB_TESTS=1) so the offline unit slice stays
fast; CI/local with infra up runs the full slice.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest


def test_trade_side_has_uppercase_contract_literals():
    from app.models.backtest_trade import TradeSide

    assert {s.value for s in TradeSide} == {"LONG", "SHORT"}


def test_trade_side_typedecorator_roundtrips_enum_and_varchar():
    from app.models.backtest_trade import TradeSide, TradeSideType

    td = TradeSideType()
    bound = td.process_bind_param(TradeSide.LONG, dialect=None)
    assert bound == "LONG"  # stored as plain VARCHAR

    result = td.process_result_value("SHORT", dialect=None)
    assert result is TradeSide.SHORT


def test_backtest_trade_table_has_no_foreign_keys():
    from app.models.backtest_trade import BacktestTrade

    assert len(BacktestTrade.__table__.foreign_keys) == 0  # 鐵律 12


def test_run_id_is_indexed_plain_column():
    from app.models.backtest_trade import BacktestTrade

    col = BacktestTrade.__table__.c.run_id
    assert col.index is True  # 關聯靠索引欄(鐵律 12)
    assert len(col.foreign_keys) == 0


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)
@pytest.mark.anyio
async def test_crud_roundtrips_backtest_trade():
    from app.core.db.database import async_engine, local_session
    from app.crud.crud_backtest_trade import crud_backtest_trades
    from app.models.backtest_trade import TradeSide
    from app.schemas.backtest_trade import BacktestTradeCreate, BacktestTradeRead

    async with local_session() as db:
        created = await crud_backtest_trades.create(
            db=db,
            object=BacktestTradeCreate(
                run_id=987654,
                instrument_id="BTCUSDT-PERP.BINANCE",
                side=TradeSide.LONG,
                entry_price=Decimal("37000.5"),
                exit_price=Decimal("37500.25"),
                quantity=Decimal("0.5"),
                sl=Decimal("36630.0"),
                tp=Decimal("37740.0"),
                pnl=Decimal("249.875"),
                opened_at=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
                closed_at=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
            ),
            schema_to_select=BacktestTradeRead,
            return_as_model=True,
        )
        trade_id = created.id

        fetched = await crud_backtest_trades.get(db=db, id=trade_id)
        assert fetched is not None
        assert fetched["run_id"] == 987654
        assert fetched["side"] == TradeSide.LONG
        assert Decimal(str(fetched["entry_price"])) == Decimal("37000.5")
        assert Decimal(str(fetched["pnl"])) == Decimal("249.875")
        assert fetched["opened_at"].tzinfo is not None  # timestamptz
        assert fetched["closed_at"].tzinfo is not None

        await crud_backtest_trades.db_delete(db=db, id=trade_id)

    await async_engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
