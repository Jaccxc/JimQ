"""卡 #24 (W5) — 策略控制命令信封契約(jimq_core.schemas.ControlCommand)。

行為層測試(public interface):
- ``ControlCommand`` 是 Pydantic v2 frozen 模型,攜帶控制命令所需欄位
  (command_type / correlation_id / strategy_id / params)。
- ``command_type`` 為 start/stop/kill 的大寫契約字面值常數
  (``COMMAND_TYPE_START_STRATEGY`` / ``COMMAND_TYPE_STOP_STRATEGY`` /
  ``COMMAND_TYPE_KILL``)。
- 可序列化成 JSON 字串(XADD 到 Redis command stream 用)並無損 round-trip
  回模型 —— api(發布端)與 engine worker(消費端)經此契約解耦。
- 控制命令與 run_backtest / research job 共用同一條 command stream
  (``COMMAND_STREAM_KEY``,DB0),靠 ``command_type`` 路由。
- KILL 為全域急停,可不帶 ``strategy_id``(對所有測試節點策略)。

純 Pydantic / 純常數,不依賴 nautilus / redis / sqlalchemy,故放 jimq_core。
"""

from __future__ import annotations

from jimq_core.constants import (
    COMMAND_STREAM_KEY,
    COMMAND_TYPE_KILL,
    COMMAND_TYPE_START_STRATEGY,
    COMMAND_TYPE_STOP_STRATEGY,
    REDIS_BUS_DB,
)
from jimq_core.schemas import ControlCommand


def test_start_command_carries_fields():
    cmd = ControlCommand(
        command_type=COMMAND_TYPE_START_STRATEGY,
        correlation_id="corr-1",
        strategy_id="ema_cross",
        params={"fast_period": 3},
    )
    assert cmd.command_type == COMMAND_TYPE_START_STRATEGY
    assert cmd.correlation_id == "corr-1"
    assert cmd.strategy_id == "ema_cross"
    assert cmd.params == {"fast_period": 3}


def test_stop_command_carries_strategy_id():
    cmd = ControlCommand(
        command_type=COMMAND_TYPE_STOP_STRATEGY,
        correlation_id="corr-2",
        strategy_id="ema_cross",
    )
    assert cmd.command_type == COMMAND_TYPE_STOP_STRATEGY
    assert cmd.strategy_id == "ema_cross"
    assert cmd.params == {}


def test_kill_command_is_global_without_strategy_id():
    """KILL 為全域急停,strategy_id 可省略(對所有測試節點策略)。"""
    cmd = ControlCommand(
        command_type=COMMAND_TYPE_KILL,
        correlation_id="corr-3",
    )
    assert cmd.command_type == COMMAND_TYPE_KILL
    assert cmd.strategy_id is None


def test_control_command_is_frozen():
    cmd = ControlCommand(
        command_type=COMMAND_TYPE_KILL, correlation_id="corr-4"
    )
    try:
        cmd.strategy_id = "x"  # type: ignore[misc]
    except Exception:  # noqa: BLE001 — pydantic frozen raises ValidationError
        return
    raise AssertionError("ControlCommand 應為 frozen(不可變)")


def test_control_command_json_roundtrip_is_lossless():
    cmd = ControlCommand(
        command_type=COMMAND_TYPE_START_STRATEGY,
        correlation_id="corr-5",
        strategy_id="ema_cross",
        params={"fast_period": 3, "slow_period": 8},
    )
    blob = cmd.model_dump_json()
    assert isinstance(blob, str)
    restored = ControlCommand.model_validate_json(blob)
    assert restored == cmd


def test_control_command_constants_share_command_stream():
    """控制命令與其他命令共用 DB0 上的同一條 command stream(B4)。"""
    assert COMMAND_STREAM_KEY == "jimq:commands"
    assert COMMAND_TYPE_START_STRATEGY == "START_STRATEGY"
    assert COMMAND_TYPE_STOP_STRATEGY == "STOP_STRATEGY"
    assert COMMAND_TYPE_KILL == "KILL"
    assert REDIS_BUS_DB == 0
