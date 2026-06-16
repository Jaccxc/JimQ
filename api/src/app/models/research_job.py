"""``research_job`` — web 觸發的研究 job(dataset build / 模型訓練)。

記錄一個從 Research 儀表板觸發的研究 job 及其生命週期(卡 #23 W4)。正規化原則
與 ``backtest_run`` 一致(DEV_CONTRACT_AFK):
- 結構化欄位為一等公民;只有 job 的任意參數放 JSONB(鐵律 10);
- ``job_type`` / ``status`` 為 VARCHAR(32) 大寫契約字面值,enum 約束放應用層
  (TypeDecorator),不用 DB-native enum(鐵律 11);
- 無外鍵;``correlation_id`` 為純索引欄(鐵律 12);
- 時間戳一律 ``timestamptz``(鐵律 10)。
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class ResearchJobType(str, enum.Enum):
    """研究 job 種類(大寫契約字面值;對齊命令平面 command_type)。"""

    BUILD_DATASET = "BUILD_DATASET"
    TRAIN = "TRAIN"


class ResearchJobStatus(str, enum.Enum):
    """研究 job 生命週期(大寫契約字面值)。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class _EnumVarchar(TypeDecorator):
    """把 str-enum 以純 ``VARCHAR(32)`` 持久化(應用層 enum 約束;鐵律 11)。

    永不發出 ``CREATE TYPE``;DB 只見大寫字面值。子類設 ``enum_cls``。
    """

    impl = String(32)
    cache_ok = True
    enum_cls: type[enum.Enum]

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value.value
        return self.enum_cls(value).value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum_cls(value)


class ResearchJobTypeType(_EnumVarchar):
    cache_ok = True
    enum_cls = ResearchJobType


class ResearchJobStatusType(_EnumVarchar):
    cache_ok = True
    enum_cls = ResearchJobStatus


class ResearchJob(Base):
    __tablename__ = "research_job"

    id: Mapped[int] = mapped_column(
        "id", Integer, autoincrement=True, primary_key=True, init=False
    )

    # --- job 定義(結構化)---
    job_type: Mapped[ResearchJobType] = mapped_column(ResearchJobTypeType(), index=True)

    # --- 命令平面 correlation id(請求 → 命令 → job;審計)。純索引欄,無 FK(鐵律 12)。
    correlation_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)

    # --- job 參數:本質非結構化 payload → JSONB(鐵律 10)---
    params: Mapped[dict] = mapped_column(JSONB, default_factory=dict)

    # --- status:應用層 enum 存 VARCHAR(32)(鐵律 11)---
    status: Mapped[ResearchJobStatus] = mapped_column(
        ResearchJobStatusType(), default=ResearchJobStatus.PENDING, index=True
    )

    # --- worker 回寫的結果摘要 / 錯誤訊息(可選)---
    result: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # --- 時間戳(timestamptz)---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, onupdate=lambda: datetime.now(UTC)
    )
