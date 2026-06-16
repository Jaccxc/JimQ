"""卡 #21 (W2) — GET /api/v1/backtests/{id}/trades endpoint.

Behaviour:
- the route is registered under /api/v1 and appears in OpenAPI;
- it returns the trades for a given run_id as a list of BacktestTradeRead
  (live round-trip opt-in via RUN_DB_TESTS=1: seed two runs' trades, assert the
  endpoint returns only the requested run's trades, ordered by opened_at).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_trades_route_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/backtests/{backtest_id}/trades" in paths
    assert "get" in paths["/api/v1/backtests/{backtest_id}/trades"]


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)
def test_trades_endpoint_returns_only_that_runs_trades():
    from app.core.db.database import local_session
    from app.crud.crud_backtest_trade import crud_backtest_trades
    from app.models.backtest_trade import TradeSide
    from app.schemas.backtest_trade import BacktestTradeCreate
    import anyio

    run_a = 910_000_001
    run_b = 910_000_002

    async def _seed():
        async with local_session() as db:
            for run_id, n, side in ((run_a, 2, TradeSide.LONG), (run_b, 1, TradeSide.SHORT)):
                for i in range(n):
                    await crud_backtest_trades.create(
                        db=db,
                        object=BacktestTradeCreate(
                            run_id=run_id,
                            instrument_id="BTCUSDT-PERP.BINANCE",
                            side=side,
                            entry_price=Decimal("37000") + i,
                            exit_price=Decimal("37100") + i,
                            quantity=Decimal("0.1"),
                            pnl=Decimal("10"),
                            opened_at=datetime(2024, 1, 1, i, tzinfo=UTC),
                            closed_at=datetime(2024, 1, 1, i + 1, tzinfo=UTC),
                        ),
                    )

    async def _cleanup():
        import sqlalchemy as sa
        from app.core.db.database import async_engine

        async with async_engine.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM backtest_trade WHERE run_id = ANY(:r)"),
                {"r": [run_a, run_b]},
            )
        await async_engine.dispose()

    anyio.run(_seed)
    try:
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/backtests/{run_a}/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2
        assert {t["run_id"] for t in body} == {run_a}
        assert all(t["side"] == "LONG" for t in body)
        # ordered by opened_at ascending
        times = [t["opened_at"] for t in body]
        assert times == sorted(times)
    finally:
        anyio.run(_cleanup)
