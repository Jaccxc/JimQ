"""卡 #29 (P2-S3) — kill switch **取消未成交單**行為強化(行為測試)。

既有 test_control_worker.py 已驗 NodeController.kill() 對每策略
cancel_all_orders + close_all_positions + stop 且標 killed。本檔強化卡 #29
驗收最關鍵的一點:**未成交掛單真的被取消**,且動作順序安全(先取消未成交單,
再平倉、最後停止 —— 避免 kill 後仍有掛單在 venue 等成交)。

用一個記錄呼叫順序與「未成交單」狀態的 fake 策略;不需真 Nautilus 節點 / testnet。
"""

from __future__ import annotations

from jimq_engine.control.node_controller import NodeController


class _OrderTrackingStrategy:
    """記錄 kill 控制面呼叫順序的 fake 策略,並模擬一批未成交掛單。"""

    def __init__(self, open_order_ids: list[str]) -> None:
        self.open_orders = list(open_order_ids)  # 未成交掛單
        self.calls: list[str] = []

    def cancel_all_orders(self, *args, **kwargs):
        self.calls.append("cancel")
        # 取消後未成交掛單清空(模擬 venue 撤單)。
        self.open_orders = []

    def close_all_positions(self, *args, **kwargs):
        self.calls.append("close")

    def stop(self):
        self.calls.append("stop")


def test_kill_cancels_every_strategy_unfilled_orders():
    """kill 後每個策略的未成交掛單都被清空(真的撤單,非僅停策略)。"""
    s1 = _OrderTrackingStrategy(["o1", "o2"])
    s2 = _OrderTrackingStrategy(["o3"])
    node = NodeController(strategies={"a": s1, "b": s2})

    node.kill()

    assert s1.open_orders == [], "策略 a 的未成交單應全被取消"
    assert s2.open_orders == [], "策略 b 的未成交單應全被取消"
    assert node.killed is True


def test_kill_cancels_orders_before_stopping():
    """順序安全:先 cancel(撤未成交)→ close(平倉)→ stop;不可先 stop 留下掛單。"""
    s = _OrderTrackingStrategy(["o1"])
    node = NodeController(strategies={"a": s})

    node.kill()

    assert s.calls == ["cancel", "close", "stop"], s.calls
    assert s.calls.index("cancel") < s.calls.index("stop")
