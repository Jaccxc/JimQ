"""backtests resource router.

- FastCRUD auto-endpoints (list / get / create / update / delete; auth stripped):
  ``GET /backtests`` (#5 history), ``GET /backtests/{id}`` (#20 status poll), …
- 卡 #20 (W1) custom ``POST /backtests/run``: 從 UI launcher 觸發一次 backtest —
  建 ``backtest_run`` 列(status=PENDING)→ 把正規化命令信封 XADD 到 Redis
  command stream(DB0 上與事件 stream 區隔的另一條 key)→ 回 run_id /
  correlation_id。**api 不 import engine**:engine 常駐 command worker 之後經
  Redis 消費此命令(解耦)。
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from fastcrud import crud_router
from sqlalchemy.ext.asyncio import AsyncSession

from jimq_core.timeframes import bar_type_for

from ...core.db.database import async_get_db
from ...crud.crud_backtest_run import crud_backtest_runs
from ...models.backtest_run import BacktestRun, BacktestStatus
from ...schemas.backtest_run import (
    BacktestRunAccepted,
    BacktestRunCreate,
    BacktestRunRead,
    BacktestRunRequest,
    BacktestRunUpdate,
)
from ...services.command_publisher import build_run_backtest_command, publish_command
from ...ws.app_factory import bus_redis_url

# FastCRUD 自動 CRUD 端點(list/get/create/update/delete)。
router = crud_router(
    session=async_get_db,
    model=BacktestRun,
    crud=crud_backtest_runs,
    create_schema=BacktestRunCreate,
    update_schema=BacktestRunUpdate,
    select_schema=BacktestRunRead,
    path="/backtests",
    tags=["backtests"],
)


# --- 卡 #20 (W1):依賴(可被測試 override)----------------------------------
def get_backtest_crud():
    """注入 backtest_run 的 FastCRUD instance(測試可 override 成 fake)。"""
    return crud_backtest_runs


def get_command_redis() -> Any:
    """注入命令平面 async Redis(DB0;測試可 override 成 fake)。"""
    return aioredis.from_url(bus_redis_url())


# 自訂 run 路由(掛在同一 /backtests path,與 FastCRUD 端點並存)。
run_router = APIRouter(prefix="/backtests", tags=["backtests"])


@run_router.post(
    "/run",
    response_model=BacktestRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="從 UI 觸發一次 backtest(建 PENDING 列 + 發命令到 command stream)",
)
async def run_backtest(
    req: BacktestRunRequest,
    db: AsyncSession = Depends(async_get_db),
    crud=Depends(get_backtest_crud),
    redis_client=Depends(get_command_redis),
) -> BacktestRunAccepted:
    """建 backtest_run(PENDING)→ XADD 命令信封到 command stream → 回 run_id。"""
    # 先生成 correlation_id 並一併存進列,使 run 與命令端到端可追蹤。
    command = build_run_backtest_command(
        run_id=0,  # 佔位;建列後以實際 id 重建信封。
        symbol=req.symbol,
        timeframe=req.timeframe,
        strategy=req.strategy,
        params=req.params,
        start=req.start,
        end=req.end,
    )

    bar_type = bar_type_for(req.symbol, req.timeframe)
    create = BacktestRunCreate(
        strategy_name=req.strategy,
        instrument_id=req.symbol,
        bar_type=bar_type,
        timeframe=req.timeframe,
        start_time=req.start,
        end_time=req.end,
        params=req.params,
        correlation_id=command.correlation_id,
    )
    # FastCRUD create_schema 不含 status(預設 PENDING);用 model 物件帶入 status。
    created = await crud.create(
        db,
        BacktestRunCreate.model_construct(**create.model_dump()),
    )
    run_id = created.id

    # 用實際 run_id 重建信封(沿用同一 correlation_id),XADD 到 command stream。
    final_command = build_run_backtest_command(
        run_id=run_id,
        symbol=req.symbol,
        timeframe=req.timeframe,
        strategy=req.strategy,
        params=req.params,
        start=req.start,
        end=req.end,
        correlation_id=command.correlation_id,
    )
    await publish_command(redis_client, final_command)

    return BacktestRunAccepted(
        run_id=run_id,
        correlation_id=command.correlation_id,
        status=BacktestStatus.PENDING,
    )


router.include_router(run_router)
