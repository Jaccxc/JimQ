"""``backtest_run`` — first JimQ application data model.

Records one backtest execution and its result metrics. Modelled on the
boilerplate ``post`` template but normalised per DEV_CONTRACT_AFK:
- structured fields are first-class columns; only the strategy's arbitrary
  parameters live in JSONB (鐵律 10);
- ``status`` is a VARCHAR(32) carrying an uppercase contract literal, with the
  enum constraint enforced in the application layer via a ``TypeDecorator``
  (no DB-native enum — 鐵律 11);
- no foreign keys — relations are plain indexed columns (鐵律 12);
- all timestamps are ``timestamptz`` and money/ratios are ``NUMERIC`` (鐵律 10).
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class BacktestStatus(str, enum.Enum):
    """Lifecycle of a backtest run (uppercase contract literals)."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BacktestStatusType(TypeDecorator):
    """Persist :class:`BacktestStatus` as a plain ``VARCHAR(32)``.

    Application-layer enum constraint (鐵律 11): no ``CREATE TYPE`` is ever
    emitted; the DB sees only uppercase string literals.
    """

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, BacktestStatus):
            return value.value
        # accept the raw uppercase literal too (validate membership)
        return BacktestStatus(value).value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return BacktestStatus(value)


class BacktestRun(Base):
    __tablename__ = "backtest_run"

    id: Mapped[int] = mapped_column(
        "id", Integer, autoincrement=True, primary_key=True, init=False
    )

    # --- run definition (structured, normalised) ---
    strategy_name: Mapped[str] = mapped_column(String(128), index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True)  # e.g. BTCUSDT-PERP.BINANCE
    bar_type: Mapped[str] = mapped_column(String(128))
    timeframe: Mapped[str] = mapped_column(String(32))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # --- grid cohort tag: groups all runs from one param-grid batch (鐵律 12: ---
    # plain indexed column, no FK; NULL for single runs). #15.
    run_group: Mapped[str | None] = mapped_column(String(64), default=None, index=True)

    # --- strategy parameters: genuinely unstructured payload -> JSONB (鐵律 10) ---
    params: Mapped[dict] = mapped_column(JSONB, default_factory=dict)

    # --- status: app-layer enum stored as VARCHAR(32) (鐵律 11) ---
    status: Mapped[BacktestStatus] = mapped_column(
        BacktestStatusType(), default=BacktestStatus.PENDING, index=True
    )

    # --- result metrics: structured first-class columns, nullable until done ---
    total_return: Mapped[float | None] = mapped_column(Numeric(20, 8), default=None)
    sharpe: Mapped[float | None] = mapped_column(Numeric(20, 8), default=None)
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(20, 8), default=None)
    num_trades: Mapped[int | None] = mapped_column(BigInteger, default=None)
    final_balance: Mapped[float | None] = mapped_column(Numeric(30, 8), default=None)

    # --- timestamps (timestamptz) ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, onupdate=lambda: datetime.now(UTC)
    )
