"""``model_registry`` — P3-S4 model store metadata (卡 #17).

Records one registered model artifact (name + version) and where its weights
live on disk (``data/models/<name>/<version>/``, gitignored). Normalised per
DEV_CONTRACT_AFK:
- structured fields are first-class columns; only the genuinely heterogeneous
  per-framework training metrics live in JSONB (鐵律 10) — the key comparison
  metric (``sharpe``) is split out as a NUMERIC column;
- ``framework`` is a VARCHAR(32) carrying an uppercase contract literal, with
  the enum constraint enforced in the application layer via a ``TypeDecorator``
  (no DB-native enum — 鐵律 11);
- no foreign keys — the ``training_run_id`` relation is a plain indexed column
  (鐵律 12), consistency maintained in the app layer;
- all timestamps are ``timestamptz`` and ratios are ``NUMERIC`` (鐵律 10).
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, Numeric, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class ModelFramework(str, enum.Enum):
    """Training framework of a registered model (uppercase contract literals)."""

    TORCH = "TORCH"
    SKLEARN = "SKLEARN"
    STABLE_BASELINES3 = "STABLE_BASELINES3"


class ModelFrameworkType(TypeDecorator):
    """Persist :class:`ModelFramework` as a plain ``VARCHAR(32)``.

    Application-layer enum constraint (鐵律 11): no ``CREATE TYPE`` is ever
    emitted; the DB sees only uppercase string literals.
    """

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, ModelFramework):
            return value.value
        # accept the raw uppercase literal too (validate membership)
        return ModelFramework(value).value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return ModelFramework(value)


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(
        "id", Integer, autoincrement=True, primary_key=True, init=False
    )

    # --- model identity (structured, normalised) ---
    name: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(64), index=True)

    # --- artifact location on disk (data/models/<name>/<version>/, gitignored) ---
    artifact_path: Mapped[str] = mapped_column(String(512))

    # --- framework: app-layer enum stored as VARCHAR(32) (鐵律 11) ---
    framework: Mapped[ModelFramework] = mapped_column(ModelFrameworkType(), index=True)

    # --- training-run relation: plain indexed column, no FK (鐵律 12) ---
    training_run_id: Mapped[str | None] = mapped_column(
        String(64), default=None, index=True
    )

    # --- key comparison metric: first-class NUMERIC column (鐵律 10) ---
    sharpe: Mapped[float | None] = mapped_column(Numeric(20, 8), default=None)

    # --- heterogeneous per-framework metrics: genuinely unstructured -> JSONB (鐵律 10) ---
    metrics: Mapped[dict] = mapped_column(JSONB, default_factory=dict)

    # --- timestamps (timestamptz) ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(UTC)
    )
