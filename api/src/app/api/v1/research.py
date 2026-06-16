"""卡 #23 (W4) — research job 控制平面 + research_job CRUD 端點。

- FastCRUD 自動端點(list/get;auth 已剝離):``GET /research/jobs/{id}``
  狀態輪詢、``GET /research/jobs`` 歷史。
- 自訂 ``POST /research/jobs``:從 Research 儀表板觸發一個研究 job
  (dataset build / 模型訓練)。建 ``research_job`` 列(status=PENDING)→ 把
  ``ResearchJobCommand`` 信封 XADD 到 Redis command stream(DB0,與 backtest
  命令同 key,靠 ``command_type`` 路由)→ 回 job_id / correlation_id / status。

**api 不 import research**:research worker(獨立 venv)之後經 Redis 消費此命令
(解耦)。job 觸發 MVP 的驗收 = job 被觸發(列建立 + 命令發布)且狀態可輪詢。
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from fastcrud import crud_router
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db.database import async_get_db
from ...crud.crud_research_job import crud_research_jobs
from ...models.research_job import ResearchJob, ResearchJobStatus
from ...schemas.research_job import (
    ResearchJobAccepted,
    ResearchJobCreate,
    ResearchJobRead,
    ResearchJobRequest,
    ResearchJobUpdate,
)
from ...services.command_publisher import build_research_job_command, publish_command
from ...ws.app_factory import bus_redis_url

# FastCRUD 自動端點:**只開讀取**(list/get)。建立改走下方自訂 POST(觸發 +
# 發命令),避免與 FastCRUD 預設 create 在同一 path 衝突。
router = crud_router(
    session=async_get_db,
    model=ResearchJob,
    crud=crud_research_jobs,
    create_schema=ResearchJobCreate,
    update_schema=ResearchJobUpdate,
    select_schema=ResearchJobRead,
    path="/research/jobs",
    tags=["research"],
    included_methods=["read", "read_multi"],
)


# --- 依賴(可被測試 override)-------------------------------------------------
def get_research_job_crud():
    """注入 research_job FastCRUD instance(測試可 override 成 fake)。"""
    return crud_research_jobs


def get_command_redis() -> Any:
    """注入命令平面 async Redis(DB0;測試可 override 成 fake)。"""
    return aioredis.from_url(bus_redis_url())


# 自訂觸發路由(掛在同一 /research/jobs path)。
trigger_router = APIRouter(prefix="/research", tags=["research"])


@trigger_router.post(
    "/jobs",
    response_model=ResearchJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="從 web 觸發一個研究 job(建 PENDING 列 + 發命令到 command stream)",
)
async def trigger_research_job(
    req: ResearchJobRequest,
    db: AsyncSession = Depends(async_get_db),
    crud=Depends(get_research_job_crud),
    redis_client=Depends(get_command_redis),
) -> ResearchJobAccepted:
    """建 research_job(PENDING)→ XADD ResearchJobCommand 信封 → 回 job_id。"""
    # 先生成 correlation_id 並一併存進列,使 job 與命令端到端可追蹤。
    seed = build_research_job_command(
        job_id=0,  # 佔位;建列後以實際 id 重建信封。
        job_type=req.job_type.value,
        params=req.params,
    )

    create = ResearchJobCreate(
        job_type=req.job_type,
        params=req.params,
        correlation_id=seed.correlation_id,
    )
    created = await crud.create(
        db,
        create,
        schema_to_select=ResearchJobRead,
        return_as_model=True,
    )
    job_id = created.id

    final_command = build_research_job_command(
        job_id=job_id,
        job_type=req.job_type.value,
        params=req.params,
        correlation_id=seed.correlation_id,
    )
    await publish_command(redis_client, final_command)

    return ResearchJobAccepted(
        job_id=job_id,
        correlation_id=seed.correlation_id,
        status=ResearchJobStatus.PENDING,
    )


router.include_router(trigger_router)
