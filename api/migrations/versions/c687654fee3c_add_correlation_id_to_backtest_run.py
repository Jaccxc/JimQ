"""add correlation_id to backtest_run

Revision ID: c687654fee3c
Revises: 40371f624c3c
Create Date: 2026-06-16 16:56:00.262428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c687654fee3c'
down_revision: Union[str, None] = '40371f624c3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# HAND-WRITTEN migration (DEV_CONTRACT_AFK 鐵律 2 — never --autogenerate).
# 卡 #20 (W1):命令平面 — UI 觸發的 backtest 經 request -> 命令信封 -> run ->
# 事件流;新增 ``correlation_id`` VARCHAR(64) 端到端追蹤 id(供審計),命令平面
# 外建立的 run(#15 grid 批跑 / 直接 CRUD)為 NULL。
# - 列舉/標籤欄位用 VARCHAR,無 DB-native enum(鐵律 11)。
# - 無外鍵;關聯靠純索引欄,一致性由應用層維護(鐵律 12)。


def upgrade() -> None:
    op.add_column(
        "backtest_run",
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_backtest_run_correlation_id", "backtest_run", ["correlation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_run_correlation_id", table_name="backtest_run")
    op.drop_column("backtest_run", "correlation_id")
