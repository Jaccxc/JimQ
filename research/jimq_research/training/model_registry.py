"""卡 #18 — 從 research 端把訓練好的模型登錄到 Postgres ``model_registry``。

與 ``store.py`` 同樣的解耦原則:research 是上層編排層,**不**匯入 api 的
``app`` 套件(避免循環匯入、不把 FastAPI/asyncpg 整包拉進 research)。改用
SQLAlchemy Core 對既有 ``model_registry`` 表做 app 級 INSERT / SELECT —— 表結構
由 api(schema 擁有者)的手寫 alembic 維護(鐵律 2),這裡只是正常應用程式讀寫。

連線只連 localhost(鐵律 4),URL 復用 ``store.local_engine_url``。
``framework`` 寫大寫契約字面值(VARCHAR,鐵律 11),無外鍵(鐵律 12),
``sharpe`` 以 NUMERIC 存、其餘 per-framework metrics 進 JSONB(鐵律 10)。

artifact 本身由 ``jimq_research.export.save_model_artifact`` 寫到磁碟
(``data/models/<name>/<version>/``,對齊 api ModelStore 慣例);這裡只登錄
metadata 並指向該 artifact 目錄。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Column,
    create_engine,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB

from jimq_research.training.store import local_engine_url

_metadata = MetaData()

# Core 宣告對齊 api ORM model / 手寫 migration 的既有欄位;research 端只讀寫。
model_registry = Table(
    "model_registry",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("version", String(64), nullable=False),
    Column("artifact_path", String(512), nullable=False),
    Column("framework", String(32), nullable=False),
    Column("training_run_id", String(64), nullable=True),
    Column("sharpe", Numeric(20, 8), nullable=True),
    Column("metrics", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def register_model(
    *,
    name: str,
    version: str,
    artifact_path: str,
    framework: str,
    sharpe: Decimal | float | None = None,
    metrics: dict[str, Any] | None = None,
    training_run_id: str | None = None,
    engine_url: str | None = None,
) -> int:
    """把一筆模型 metadata INSERT 進 ``model_registry``,回傳新列 id。

    ``framework`` 必須是大寫契約字面值(``SKLEARN`` / ``TORCH`` /
    ``STABLE_BASELINES3``);app 層約束,DB 只存 VARCHAR。
    """
    engine = create_engine(engine_url or local_engine_url())
    now = datetime.now(UTC)
    try:
        with engine.begin() as conn:
            result = conn.execute(
                insert(model_registry)
                .values(
                    name=name,
                    version=version,
                    artifact_path=artifact_path,
                    framework=framework,
                    training_run_id=training_run_id,
                    sharpe=(Decimal(str(sharpe)) if sharpe is not None else None),
                    metrics=metrics or {},
                    created_at=now,
                )
                .returning(model_registry.c.id)
            )
            return int(result.scalar_one())
    finally:
        engine.dispose()


def get_model(
    *,
    name: str,
    version: str,
    engine_url: str | None = None,
) -> dict[str, Any] | None:
    """查回某 ``(name, version)`` 的 registry 列(含 artifact_path);無則 None。"""
    engine = create_engine(engine_url or local_engine_url())
    try:
        stmt = (
            select(model_registry)
            .where(model_registry.c.name == name)
            .where(model_registry.c.version == version)
            .order_by(model_registry.c.id.desc())
        )
        with engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
            return dict(row) if row is not None else None
    finally:
        engine.dispose()
