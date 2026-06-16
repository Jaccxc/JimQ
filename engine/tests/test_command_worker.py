"""卡 #20 (W1) — engine command worker(engine.control.worker)。

行為層測試(public interface):
- ``parse_command_entry``:把 Redis command stream 的一筆 entry(``command_type``
  + JSON ``payload``)解析回 ``RunBacktestCommand``;非 run_backtest / 壞 payload
  回 None(安全略過)。
- ``handle_run_backtest``(整合,opt-in RUN_DB_TESTS+本機 Redis):給一個小區間
  命令 + catalog,跑啟用 Redis Streams 的 backtest → 事件進事件 stream(XLEN>0)
  → backtest_run status=COMPLETED → 發布 latest stream key。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from jimq_core.constants import COMMAND_TYPE_RUN_BACKTEST
from jimq_core.schemas import RunBacktestCommand

from jimq_engine.control.worker import parse_command_entry


def _entry(command_type: str, payload: str) -> tuple[bytes, dict]:
    return (b"0-1", {b"command_type": command_type.encode(), b"payload": payload.encode()})


def _cmd_json(**overrides) -> str:
    base = dict(
        correlation_id="corr-1",
        run_id=1,
        symbol="BTCUSDT-PERP.BINANCE",
        timeframe="1m",
        strategy="ema_cross",
        params={"fast_period": 3, "slow_period": 8},
        start=datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC),
        end=datetime(2023, 11, 14, 23, 13, 20, tzinfo=UTC),
    )
    base.update(overrides)
    return RunBacktestCommand(**base).model_dump_json()


def test_parse_valid_run_backtest_entry():
    cmd = parse_command_entry(_entry(COMMAND_TYPE_RUN_BACKTEST, _cmd_json()))
    assert isinstance(cmd, RunBacktestCommand)
    assert cmd.run_id == 1
    assert cmd.strategy == "ema_cross"


def test_parse_ignores_unknown_command_type():
    assert parse_command_entry(_entry("SOMETHING_ELSE", _cmd_json())) is None


def test_parse_ignores_bad_payload():
    assert parse_command_entry(_entry(COMMAND_TYPE_RUN_BACKTEST, "not-json")) is None


# --- 整合:真的跑一個小 backtest 經 worker handler ---------------------------

_DB_AND_REDIS = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 (需本機 Postgres + Redis) to run the worker integration",
)


@_DB_AND_REDIS
async def test_handle_run_backtest_runs_streams_and_completes(tmp_path):
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    import redis as redis_sync
    from nautilus_trader.persistence.catalog import ParquetDataCatalog

    from jimq_core.constants import REDIS_BUS_DB
    from jimq_engine.catalog.ingest import BAR_TYPE_1M, ingest_bars
    from jimq_engine.catalog.instruments import btcusdt_perp_binance
    from jimq_engine.control.status_writer import StatusWriter, backtest_run_db_url
    from jimq_engine.control.worker import handle_run_backtest

    # 1) 準備一段合成黃金交叉 bars 進 catalog。
    catalog = ParquetDataCatalog(path=str(tmp_path / "catalog"))
    instrument = btcusdt_perp_binance()
    catalog.write_data([instrument])
    base = 1_700_000_000_000
    down = [40000.0 - i * 20 for i in range(15)]
    up = [down[-1] + i * 120 for i in range(1, 20)]
    klines = []
    for i, p in enumerate(down + up):
        ot = base + i * 60_000
        klines.append([ot, f"{p}", f"{p+5}", f"{p-5}", f"{p}", "10.000", ot + 59_999, "0", 1, "0", "0", "0"])
    ingest_bars(catalog, klines, instrument)

    # 2) 建一筆 PENDING run。
    db_url = backtest_run_db_url()
    db = create_async_engine(db_url)
    async with db.begin() as conn:
        run_id = (
            await conn.execute(
                sa.text(
                    "INSERT INTO backtest_run "
                    "(strategy_name,instrument_id,bar_type,timeframe,start_time,end_time,"
                    " params,status,created_at) VALUES "
                    "('ema_cross','BTCUSDT-PERP.BINANCE',"
                    "'BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL','1m',now(),now(),"
                    "'{}'::jsonb,'PENDING',now()) RETURNING id"
                )
            )
        ).scalar_one()

    cmd = RunBacktestCommand(
        correlation_id="corr-int",
        run_id=run_id,
        symbol="BTCUSDT-PERP.BINANCE",
        timeframe="1m",
        strategy="ema_cross",
        params={"fast_period": 3, "slow_period": 8},
        start=datetime(2023, 11, 14, 0, 0, tzinfo=UTC),
        end=datetime(2023, 11, 15, 0, 0, tzinfo=UTC),
    )

    from jimq_engine.control.trade_writer import TradeWriter

    writer = StatusWriter(db_url)
    trade_writer = TradeWriter(db_url)
    rclient = redis_sync.Redis(host="localhost", port=6379, db=REDIS_BUS_DB)
    try:
        stream_key = await handle_run_backtest(
            cmd,
            writer=writer,
            catalog=catalog,
            redis_client=rclient,
            trade_writer=trade_writer,
        )
        # 事件進事件 stream。
        import time

        for _ in range(50):
            if rclient.exists(stream_key) and rclient.xlen(stream_key) > 0:
                break
            time.sleep(0.05)
        assert rclient.xlen(stream_key) > 0
        # status=COMPLETED。
        async with db.connect() as conn:
            status = (
                await conn.execute(
                    sa.text("SELECT status FROM backtest_run WHERE id=:id"), {"id": run_id}
                )
            ).scalar_one()
        assert status == "COMPLETED"
        # 卡 #21:跑完把成交寫入 backtest_trade(此合成黃金交叉應至少成交一筆)。
        async with db.connect() as conn:
            n_trades = (
                await conn.execute(
                    sa.text("SELECT count(*) FROM backtest_trade WHERE run_id=:id"),
                    {"id": run_id},
                )
            ).scalar_one()
        assert n_trades >= 1
    finally:
        rclient.delete(stream_key)
        async with db.begin() as conn:
            await conn.execute(sa.text("DELETE FROM backtest_trade WHERE run_id=:id"), {"id": run_id})
            await conn.execute(sa.text("DELETE FROM backtest_run WHERE id=:id"), {"id": run_id})
        await writer.aclose()
        await trade_writer.aclose()
        rclient.close()
        await db.dispose()
