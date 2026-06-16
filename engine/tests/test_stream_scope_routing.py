"""卡 A — Live/Backtest 資料源隔離:engine 發 key 分流(行為測試)。

engine 把實際 stream key 依資料源寫到**不同** latest-key,api 雙 scope supervisor
才能各 watch 自己的 key、互不污染:
- ``run_live_data.py`` / ``run_live_trade.py``(live/paper 資料源)→ 寫
  ``LIVE_LATEST_STREAM_KEY``。
- ``run_streaming_backtest.py``(backtest 資料源)與 control worker 的
  ``handle_run_backtest`` → 寫 ``BACKTEST_LATEST_STREAM_KEY``。

只驗 public 常數綁定與 worker publish 目標(不啟動真節點 / 不連網):確保兩端
共用 jimq_core 單一真相來源、scope 不漂移。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from jimq_core.constants import (
    BACKTEST_LATEST_STREAM_KEY,
    LIVE_LATEST_STREAM_KEY,
)

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_run_live_data_publishes_to_live_scope_key():
    mod = _load("run_live_data_mod_scope", "run_live_data.py")
    assert mod.LATEST_STREAM_KEY == LIVE_LATEST_STREAM_KEY


def test_run_live_trade_publishes_to_live_scope_key():
    mod = _load("run_live_trade_mod_scope", "run_live_trade.py")
    assert mod.LATEST_STREAM_KEY == LIVE_LATEST_STREAM_KEY


def test_run_streaming_backtest_publishes_to_backtest_scope_key():
    mod = _load("run_streaming_backtest_mod_scope", "run_streaming_backtest.py")
    assert mod.LATEST_STREAM_KEY == BACKTEST_LATEST_STREAM_KEY


class _RecordingRedis:
    """記錄 set 呼叫的同步 fake(只關心 latest-key 目標)。"""

    def __init__(self):
        self.sets: dict[str, str] = {}

    def set(self, key, value):  # noqa: A003
        self.sets[key] = value


def test_control_worker_publishes_backtest_run_key_to_backtest_scope():
    """control worker 跑完 backtest → latest key 寫到 backtest scope(非 live)。"""
    from jimq_engine.control import worker

    client = _RecordingRedis()
    worker._publish_latest_key(client, "trader-X:inst:stream")

    assert client.sets.get(BACKTEST_LATEST_STREAM_KEY) == "trader-X:inst:stream"
    # 不再寫舊單一 key / live key(避免污染 Live)。
    assert LIVE_LATEST_STREAM_KEY not in client.sets
