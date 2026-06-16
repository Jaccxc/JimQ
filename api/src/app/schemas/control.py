"""Pydantic schemas for 策略控制平面 (卡 #24 W5)。

控制動作為無狀態觸發(start/stop/kill → 命令平面),不對應 DB 列 —— 故只需
請求 / 回應 DTO,無 Create/Update/Read CRUD schema。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrategyControlRequest(BaseModel):
    """start 時的可選 body:策略參數 payload(stop/kill 不需 body)。"""

    model_config = ConfigDict(extra="forbid")

    params: dict[str, Any] = Field(default_factory=dict)


class ControlAccepted(BaseModel):
    """控制端點回應:命令已發布到 command stream。

    - ``strategy_id``:目標策略(KILL 全域急停為 ``None``)。
    - ``command_type``:START_STRATEGY / STOP_STRATEGY / KILL 大寫字面值。
    - ``correlation_id``:端到端追蹤 id(供審計 / 狀態回流對齊)。
    """

    strategy_id: str | None = None
    command_type: str
    correlation_id: str
