"""卡 #21 (W2) — backtest 成交抽取 + 持久化(app 級 SQLAlchemy)。

backtest 跑完後,把引擎 cache 的 **closed positions** 抽成正規化成交(round-trip
trade:進場 → 出場),並用 app 級 SQLAlchemy 寫入 ``backtest_trade`` 表(非手動
psql;鐵律 2 精神)。

設計(本地決策,對齊 W1 status_writer):
- engine 不 import api 套件(避免反向耦合);此處用 SQLAlchemy Core 對
  ``backtest_trade`` 表下精準 ``INSERT``,欄位契約與 api model 對齊
  (side VARCHAR、NUMERIC、timestamptz)。
- ``side`` 以大寫字面值 LONG/SHORT(鐵律 11;對齊 api TradeSide)。
- SL/TP 從該部位的 bracket 子單抽:STOP* 子單的 ``trigger_price`` = SL、
  LIMIT 子單的 ``price`` = TP;無 bracket → NULL。
- 只連 localhost(鐵律 4);async engine 生命週期由 caller 持有。

``extract_trades`` 為純函式(只讀引擎 public cache),可單獨單元測試,不需 DB。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_NS_PER_SEC = 1_000_000_000

# side 契約字面值(對齊 api TradeSide;鐵律 11)。
SIDE_LONG = "LONG"
SIDE_SHORT = "SHORT"

# backtest_trade 表的輕量 Core 定義(欄位契約對齊 api model)。
_metadata = sa.MetaData()
backtest_trade_table = sa.Table(
    "backtest_trade",
    _metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("run_id", sa.Integer),
    sa.Column("instrument_id", sa.String(64)),
    sa.Column("side", sa.String(32)),
    sa.Column("entry_price", sa.Numeric(30, 8)),
    sa.Column("exit_price", sa.Numeric(30, 8)),
    sa.Column("quantity", sa.Numeric(30, 8)),
    sa.Column("sl", sa.Numeric(30, 8)),
    sa.Column("tp", sa.Numeric(30, 8)),
    sa.Column("pnl", sa.Numeric(30, 8)),
    sa.Column("opened_at", sa.DateTime(timezone=True)),
    sa.Column("closed_at", sa.DateTime(timezone=True)),
)

# bracket 子單型別字面值(Nautilus OrderType.name)。
_STOP_TYPES = {"STOP_MARKET", "STOP", "STOP_LIMIT"}
_LIMIT_TYPE = "LIMIT"


def _ns_to_dt(ts_ns: Any) -> datetime:
    return datetime.fromtimestamp(int(ts_ns) / _NS_PER_SEC, tz=UTC)


def _side_literal(position: Any) -> str:
    """Nautilus PositionSide → LONG/SHORT 字面值(其餘視為 LONG fallback)。"""
    name = getattr(getattr(position, "side", None), "name", None)
    return SIDE_SHORT if name == "SHORT" else SIDE_LONG


def _bracket_sl_tp(orders: Sequence[Any]) -> tuple[Any, Any]:
    """從部位的 bracket 子單抽 (sl, tp);無對應子單則為 None。

    STOP* 子單的 ``trigger_price`` = 停損;LIMIT 子單的 ``price`` = 停利。
    """
    sl: Any = None
    tp: Any = None
    for o in orders:
        otype = getattr(o, "order_type", None)
        # order_type 可能是 enum(有 .name)或字串。
        otype_name = getattr(otype, "name", otype)
        if otype_name in _STOP_TYPES:
            trig = getattr(o, "trigger_price", None)
            if trig is not None and sl is None:
                sl = trig
        elif otype_name == _LIMIT_TYPE:
            px = getattr(o, "price", None)
            if px is not None and tp is None:
                tp = px
    return sl, tp


def extract_trades(engine: Any, *, run_id: int) -> list[dict[str, Any]]:
    """把跑完引擎的 closed positions 映射成正規化成交 dict 列表。

    每個 closed position = 一筆 round-trip 成交。SL/TP 從該部位的 bracket 子單抽
    (``cache.orders_for_position``);無 bracket → None。價量/pnl 以 ``str`` 化後
    交給 Numeric 欄位(避免 float 精度;DB 側 NUMERIC)。
    """
    cache = engine.cache
    trades: list[dict[str, Any]] = []
    for pos in cache.positions_closed():
        try:
            orders = cache.orders_for_position(pos.id)
        except Exception:  # noqa: BLE001 — 抽 SL/TP 失敗不應擋成交持久化。
            orders = []
        sl, tp = _bracket_sl_tp(orders)
        trades.append(
            {
                "run_id": run_id,
                "instrument_id": str(pos.instrument_id),
                "side": _side_literal(pos),
                "entry_price": str(pos.avg_px_open),
                "exit_price": str(pos.avg_px_close),
                "quantity": str(pos.peak_qty),
                "sl": None if sl is None else str(sl),
                "tp": None if tp is None else str(tp),
                "pnl": None
                if getattr(pos, "realized_pnl", None) is None
                else str(getattr(pos.realized_pnl, "as_double", lambda: pos.realized_pnl)()),
                "opened_at": _ns_to_dt(pos.ts_opened),
                "closed_at": _ns_to_dt(pos.ts_closed),
            }
        )
    return trades


def _coerce_numeric(value: Any) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


class TradeWriter:
    """以 app 級 SQLAlchemy 把成交 bulk-insert 到 backtest_trade。"""

    def __init__(self, db_url: str, *, engine: AsyncEngine | None = None) -> None:
        self._engine = engine or create_async_engine(db_url)

    async def write_trades(self, trades: Sequence[dict[str, Any]]) -> int:
        """Bulk-insert 成交;回傳寫入筆數。空列表為 no-op。"""
        if not trades:
            return 0
        rows = []
        for t in trades:
            rows.append(
                {
                    "run_id": int(t["run_id"]),
                    "instrument_id": t["instrument_id"],
                    "side": t["side"],
                    "entry_price": _coerce_numeric(t["entry_price"]),
                    "exit_price": _coerce_numeric(t["exit_price"]),
                    "quantity": _coerce_numeric(t["quantity"]),
                    "sl": _coerce_numeric(t.get("sl")),
                    "tp": _coerce_numeric(t.get("tp")),
                    "pnl": _coerce_numeric(t.get("pnl")),
                    "opened_at": t["opened_at"],
                    "closed_at": t["closed_at"],
                }
            )
        async with self._engine.begin() as conn:
            await conn.execute(sa.insert(backtest_trade_table), rows)
        return len(rows)

    async def aclose(self) -> None:
        await self._engine.dispose()
