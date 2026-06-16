"""卡 #20 (W1) — 命令平面發布端。

職責:把 UI launcher 的 backtest 請求轉成正規化 ``RunBacktestCommand`` 信封,
並 XADD 到 Redis command stream(``COMMAND_STREAM_KEY``,DB0 上與事件 stream
區隔的另一條 key)。engine 常駐 command worker 之後 XREADGROUP 消費。

設計(本地決策):
- **解耦**:api 不 import engine;兩端僅共用 ``jimq_core`` 的信封與常數。
- **stream entry 格式**:單一 field ``payload`` 帶信封 JSON 字串(無損 round-trip),
  外加頂層 ``command_type`` field 供消費端快速路由(無需先 parse payload)。
- **correlation_id**:端到端追蹤(請求 → 命令 → run → 事件流);未給則生成 uuid4。
- 命令平面與事件 bus 共用 DB0(同一 Redis instance),靠 key 區隔(B4)。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from jimq_core.constants import (
    COMMAND_STREAM_KEY,
    COMMAND_TYPE_BUILD_DATASET,
    COMMAND_TYPE_START_STRATEGY,
    COMMAND_TYPE_TRAIN,
)
from jimq_core.schemas import ControlCommand, ResearchJobCommand, RunBacktestCommand

# research_job 種類 → 命令平面 command_type(列舉欄位慣例,大寫字面值)。
_JOB_TYPE_TO_COMMAND: dict[str, str] = {
    "BUILD_DATASET": COMMAND_TYPE_BUILD_DATASET,
    "TRAIN": COMMAND_TYPE_TRAIN,
}


def build_run_backtest_command(
    *,
    run_id: int,
    symbol: str,
    timeframe: str,
    strategy: str,
    params: dict[str, Any],
    start: datetime,
    end: datetime,
    correlation_id: str | None = None,
) -> RunBacktestCommand:
    """把 launcher 請求欄位 + 預建 ``run_id`` 組成 ``RunBacktestCommand`` 信封。

    ``correlation_id`` 未給時生成 uuid4(端到端追蹤;與 ``backtest_run`` 同欄回寫)。
    """
    return RunBacktestCommand(
        correlation_id=correlation_id or uuid.uuid4().hex,
        run_id=run_id,
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        params=params,
        start=start,
        end=end,
    )


def build_research_job_command(
    *,
    job_id: int,
    job_type: str,
    params: dict[str, Any],
    correlation_id: str | None = None,
) -> ResearchJobCommand:
    """把 Research 儀表板的 job 請求組成 ``ResearchJobCommand`` 信封。

    ``job_type`` 為 ``BUILD_DATASET`` / ``TRAIN`` 大寫字面值,映射到對應命令平面
    ``command_type``。``correlation_id`` 未給時生成 uuid4(端到端追蹤;與
    ``research_job`` 同欄回寫)。
    """
    return ResearchJobCommand(
        command_type=_JOB_TYPE_TO_COMMAND[job_type],
        correlation_id=correlation_id or uuid.uuid4().hex,
        job_id=job_id,
        params=params,
    )


def build_control_command(
    *,
    command_type: str = COMMAND_TYPE_START_STRATEGY,
    strategy_id: str | None = None,
    params: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> ControlCommand:
    """組裝策略控制命令信封(卡 #24 W5)。

    ``command_type`` 為 START_STRATEGY / STOP_STRATEGY / KILL 大寫字面值。
    ``strategy_id`` start/stop 必帶,KILL 為全域急停可省略。``correlation_id``
    未給時生成 uuid4(端到端追蹤)。
    """
    return ControlCommand(
        command_type=command_type,
        correlation_id=correlation_id or uuid.uuid4().hex,
        strategy_id=strategy_id,
        params=params or {},
    )


async def publish_command(client: Any, command: Any) -> str:
    """把命令信封 XADD 到 Redis command stream(``COMMAND_STREAM_KEY``)。

    ``client`` 為 async Redis 介面(需 ``xadd``)。payload 為信封 JSON 字串
    (engine worker 端可無損還原);回傳 Redis entry id。
    """
    entry_id = await client.xadd(
        COMMAND_STREAM_KEY,
        {
            "command_type": command.command_type,
            "payload": command.model_dump_json(),
        },
    )
    return entry_id.decode() if isinstance(entry_id, (bytes, bytearray)) else str(entry_id)
