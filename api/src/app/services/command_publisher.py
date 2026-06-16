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

from jimq_core.constants import COMMAND_STREAM_KEY
from jimq_core.schemas import RunBacktestCommand


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


async def publish_command(client: Any, command: RunBacktestCommand) -> str:
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
