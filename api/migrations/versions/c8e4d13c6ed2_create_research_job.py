"""create research_job

Revision ID: c8e4d13c6ed2
Revises: d9b310772509
Create Date: 2026-06-16 18:48:14.880916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c8e4d13c6ed2'
down_revision: Union[str, None] = 'd9b310772509'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# HAND-WRITTEN migration (DEV_CONTRACT_AFK 鐵律 2 — never --autogenerate).
# 卡 #23 (W4):web 觸發的研究 job(dataset build / 模型訓練)。
# - job_type / status 為純 VARCHAR(32),帶大寫 app-enum 字面值;無 DB-native enum
#   / CREATE TYPE(鐵律 11)。
# - job 參數 / 結果為本質非結構化 payload → JSONB(鐵律 10)。
# - 無外鍵;correlation_id 為純索引欄,一致性由應用層維護(鐵律 12)。
# - timestamptz(鐵律 10)。


def upgrade() -> None:
    op.create_table(
        "research_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # application-layer enum stored as VARCHAR(32) (no DB-native enum)
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # no ForeignKeyConstraint (鐵律 12)
    )
    op.create_index("ix_research_job_job_type", "research_job", ["job_type"])
    op.create_index("ix_research_job_correlation_id", "research_job", ["correlation_id"])
    op.create_index("ix_research_job_status", "research_job", ["status"])


def downgrade() -> None:
    op.drop_index("ix_research_job_status", table_name="research_job")
    op.drop_index("ix_research_job_correlation_id", table_name="research_job")
    op.drop_index("ix_research_job_job_type", table_name="research_job")
    op.drop_table("research_job")
