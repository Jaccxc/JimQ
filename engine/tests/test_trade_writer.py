"""卡 #21 (W2) — backtest 成交抽取 + 持久化(engine.control.trade_writer)。

行為層測試(public interface):
- ``extract_trades``:把跑完引擎的 closed positions 映射成正規化成交 dict
  (run_id、side LONG/SHORT、entry/exit price、qty、sl/tp、pnl、opened/closed_at);
  SL/TP 從該部位的 bracket 子單(STOP/LIMIT)抽,無 bracket → None。
- ``TradeWriter.write_trades``:app 級 SQLAlchemy 把成交 bulk-insert 到
  backtest_trade(真 localhost Postgres round-trip;opt-in RUN_DB_TESTS=1)。

只連 localhost(鐵律 4);無 FK / VARCHAR enum / NUMERIC / timestamptz(鐵律 10/11/12)。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from jimq_engine.control.trade_writer import extract_trades

_NS_PER_SEC = 1_000_000_000


# --- 純抽取:用最小 fake 引擎/cache 驗映射(不需真 DB / Nautilus run) ---------


class _FakeOrder:
    def __init__(self, order_type, *, trigger_price=None, price=None):
        self.order_type = order_type
        self.trigger_price = trigger_price
        self.price = price


class _FakePosition:
    def __init__(
        self,
        *,
        position_id,
        instrument_id,
        side,
        avg_px_open,
        avg_px_close,
        peak_qty,
        realized_pnl,
        ts_opened,
        ts_closed,
    ):
        self.id = position_id
        self.instrument_id = instrument_id
        self.side = side
        self.avg_px_open = avg_px_open
        self.avg_px_close = avg_px_close
        self.peak_qty = peak_qty
        self.realized_pnl = realized_pnl
        self.ts_opened = ts_opened
        self.ts_closed = ts_closed


class _FakeSide:
    """模擬 Nautilus PositionSide:name = LONG/SHORT/FLAT。"""

    def __init__(self, name):
        self.name = name


class _FakeCache:
    def __init__(self, positions, orders_by_pos):
        self._positions = positions
        self._orders_by_pos = orders_by_pos

    def positions_closed(self):
        return self._positions

    def orders_for_position(self, position_id):
        return self._orders_by_pos.get(position_id, [])


class _FakeEngine:
    def __init__(self, cache):
        self.cache = cache


def _ns(dt: datetime) -> int:
    return int(dt.timestamp() * _NS_PER_SEC)


def test_extract_maps_closed_long_position_with_bracket_sl_tp():
    opened = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    closed = datetime(2024, 1, 1, 1, 0, tzinfo=UTC)
    pos = _FakePosition(
        position_id="P-1",
        instrument_id="BTCUSDT-PERP.BINANCE",
        side=_FakeSide("LONG"),
        avg_px_open=37000.5,
        avg_px_close=37500.25,
        peak_qty=0.5,
        realized_pnl=249.875,
        ts_opened=_ns(opened),
        ts_closed=_ns(closed),
    )
    # bracket 子單:STOP_MARKET(SL trigger)+ LIMIT(TP price)。
    orders = [
        _FakeOrder("STOP_MARKET", trigger_price=36630.0),
        _FakeOrder("LIMIT", price=37740.0),
    ]
    engine = _FakeEngine(_FakeCache([pos], {"P-1": orders}))

    trades = extract_trades(engine, run_id=42)

    assert len(trades) == 1
    t = trades[0]
    assert t["run_id"] == 42
    assert t["instrument_id"] == "BTCUSDT-PERP.BINANCE"
    assert t["side"] == "LONG"
    assert Decimal(str(t["entry_price"])) == Decimal("37000.5")
    assert Decimal(str(t["exit_price"])) == Decimal("37500.25")
    assert Decimal(str(t["quantity"])) == Decimal("0.5")
    assert Decimal(str(t["sl"])) == Decimal("36630.0")
    assert Decimal(str(t["tp"])) == Decimal("37740.0")
    assert Decimal(str(t["pnl"])) == Decimal("249.875")
    assert t["opened_at"] == opened
    assert t["closed_at"] == closed


def test_extract_handles_no_bracket_orders_as_null_sl_tp():
    pos = _FakePosition(
        position_id="P-2",
        instrument_id="BTCUSDT-PERP.BINANCE",
        side=_FakeSide("SHORT"),
        avg_px_open=40000.0,
        avg_px_close=39500.0,
        peak_qty=1.0,
        realized_pnl=500.0,
        ts_opened=_ns(datetime(2024, 1, 2, tzinfo=UTC)),
        ts_closed=_ns(datetime(2024, 1, 2, 1, tzinfo=UTC)),
    )
    engine = _FakeEngine(_FakeCache([pos], {}))  # 無 bracket 子單

    trades = extract_trades(engine, run_id=7)
    assert len(trades) == 1
    assert trades[0]["side"] == "SHORT"
    assert trades[0]["sl"] is None
    assert trades[0]["tp"] is None


# --- DB round-trip:TradeWriter 寫入後可讀回(opt-in)--------------------------

_DB = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)


@_DB
async def test_trade_writer_persists_trades_roundtrip():
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from jimq_engine.control.status_writer import backtest_run_db_url
    from jimq_engine.control.trade_writer import TradeWriter

    url = backtest_run_db_url()
    db = create_async_engine(url)
    writer = TradeWriter(url)
    run_id = 555_000_001
    try:
        trades = [
            {
                "run_id": run_id,
                "instrument_id": "BTCUSDT-PERP.BINANCE",
                "side": "LONG",
                "entry_price": Decimal("37000.5"),
                "exit_price": Decimal("37500.25"),
                "quantity": Decimal("0.5"),
                "sl": Decimal("36630.0"),
                "tp": Decimal("37740.0"),
                "pnl": Decimal("249.875"),
                "opened_at": datetime(2024, 1, 1, tzinfo=UTC),
                "closed_at": datetime(2024, 1, 1, 1, tzinfo=UTC),
            }
        ]
        await writer.write_trades(trades)

        async with db.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT side, entry_price, sl, pnl FROM backtest_trade "
                        "WHERE run_id=:r"
                    ),
                    {"r": run_id},
                )
            ).all()
        assert len(rows) == 1
        assert rows[0][0] == "LONG"
        assert Decimal(str(rows[0][1])) == Decimal("37000.5")
        assert Decimal(str(rows[0][2])) == Decimal("36630.0")
    finally:
        async with db.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM backtest_trade WHERE run_id=:r"), {"r": run_id}
            )
        await writer.aclose()
        await db.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
