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

from jimq_engine.control.trade_writer import extract_trades, round_trips_from_fills

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


# --- 從 fill 流重建 round-trip(NETTING:單一 position 永不歸零的情況)----------


class _FakeFill:
    """模擬 Nautilus OrderFilled:last_px / last_qty / is_buy / ts_event。"""

    def __init__(self, *, is_buy, last_px, last_qty, ts_event):
        self.is_buy = is_buy
        self.is_sell = not is_buy
        self.last_px = last_px
        self.last_qty = last_qty
        self.ts_event = ts_event


def test_round_trips_long_then_flat():
    # buy 1 @100(開多)→ sell 1 @110(平多歸零)= 一筆 LONG round-trip,pnl=+10。
    fills = [
        _FakeFill(is_buy=True, last_px=100.0, last_qty=1.0, ts_event=_ns(datetime(2024, 1, 1, 0, 0, tzinfo=UTC))),
        _FakeFill(is_buy=False, last_px=110.0, last_qty=1.0, ts_event=_ns(datetime(2024, 1, 1, 1, 0, tzinfo=UTC))),
    ]
    trips = round_trips_from_fills(fills, instrument_id="BTCUSDT-PERP.BINANCE", run_id=9)
    assert len(trips) == 1
    t = trips[0]
    assert t["side"] == "LONG"
    assert Decimal(str(t["entry_price"])) == Decimal("100.0")
    assert Decimal(str(t["exit_price"])) == Decimal("110.0")
    assert Decimal(str(t["quantity"])) == Decimal("1.0")
    assert Decimal(str(t["pnl"])) == Decimal("10.0")
    assert t["run_id"] == 9


def test_round_trips_flip_long_to_short_splits_into_two():
    # buy 1 @100(開多)→ sell 2 @120(平多 +20 並反手做空 1)→ buy 1 @115(平空 +5)。
    fills = [
        _FakeFill(is_buy=True, last_px=100.0, last_qty=1.0, ts_event=1),
        _FakeFill(is_buy=False, last_px=120.0, last_qty=2.0, ts_event=2),
        _FakeFill(is_buy=True, last_px=115.0, last_qty=1.0, ts_event=3),
    ]
    trips = round_trips_from_fills(fills, instrument_id="X", run_id=1)
    assert len(trips) == 2
    long_t, short_t = trips
    assert long_t["side"] == "LONG"
    assert Decimal(str(long_t["pnl"])) == Decimal("20.0")  # (120-100)*1
    assert short_t["side"] == "SHORT"
    assert Decimal(str(short_t["quantity"])) == Decimal("1.0")
    assert Decimal(str(short_t["pnl"])) == Decimal("5.0")  # (120-115)*1 short


def test_round_trips_reversal_chain_per_trade_entry_differs_from_exit():
    """還原 run #94 的 always-in-market 反手鏈:重現使用者「同價卻有 PnL」回報。

    根因:策略持續反手 → 第 N 筆的**出場價 = 第 N+1 筆的進場價**(同一根反手 fill)。
    那是兩筆不同 trade 的邊界價,**非同一筆**的進出同價。本測試斷言:
      1. 每一筆 trade 自身的 entry_price ≠ exit_price(除尾段未平倉)。
      2. 每一筆的 pnl 號與 (exit-entry)×方向 一致(SHORT 進<出 → 負)。
      3. 相鄰兩筆的「前者 exit = 後者 entry」(這正是使用者看到的「同價」來源)。
    """
    # 取 run #94 前三筆的價格鏈:42494.1 → 42542.3 → 42471.7 → 42447.0,持續反手。
    fills = [
        _FakeFill(is_buy=False, last_px=42494.1, last_qty=0.1, ts_event=1),  # 開空
        _FakeFill(is_buy=True, last_px=42542.3, last_qty=0.2, ts_event=2),   # 平空(虧)+反手做多
        _FakeFill(is_buy=False, last_px=42471.7, last_qty=0.2, ts_event=3),  # 平多(虧)+反手做空
        _FakeFill(is_buy=True, last_px=42447.0, last_qty=0.1, ts_event=4),   # 平空(賺)歸零
    ]
    trips = round_trips_from_fills(fills, instrument_id="BTCUSDT-PERP.BINANCE", run_id=94)
    assert len(trips) == 3

    for t in trips:
        entry = Decimal(str(t["entry_price"]))
        exit_ = Decimal(str(t["exit_price"]))
        pnl = Decimal(str(t["pnl"]))
        # (1) 同一筆進出價不同。
        assert entry != exit_, f"同一筆 entry==exit:{t}"
        # (2) pnl 號與方向一致。
        direction = Decimal("1") if t["side"] == "LONG" else Decimal("-1")
        expected_sign_pnl = (exit_ - entry) * direction
        assert (pnl > 0) == (expected_sign_pnl > 0)
        assert (pnl < 0) == (expected_sign_pnl < 0)

    # (3) 相鄰邊界:前者 exit_price == 後者 entry_price(使用者看到的「同價」實為此)。
    for a, b in zip(trips, trips[1:]):
        assert Decimal(str(a["exit_price"])) == Decimal(str(b["entry_price"]))

    # 第一筆對齊 DB run #94 第 413 列:SHORT 42494.1→42542.3,pnl ≈ -4.82。
    first = trips[0]
    assert first["side"] == "SHORT"
    assert Decimal(str(first["pnl"])) == (
        (Decimal("42494.1") - Decimal("42542.3")) * Decimal("0.1")
    )


def test_round_trips_open_tail_position_is_closed_at_last_fill():
    # buy 1 @100,沒有平倉 fill:回測結束仍持倉。仍輸出一筆(exit=最後 fill 價,
    # 標記未實現以最後價估;pnl=0,確保權益曲線不漏掉進場 marker)。
    fills = [_FakeFill(is_buy=True, last_px=100.0, last_qty=1.0, ts_event=5)]
    trips = round_trips_from_fills(fills, instrument_id="X", run_id=1)
    assert len(trips) == 1
    assert trips[0]["side"] == "LONG"
    assert Decimal(str(trips[0]["quantity"])) == Decimal("1.0")


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
