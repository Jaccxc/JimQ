"""Pydantic schemas for ``research_job`` (卡 #23 W4;modelled on backtest_run)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.research_job import ResearchJobStatus, ResearchJobType


class ResearchJobBase(BaseModel):
    job_type: ResearchJobType
    params: dict[str, Any] = Field(default_factory=dict)
    correlation_id: Annotated[
        str | None, Field(default=None, max_length=64, examples=["corr-abc"])
    ] = None


class ResearchJobCreate(ResearchJobBase):
    model_config = ConfigDict(extra="forbid")


class ResearchJobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ResearchJobStatus | None = None
    result: dict[str, Any] | None = None


class ResearchJobRead(ResearchJobBase):
    id: int
    status: ResearchJobStatus
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ResearchJobRequest(BaseModel):
    """從 Research 儀表板觸發一個研究 job 的請求 body。

    只收使用者層欄位(job_type/params);status/id/correlation_id 由伺服端產生。
    ``job_type`` 為應用層 enum(BUILD_DATASET / TRAIN),未知值由 pydantic 回 422。
    """

    model_config = ConfigDict(extra="forbid")

    job_type: ResearchJobType
    params: dict[str, Any] = Field(default_factory=dict)


class ResearchJobAccepted(BaseModel):
    """POST /research/jobs 的回應:job 已建立(PENDING)、命令已發布。"""

    job_id: int
    correlation_id: str
    status: ResearchJobStatus
