"""卡 #20 (W1) — 命令平面信封契約(jimq_core.schemas.RunBacktestCommand)。

行為層測試(public interface):
- ``RunBacktestCommand`` 是 Pydantic v2 frozen 模型,攜帶 run_backtest 命令所需
  欄位(command_type / correlation_id / run_id / symbol / timeframe / strategy /
  params / start / end)。
- ``command_type`` 預設為共用契約常數 ``COMMAND_TYPE_RUN_BACKTEST``。
- 可序列化成 JSON 字串(XADD 到 Redis command stream 用)並無損 round-trip
  回模型 —— api(發布端)與 engine worker(消費端)經此契約解耦。
- 命令平面 stream key 為共用契約常數 ``COMMAND_STREAM_KEY``(與事件 stream 區隔)。

純 Pydantic / 純常數,不依賴 nautilus / redis / sqlalchemy,故放 jimq_core。
"""

from __future__ import annotations

from datetime import UTC, datetime

from jimq_core.constants import (
    COMMAND_STREAM_KEY,
    COMMAND_TYPE_RUN_BACKTEST,
    REDIS_BUS_DB,
)
from jimq_core.schemas import RunBacktestCommand


def _cmd(**overrides) -> RunBacktestCommand:
    base = dict(
        correlation_id="corr-abc",
        run_id=42,
        symbol="BTCUSDT-PERP.BINANCE",
        timeframe="1m",
        strategy="ema_cross",
        params={"fast_period": 3, "slow_period": 8},
        start=datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC),
        end=datetime(2023, 11, 14, 23, 13, 20, tzinfo=UTC),
    )
    base.update(overrides)
    return RunBacktestCommand(**base)


def test_command_carries_run_backtest_fields():
    cmd = _cmd()
    assert cmd.command_type == COMMAND_TYPE_RUN_BACKTEST
    assert cmd.correlation_id == "corr-abc"
    assert cmd.run_id == 42
    assert cmd.symbol == "BTCUSDT-PERP.BINANCE"
    assert cmd.timeframe == "1m"
    assert cmd.strategy == "ema_cross"
    assert cmd.params == {"fast_period": 3, "slow_period": 8}


def test_command_is_frozen():
    cmd = _cmd()
    try:
        cmd.run_id = 99  # type: ignore[misc]
    except Exception:  # noqa: BLE001 — pydantic frozen raises ValidationError
        return
    raise AssertionError("RunBacktestCommand 應為 frozen(不可變)")


def test_command_json_roundtrip_is_lossless():
    """信封序列化成 JSON 字串再 parse 回模型,欄位無損(XADD payload 契約)。"""
    cmd = _cmd()
    blob = cmd.model_dump_json()
    assert isinstance(blob, str)
    restored = RunBacktestCommand.model_validate_json(blob)
    assert restored == cmd


def test_command_plane_constants_are_distinct_from_event_bus():
    """命令平面用 DB0 的另一條 stream key,與事件 stream 區隔(B4)。"""
    assert COMMAND_STREAM_KEY == "jimq:commands"
    assert COMMAND_TYPE_RUN_BACKTEST == "RUN_BACKTEST"
    # 命令平面與事件 bus 共用 DB0(同一 Redis instance),靠 key 區隔而非 DB。
    assert REDIS_BUS_DB == 0
