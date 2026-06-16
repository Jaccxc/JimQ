"""``backtest_trade`` — per-run executed trades (卡 #21 W2).

Each row is one closed round-trip trade (entry → exit) from a backtest run,
normalised per DEV_CONTRACT_AFK:
- ``run_id`` relates the trade to its :class:`BacktestRun` as a **plain indexed
  column with no foreign key** (鐵律 12); referential integrity is maintained in
  the application layer;
- ``side`` is a VARCHAR(32) carrying an uppercase contract literal (LONG/SHORT),
  with the enum constraint enforced in the application layer via a
  ``TypeDecorator`` — no DB-native enum (鐵律 11);
- prices / quantity / pnl are ``NUMERIC`` and ``opened_at`` / ``closed_at`` are
  ``timestamptz`` (鐵律 10); ``sl`` / ``tp`` are nullable (a trade may have no
  bracket SL/TP).
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class TradeSide(str, enum.Enum):
    """Direction of a closed trade (uppercase contract literals)."""

    LONG = "LONG"
    SHORT = "SHORT"


class TradeSideType(TypeDecorator):
    """Persist :class:`TradeSide` as a plain ``VARCHAR(32)``.

    Application-layer enum constraint (鐵律 11): no ``CREATE TYPE`` is ever
    emitted; the DB sees only uppercase string literals.
    """

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, TradeSide):
            return value.value
        return TradeSide(value).value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return TradeSide(value)


class BacktestTrade(Base):
    __tablename__ = "backtest_trade"

    id: Mapped[int] = mapped_column(
        "id", Integer, autoincrement=True, primary_key=True, init=False
    )

    # --- relation to backtest_run: plain indexed column, NO foreign key (鐵律 12) ---
    run_id: Mapped[int] = mapped_column(Integer, index=True)

    instrument_id: Mapped[str] = mapped_column(String(64), index=True)

    # --- side: app-layer enum stored as VARCHAR(32) (鐵律 11) ---
    side: Mapped[TradeSide] = mapped_column(TradeSideType())

    # --- prices / quantity / pnl: NUMERIC (鐵律 10) ---
    entry_price: Mapped[float] = mapped_column(Numeric(30, 8))
    exit_price: Mapped[float] = mapped_column(Numeric(30, 8))
    quantity: Mapped[float] = mapped_column(Numeric(30, 8))

    # --- timestamps (timestamptz) ---
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # --- nullable trailing columns (MappedAsDataclass: defaults must come last) ---
    # bracket stop-loss / take-profit: nullable (策略可能無 bracket)
    sl: Mapped[float | None] = mapped_column(Numeric(30, 8), default=None)
    tp: Mapped[float | None] = mapped_column(Numeric(30, 8), default=None)
    pnl: Mapped[float | None] = mapped_column(Numeric(30, 8), default=None)
