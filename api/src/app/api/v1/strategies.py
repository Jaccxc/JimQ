"""卡 #24 (W5) — 策略控制平面端點(start / stop / 全域 kill)。

- ``POST /strategies/{strategy_id}/start``:啟動目標策略 → 發 START_STRATEGY
  控制命令信封到 Redis command stream(DB0)。
- ``POST /strategies/{strategy_id}/stop``:停止目標策略 → 發 STOP_STRATEGY。
- ``POST /kill``:header 全域急停 → 發 KILL(停止所有策略 + 取消未成交單)。

**api 不 import engine**:engine 常駐 command worker 之後經 Redis 消費這些命令、
對 backtest/sandbox 測試節點動作(解耦、可重播、可審計)。真 live 節點控制屬
P2-S3(需有效金鑰)。控制動作為無狀態觸發(命令來源即真相),不落 DB CRUD ——
狀態回流走既有 WS / 輪詢。
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status

from jimq_core.constants import (
    COMMAND_TYPE_KILL,
    COMMAND_TYPE_START_STRATEGY,
    COMMAND_TYPE_STOP_STRATEGY,
)

from ...schemas.control import ControlAccepted, StrategyControlRequest
from ...services.command_publisher import build_control_command, publish_command
from ...ws.app_factory import bus_redis_url


def get_command_redis() -> Any:
    """注入命令平面 async Redis(DB0;測試可 override 成 fake)。"""
    return aioredis.from_url(bus_redis_url())


router = APIRouter(tags=["control"])


async def _publish_control(
    redis_client: Any,
    *,
    command_type: str,
    strategy_id: str | None,
    params: dict[str, Any] | None,
) -> ControlAccepted:
    command = build_control_command(
        command_type=command_type, strategy_id=strategy_id, params=params
    )
    await publish_command(redis_client, command)
    return ControlAccepted(
        strategy_id=strategy_id,
        command_type=command_type,
        correlation_id=command.correlation_id,
    )


@router.post(
    "/strategies/{strategy_id}/start",
    response_model=ControlAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="啟動策略(發 START_STRATEGY 控制命令到 command stream)",
)
async def start_strategy(
    strategy_id: str,
    req: StrategyControlRequest | None = None,
    redis_client=Depends(get_command_redis),
) -> ControlAccepted:
    """發 START_STRATEGY 命令(帶 strategy_id + params)到 command stream。"""
    params = req.params if req is not None else {}
    return await _publish_control(
        redis_client,
        command_type=COMMAND_TYPE_START_STRATEGY,
        strategy_id=strategy_id,
        params=params,
    )


@router.post(
    "/strategies/{strategy_id}/stop",
    response_model=ControlAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="停止策略(發 STOP_STRATEGY 控制命令到 command stream)",
)
async def stop_strategy(
    strategy_id: str,
    redis_client=Depends(get_command_redis),
) -> ControlAccepted:
    """發 STOP_STRATEGY 命令(帶 strategy_id)到 command stream。"""
    return await _publish_control(
        redis_client,
        command_type=COMMAND_TYPE_STOP_STRATEGY,
        strategy_id=strategy_id,
        params=None,
    )


@router.post(
    "/kill",
    response_model=ControlAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="全域急停(發 KILL:停止所有策略 + 取消未成交單)",
)
async def kill(
    redis_client=Depends(get_command_redis),
) -> ControlAccepted:
    """header 全域 KILL → 發 KILL 命令(strategy_id 省略)到 command stream。"""
    return await _publish_control(
        redis_client,
        command_type=COMMAND_TYPE_KILL,
        strategy_id=None,
        params=None,
    )
