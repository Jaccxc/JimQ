"""create backtest_run

Revision ID: 3a154611ac4e
Revises: 
Create Date: 2026-06-16 03:20:50.103576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3a154611ac4e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# HAND-WRITTEN migration (DEV_CONTRACT_AFK 鐵律 2 — never --autogenerate).
# - status is a plain VARCHAR(32) carrying an uppercase app-enum literal; no
#   DB-native enum / CREATE TYPE (鐵律 11).
# - no foreign keys; relations are plain indexed columns (鐵律 12).
# - timestamptz + NUMERIC for precise money/ratios (鐵律 10).


def upgrade() -> None:
    op.create_table(
        "backtest_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_name", sa.String(length=128), nullable=False),
        sa.Column("instrument_id", sa.String(length=64), nullable=False),
        sa.Column("bar_type", sa.String(length=128), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # application-layer enum stored as VARCHAR(32) (no DB-native enum)
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_return", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("sharpe", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("num_trades", sa.BigInteger(), nullable=True),
        sa.Column("final_balance", sa.Numeric(precision=30, scale=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # no ForeignKeyConstraint (鐵律 12)
    )
    op.create_index("ix_backtest_run_strategy_name", "backtest_run", ["strategy_name"])
    op.create_index("ix_backtest_run_instrument_id", "backtest_run", ["instrument_id"])
    op.create_index("ix_backtest_run_status", "backtest_run", ["status"])


def downgrade() -> None:
    op.drop_index("ix_backtest_run_status", table_name="backtest_run")
    op.drop_index("ix_backtest_run_instrument_id", table_name="backtest_run")
    op.drop_index("ix_backtest_run_strategy_name", table_name="backtest_run")
    op.drop_table("backtest_run")
