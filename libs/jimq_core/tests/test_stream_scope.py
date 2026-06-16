"""卡 A — Live/Backtest 資料源隔離:scoped latest-stream-key 契約常數。

行為層測試(public interface):
- engine 與 api 共用的 scoped latest-key 常數:live 與 backtest 各自一條 Redis
  key,字面值不同且都帶舊 prefix(``jimq:``)。
- ``SCOPE_LATEST_KEY`` 把 scope 字面值(``STREAM_SCOPE_LIVE`` /
  ``STREAM_SCOPE_BACKTEST``)映到對應 latest-key,供 api 雙 scope supervisor 與
  engine 發 key 共用單一真相來源(避免兩端字面值漂移)。
- 舊的單一 ``LATEST_STREAM_KEY`` 仍保留(相容)。

純常數,不依賴 redis / nautilus,故放 jimq_core。
"""

from __future__ import annotations

from jimq_core.constants import (
    BACKTEST_LATEST_STREAM_KEY,
    LATEST_STREAM_KEY,
    LIVE_LATEST_STREAM_KEY,
    SCOPE_LATEST_KEY,
    STREAM_SCOPE_BACKTEST,
    STREAM_SCOPE_LIVE,
)


def test_live_and_backtest_keys_are_distinct_namespaced():
    assert LIVE_LATEST_STREAM_KEY == "jimq:live:latest_stream_key"
    assert BACKTEST_LATEST_STREAM_KEY == "jimq:backtest:latest_stream_key"
    assert LIVE_LATEST_STREAM_KEY != BACKTEST_LATEST_STREAM_KEY


def test_legacy_single_key_preserved_for_compat():
    assert LATEST_STREAM_KEY == "jimq:latest_stream_key"


def test_scope_literals():
    assert STREAM_SCOPE_LIVE == "live"
    assert STREAM_SCOPE_BACKTEST == "backtest"


def test_scope_latest_key_maps_scope_to_redis_key():
    assert SCOPE_LATEST_KEY[STREAM_SCOPE_LIVE] == LIVE_LATEST_STREAM_KEY
    assert SCOPE_LATEST_KEY[STREAM_SCOPE_BACKTEST] == BACKTEST_LATEST_STREAM_KEY
    # 只認得這兩個 scope。
    assert set(SCOPE_LATEST_KEY) == {STREAM_SCOPE_LIVE, STREAM_SCOPE_BACKTEST}
