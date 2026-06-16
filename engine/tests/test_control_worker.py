"""卡 #24 (W5) — engine command worker 控制命令處理(engine.control.worker)。

行為層測試(public interface):
- ``parse_control_entry``:把 Redis command stream 的一筆 entry(``command_type``
  + JSON ``payload``)解析回 ``ControlCommand``;非控制命令 / 壞 payload 回 None
  (安全略過,讓 run_backtest / research 命令各走各的解析)。
- ``handle_control_command``:依命令型別對**測試節點控制器**(node controller)
  動作 ——
    * START_STRATEGY → controller.start_strategy(strategy_id, params)
    * STOP_STRATEGY  → controller.stop_strategy(strategy_id)
    * KILL           → controller.kill()(= 停止所有策略 + 取消未成交單)
  controller 為注入的抽象(對 backtest/sandbox 測試節點;真 live 節點屬 P2-S3),
  測試用 fake 驗行為,不需真 Nautilus 節點。
- ``NodeController``(對測試節點的具體實作):``kill`` 明確 = 對每個策略
  ``cancel_all_orders`` + ``close_all_positions``,並把節點標記為已 kill;
  ``stop_strategy`` 停單一策略;``start_strategy`` 啟動。用 fake strategy 驗行為。
"""

from __future__ import annotations

from jimq_core.constants import (
    COMMAND_TYPE_KILL,
    COMMAND_TYPE_START_STRATEGY,
    COMMAND_TYPE_STOP_STRATEGY,
)
from jimq_core.schemas import ControlCommand

from jimq_engine.control.worker import handle_control_command, parse_control_entry
from jimq_engine.control.node_controller import NodeController


def _entry(command_type: str, payload: str) -> tuple[bytes, dict]:
    return (b"0-1", {b"command_type": command_type.encode(), b"payload": payload.encode()})


def _control_json(**kw) -> str:
    return ControlCommand(**kw).model_dump_json()


# --- parse_control_entry ----------------------------------------------------

def test_parse_valid_start_entry():
    cmd = parse_control_entry(
        _entry(
            COMMAND_TYPE_START_STRATEGY,
            _control_json(
                command_type=COMMAND_TYPE_START_STRATEGY,
                correlation_id="c1",
                strategy_id="ema_cross",
                params={"fast_period": 3},
            ),
        )
    )
    assert isinstance(cmd, ControlCommand)
    assert cmd.command_type == COMMAND_TYPE_START_STRATEGY
    assert cmd.strategy_id == "ema_cross"


def test_parse_valid_kill_entry():
    cmd = parse_control_entry(
        _entry(
            COMMAND_TYPE_KILL,
            _control_json(command_type=COMMAND_TYPE_KILL, correlation_id="c2"),
        )
    )
    assert isinstance(cmd, ControlCommand)
    assert cmd.command_type == COMMAND_TYPE_KILL


def test_parse_ignores_non_control_command():
    # run_backtest 的 command_type 不屬控制平面 → None(由各自解析器處理)。
    assert parse_control_entry(_entry("RUN_BACKTEST", "{}")) is None


def test_parse_ignores_bad_payload():
    assert parse_control_entry(_entry(COMMAND_TYPE_KILL, "not-json")) is None


# --- handle_control_command(對 fake controller 驗行為)----------------------

class _FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def start_strategy(self, strategy_id, params):  # noqa: ANN001
        self.calls.append(("start", strategy_id, params))

    def stop_strategy(self, strategy_id):  # noqa: ANN001
        self.calls.append(("stop", strategy_id))

    def kill(self):
        self.calls.append(("kill",))


def test_handle_start_dispatches_to_controller():
    ctrl = _FakeController()
    handle_control_command(
        ControlCommand(
            command_type=COMMAND_TYPE_START_STRATEGY,
            correlation_id="c1",
            strategy_id="ema_cross",
            params={"fast_period": 3},
        ),
        controller=ctrl,
    )
    assert ctrl.calls == [("start", "ema_cross", {"fast_period": 3})]


def test_handle_stop_dispatches_to_controller():
    ctrl = _FakeController()
    handle_control_command(
        ControlCommand(
            command_type=COMMAND_TYPE_STOP_STRATEGY,
            correlation_id="c2",
            strategy_id="ema_cross",
        ),
        controller=ctrl,
    )
    assert ctrl.calls == [("stop", "ema_cross")]


def test_handle_kill_dispatches_to_controller():
    ctrl = _FakeController()
    handle_control_command(
        ControlCommand(command_type=COMMAND_TYPE_KILL, correlation_id="c3"),
        controller=ctrl,
    )
    assert ctrl.calls == [("kill",)]


# --- NodeController(對測試節點的具體 kill 行為)-----------------------------

class _FakeStrategy:
    """模擬一個掛在測試節點上的 Nautilus 策略(只暴露本卡用到的控制面)。"""

    def __init__(self, strategy_id: str) -> None:
        self.id = strategy_id
        self.cancelled_orders = False
        self.closed_positions = False
        self.stopped = False

    def cancel_all_orders(self, *args, **kwargs):
        self.cancelled_orders = True

    def close_all_positions(self, *args, **kwargs):
        self.closed_positions = True

    def stop(self):
        self.stopped = True


def test_node_controller_kill_cancels_orders_and_closes_positions():
    """KILL 明確行為:對每個策略取消未成交單 + 平倉,並標記節點已 kill。"""
    s1 = _FakeStrategy("ema_cross")
    s2 = _FakeStrategy("other")
    node = NodeController(strategies={"ema_cross": s1, "other": s2})

    node.kill()

    assert s1.cancelled_orders and s1.closed_positions and s1.stopped
    assert s2.cancelled_orders and s2.closed_positions and s2.stopped
    assert node.killed is True


def test_node_controller_stop_strategy_only_stops_target():
    s1 = _FakeStrategy("ema_cross")
    s2 = _FakeStrategy("other")
    node = NodeController(strategies={"ema_cross": s1, "other": s2})

    node.stop_strategy("ema_cross")

    assert s1.stopped is True
    assert s2.stopped is False


def test_node_controller_stop_unknown_strategy_is_noop():
    node = NodeController(strategies={})
    node.stop_strategy("ghost")  # 不存在 → 安全略過,不拋。
