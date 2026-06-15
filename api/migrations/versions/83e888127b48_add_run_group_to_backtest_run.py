"""add run_group to backtest_run

Revision ID: 83e888127b48
Revises: 3a154611ac4e
Create Date: 2026-06-16 05:43:53.921692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83e888127b48'
down_revision: Union[str, None] = '3a154611ac4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# HAND-WRITTEN migration (DEV_CONTRACT_AFK 鐵律 2 — never --autogenerate).
# 卡 #15:批量 backtest runner 對一次參數網格批跑產出多筆 run。新增
# ``run_group`` VARCHAR(64) 標記同一網格批跑的所有 run(單跑為 NULL),供
# 查詢 / 比較整個 cohort。
# - 列舉/標籤欄位用 VARCHAR,無 DB-native enum(鐵律 11)。
# - 無外鍵;關聯靠純索引欄,一致性由應用層維護(鐵律 12)。


def upgrade() -> None:
    op.add_column(
        "backtest_run",
        sa.Column("run_group", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_backtest_run_run_group", "backtest_run", ["run_group"])


def downgrade() -> None:
    op.drop_index("ix_backtest_run_run_group", table_name="backtest_run")
    op.drop_column("backtest_run", "run_group")
