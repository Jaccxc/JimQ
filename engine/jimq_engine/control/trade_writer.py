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
    if trades:
        return trades

    # 退路:NETTING OMS 下整個 instrument 只有一個永不歸零的 position →
    # positions_closed() 為空,即使中途進出數百次。改從 fill 流重建 round-trip,
    # 讓進出場 marker + 權益曲線不再是空的(這是「無權益曲線」的根因)。
    return _round_trips_from_engine_fills(engine, run_id=run_id)


def _fill_sort_key(f: Any) -> int:
    return int(getattr(f, "ts_event", 0))


def round_trips_from_fills(
    fills: Sequence[Any], *, instrument_id: str, run_id: int
) -> list[dict[str, Any]]:
    """從**有序 fill 流**重建 round-trip 成交(NETTING 單一部位永不歸零時用)。

    NETTING OMS 下整個 instrument 只有一個 position 物件,跑完常仍持倉 →
    ``positions_closed()`` 為空,即使中途進出數百次。此處改以 fill 流還原:

    - 追蹤帶號淨部位(多 +、空 -)。淨部位由平倉(歸零)或反手(穿越零點)時,
      把該段切成一筆 round-trip,實現 PnL = (出場均價 - 進場均價) * 量 * 方向號。
    - 進場以量加權均價;反手時超出歸零的剩餘量開新反向 round-trip。
    - 跑完仍持倉的尾段也輸出一筆(exit=最後 fill 價,pnl=0)使進場 marker 不漏。

    PnL 不含手續費(權益曲線近似;成交價差為主訊號)。價量以 ``str`` 化交給
    Numeric 欄位(避免 float 精度)。
    """
    ordered = sorted(fills, key=_fill_sort_key)
    trades: list[dict[str, Any]] = []

    # 目前 round-trip 狀態(None = flat)。
    net = Decimal("0")  # 帶號淨部位
    entry_notional = Decimal("0")  # 進場量加權名目(abs)
    entry_qty = Decimal("0")  # 進場累計量(abs)
    exit_notional = Decimal("0")  # 平倉量加權名目(abs)
    exit_qty = Decimal("0")  # 平倉累計量(abs)
    opened_ns: int | None = None
    last_ns: int = 0

    def _flush(closed_ns: int) -> None:
        nonlocal net, entry_notional, entry_qty, exit_notional, exit_qty, opened_ns
        if entry_qty == 0 or opened_ns is None:
            net = Decimal("0")
            entry_notional = entry_qty = exit_notional = exit_qty = Decimal("0")
            opened_ns = None
            return
        side = SIDE_LONG if net_sign_at_open > 0 else SIDE_SHORT
        entry_px = entry_notional / entry_qty
        if exit_qty > 0:
            exit_px = exit_notional / exit_qty
            direction = Decimal("1") if side == SIDE_LONG else Decimal("-1")
            pnl = (exit_px - entry_px) * exit_qty * direction
        else:
            exit_px = entry_px  # 未平倉尾段:以進場價當出場(pnl=0)。
            pnl = Decimal("0")
        trades.append(
            {
                "run_id": run_id,
                "instrument_id": instrument_id,
                "side": side,
                "entry_price": str(entry_px),
                "exit_price": str(exit_px),
                "quantity": str(entry_qty),
                "sl": None,
                "tp": None,
                "pnl": str(pnl),
                "opened_at": _ns_to_dt(opened_ns),
                "closed_at": _ns_to_dt(closed_ns),
            }
        )
        net = Decimal("0")
        entry_notional = entry_qty = exit_notional = exit_qty = Decimal("0")
        opened_ns = None

    net_sign_at_open = 0
    for f in ordered:
        qty = Decimal(str(f.last_qty))
        px = Decimal(str(f.last_px))
        ts = int(getattr(f, "ts_event", 0))
        last_ns = ts
        signed = qty if getattr(f, "is_buy", False) else -qty

        if net == 0:
            # 開新 round-trip。
            net = signed
            net_sign_at_open = 1 if signed > 0 else -1
            entry_notional = px * qty
            entry_qty = qty
            opened_ns = ts
            continue

        same_dir = (net > 0 and signed > 0) or (net < 0 and signed < 0)
        if same_dir:
            net += signed
            entry_notional += px * qty
            entry_qty += qty
            continue

        # 反方向:平倉(可能歸零或反手)。
        closing = min(qty, abs(net))
        exit_notional += px * closing
        exit_qty += closing
        new_net = net + signed
        if new_net == 0:
            _flush(ts)
        elif (new_net > 0) != (net > 0):
            # 反手:先收尾舊段,剩餘量開新反向段。
            _flush(ts)
            remainder = abs(new_net)
            net = new_net
            net_sign_at_open = 1 if new_net > 0 else -1
            entry_notional = px * remainder
            entry_qty = remainder
            opened_ns = ts
        else:
            net = new_net  # 部分平倉,仍同向持倉。

    if entry_qty > 0 and opened_ns is not None:
        _flush(last_ns)
    return trades


def _round_trips_from_engine_fills(engine: Any, *, run_id: int) -> list[dict[str, Any]]:
    """從引擎 cache 的所有 OrderFilled 事件(依 instrument 分組)重建 round-trip。

    供 NETTING 退路:positions_closed() 為空但確有成交時,從 fill 流還原進出場。
    """
    cache = engine.cache
    fills_by_instrument: dict[str, list[Any]] = {}
    try:
        orders = cache.orders()
    except Exception:  # noqa: BLE001
        return []
    for order in orders:
        for ev in getattr(order, "events", []):
            if type(ev).__name__ != "OrderFilled":
                continue
            iid = str(getattr(ev, "instrument_id", ""))
            fills_by_instrument.setdefault(iid, []).append(ev)

    trades: list[dict[str, Any]] = []
    for iid, fills in fills_by_instrument.items():
        trades.extend(round_trips_from_fills(fills, instrument_id=iid, run_id=run_id))
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
