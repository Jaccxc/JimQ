"""create backtest_trade

Revision ID: d9b310772509
Revises: c687654fee3c
Create Date: 2026-06-16 17:25:47.861251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9b310772509'
down_revision: Union[str, None] = 'c687654fee3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# HAND-WRITTEN migration (DEV_CONTRACT_AFK 鐵律 2 — never --autogenerate).
# 卡 #21 (W2):per-run 成交持久化表。
# - ``run_id`` 關聯 backtest_run,但**無外鍵**;純索引欄,一致性由應用層維護(鐵律 12)。
# - ``side`` 為 VARCHAR(32) 大寫契約字面值(LONG/SHORT),無 DB-native enum(鐵律 11)。
# - 價量/pnl 用 NUMERIC;``opened_at``/``closed_at`` 用 timestamptz(鐵律 10)。
# - ``sl``/``tp``/``pnl`` 可為 NULL(策略可能無 bracket SL/TP)。


def upgrade() -> None:
    op.create_table(
        "backtest_trade",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # relation to backtest_run: plain indexed column, NO foreign key (鐵律 12)
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.String(length=64), nullable=False),
        # application-layer enum stored as VARCHAR(32) (no DB-native enum)
        sa.Column("side", sa.String(length=32), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("sl", sa.Numeric(precision=30, scale=8), nullable=True),
        sa.Column("tp", sa.Numeric(precision=30, scale=8), nullable=True),
        sa.Column("pnl", sa.Numeric(precision=30, scale=8), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # no ForeignKeyConstraint (鐵律 12)
    )
    op.create_index("ix_backtest_trade_run_id", "backtest_trade", ["run_id"])
    op.create_index(
        "ix_backtest_trade_instrument_id", "backtest_trade", ["instrument_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_trade_instrument_id", table_name="backtest_trade")
    op.drop_index("ix_backtest_trade_run_id", table_name="backtest_trade")
    op.drop_table("backtest_trade")
