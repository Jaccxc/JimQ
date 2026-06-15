"""create model_registry

Revision ID: 40371f624c3c
Revises: 83e888127b48
Create Date: 2026-06-16 06:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '40371f624c3c'
down_revision: Union[str, None] = '83e888127b48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# HAND-WRITTEN migration (DEV_CONTRACT_AFK 鐵律 2 — never --autogenerate).
# 卡 #17:model registry。registered model artifact 的 metadata。
# - framework 是 plain VARCHAR(32) 載大寫 app-enum 字面值;無 DB-native enum
#   / CREATE TYPE(鐵律 11)。
# - 無外鍵;training_run_id 為純索引欄,一致性由應用層維護(鐵律 12)。
# - created_at timestamptz;key metric sharpe 為 NUMERIC;其餘異質框架指標
#   走 JSONB(鐵律 10)。


def upgrade() -> None:
    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("artifact_path", sa.String(length=512), nullable=False),
        # application-layer enum stored as VARCHAR(32) (no DB-native enum)
        sa.Column("framework", sa.String(length=32), nullable=False),
        # training-run relation: plain indexed column, no FK (鐵律 12)
        sa.Column("training_run_id", sa.String(length=64), nullable=True),
        # key comparison metric as NUMERIC; heterogeneous metrics as JSONB
        sa.Column("sharpe", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # no ForeignKeyConstraint (鐵律 12)
    )
    op.create_index("ix_model_registry_name", "model_registry", ["name"])
    op.create_index("ix_model_registry_version", "model_registry", ["version"])
    op.create_index("ix_model_registry_framework", "model_registry", ["framework"])
    op.create_index(
        "ix_model_registry_training_run_id", "model_registry", ["training_run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_model_registry_training_run_id", table_name="model_registry")
    op.drop_index("ix_model_registry_framework", table_name="model_registry")
    op.drop_index("ix_model_registry_version", table_name="model_registry")
    op.drop_index("ix_model_registry_name", table_name="model_registry")
    op.drop_table("model_registry")
