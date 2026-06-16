"""卡 #20 (W1) — backtest_run 狀態回寫(engine.control.status_writer)。

worker 用 app 級 SQLAlchemy(非手動 psql;鐵律 2 精神)回寫 backtest_run 的
status 流轉與結果指標。只連 localhost(鐵律 4)。

行為層測試:
- ``backtest_run_db_url`` 由 env 組 async DSN,預設 localhost(鐵律 4)。
- ``StatusWriter.mark_*`` 透過 public interface 改 run 的 status —— 用真 localhost
  Postgres round-trip 驗證(opt-in RUN_DB_TESTS=1;CI 無 DB 時跳過)。
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from jimq_engine.control.status_writer import StatusWriter, backtest_run_db_url


def test_db_url_defaults_localhost():
    url = backtest_run_db_url(env={})
    assert "localhost" in url
    assert url.startswith("postgresql+asyncpg://")


def test_db_url_honours_env_overrides():
    url = backtest_run_db_url(
        env={
            "POSTGRES_USER": "u",
            "POSTGRES_PASSWORD": "p",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "jimq",
        }
    )
    assert url == "postgresql+asyncpg://u:p@localhost:5432/jimq"


pytestmark_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)


@pytestmark_db
async def test_status_transitions_roundtrip_against_localhost_db():
    """建一筆 PENDING run,mark_running -> mark_completed,DB 端可讀到流轉。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    url = backtest_run_db_url()
    engine = create_async_engine(url)
    writer = StatusWriter(url)
    try:
        # 直接以 SQLAlchemy Core 插一筆 PENDING run(app 級寫入,非 psql)。
        async with engine.begin() as conn:
            res = await conn.execute(
                sa.text(
                    "INSERT INTO backtest_run "
                    "(strategy_name, instrument_id, bar_type, timeframe, "
                    " start_time, end_time, params, status, created_at) "
                    "VALUES (:s, :i, :b, :t, now(), now(), '{}'::jsonb, 'PENDING', now()) "
                    "RETURNING id"
                ),
                {
                    "s": "ema_cross",
                    "i": "BTCUSDT-PERP.BINANCE",
                    "b": "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
                    "t": "1m",
                },
            )
            run_id = res.scalar_one()

        await writer.mark_running(run_id)
        async with engine.connect() as conn:
            status = (
                await conn.execute(
                    sa.text("SELECT status FROM backtest_run WHERE id=:id"),
                    {"id": run_id},
                )
            ).scalar_one()
        assert status == "RUNNING"

        await writer.mark_completed(
            run_id,
            metrics={"num_trades": 3, "final_balance": Decimal("1000001.5")},
        )
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    sa.text(
                        "SELECT status, num_trades, final_balance "
                        "FROM backtest_run WHERE id=:id"
                    ),
                    {"id": run_id},
                )
            ).one()
        assert row.status == "COMPLETED"
        assert row.num_trades == 3
        assert Decimal(row.final_balance) == Decimal("1000001.5")

        # 清理測試列。
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM backtest_run WHERE id=:id"), {"id": run_id}
            )
    finally:
        await writer.aclose()
        await engine.dispose()


@pytestmark_db
async def test_mark_failed_sets_failed_status():
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    url = backtest_run_db_url()
    engine = create_async_engine(url)
    writer = StatusWriter(url)
    try:
        async with engine.begin() as conn:
            run_id = (
                await conn.execute(
                    sa.text(
                        "INSERT INTO backtest_run "
                        "(strategy_name, instrument_id, bar_type, timeframe, "
                        " start_time, end_time, params, status, created_at) "
                        "VALUES ('ema_cross','BTCUSDT-PERP.BINANCE',"
                        "'BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL','1m',"
                        "now(),now(),'{}'::jsonb,'PENDING',now()) RETURNING id"
                    )
                )
            ).scalar_one()
        await writer.mark_failed(run_id)
        async with engine.connect() as conn:
            status = (
                await conn.execute(
                    sa.text("SELECT status FROM backtest_run WHERE id=:id"),
                    {"id": run_id},
                )
            ).scalar_one()
        assert status == "FAILED"
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM backtest_run WHERE id=:id"), {"id": run_id}
            )
    finally:
        await writer.aclose()
        await engine.dispose()
