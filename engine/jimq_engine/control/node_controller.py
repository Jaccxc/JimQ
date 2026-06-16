"""卡 #24 (W5) — 對測試節點的策略控制器(NodeController)。

把策略 start/stop 與全域 kill 的**行為**收斂在一個薄控制器上,讓 command
worker 只負責路由、由它對掛在節點上的策略動作。對 backtest/sandbox 測試節點
(真 live 節點控制屬 P2-S3,需有效金鑰)。

設計(本地決策):
- ``strategies``:``strategy_id -> Strategy``(掛在節點上的 Nautilus 策略;測試
  以薄 fake 替身,只暴露 ``cancel_all_orders`` / ``close_all_positions`` /
  ``stop``)。
- ``kill`` 明確語義(卡驗收):對**每個**策略取消未成交單 + 平倉 + 停止,並把
  節點標記 ``killed``。這是 header 全域急停接到命令平面後的真行為。
- ``stop_strategy`` 只停目標策略;未知 strategy_id 安全略過(命令來源不可信)。
- ``start_strategy`` 為佔位掛點:測試節點上策略已預先註冊,start 標記為啟用
  (真正動態掛載 / 由模型權重起策略屬後續卡);保留介面供 worker 派送。

不依賴 redis / sqlalchemy;只與 Nautilus 策略物件互動(且只用其控制面),
故可單獨以 fake 策略做行為測試。
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)


class NodeController:
    """對(測試)節點上策略的控制器:start / stop / kill。"""

    def __init__(self, strategies: Mapping[str, Any] | None = None) -> None:
        self._strategies: dict[str, Any] = dict(strategies or {})
        self.killed: bool = False
        self.started: set[str] = set()

    def start_strategy(self, strategy_id: str, params: Mapping[str, Any] | None = None) -> None:
        """標記策略為啟用。測試節點上策略已預先註冊;此處啟動既有策略。

        未知 strategy_id 安全略過(命令來源不可信)。真正依模型權重動態掛載
        新策略屬後續卡 —— 本卡只需啟動 / 控制已在節點上的測試策略。
        """
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            logger.info("start_strategy:未知策略 %s(略過)", strategy_id)
            return
        self.started.add(strategy_id)
        logger.info("start_strategy:%s params=%s", strategy_id, dict(params or {}))

    def stop_strategy(self, strategy_id: str) -> None:
        """停止單一目標策略。未知 strategy_id 安全略過。"""
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            logger.info("stop_strategy:未知策略 %s(略過)", strategy_id)
            return
        self.started.discard(strategy_id)
        self._stop_one(strategy)
        logger.info("stop_strategy:%s 已停止", strategy_id)

    def kill(self) -> None:
        """全域急停:對每個策略取消未成交單 + 平倉 + 停止,並標記節點已 kill。

        這是 header 全域 KILL 按鈕經命令平面接上後的明確行為(卡 #24 驗收)。
        """
        for strategy_id, strategy in self._strategies.items():
            try:
                self._cancel_orders(strategy)
                self._close_positions(strategy)
                self._stop_one(strategy)
            except Exception:  # noqa: BLE001 — 單一策略失敗不擋其餘急停。
                logger.exception("kill:策略 %s 急停時出錯(繼續其餘)", strategy_id)
        self.started.clear()
        self.killed = True
        logger.warning("KILL:已對 %s 個策略取消未成交單 + 平倉 + 停止", len(self._strategies))

    # --- 與 Nautilus 策略控制面互動(只用必要方法;容忍替身缺方法)-----------
    @staticmethod
    def _cancel_orders(strategy: Any) -> None:
        fn = getattr(strategy, "cancel_all_orders", None)
        if callable(fn):
            fn()

    @staticmethod
    def _close_positions(strategy: Any) -> None:
        fn = getattr(strategy, "close_all_positions", None)
        if callable(fn):
            fn()

    @staticmethod
    def _stop_one(strategy: Any) -> None:
        fn = getattr(strategy, "stop", None)
        if callable(fn):
            fn()
