"""卡 #10 — 串流接線的環境變數覆寫 + 動態 stream key 解析(行為測試)。

S8 全棧整合需要兩件事可由環境覆寫,且不破壞既有 localhost 預設:

1. ``bus_redis_url(env)``:Nautilus bus(DB0)的 Redis URL 由 ``REDIS_HOST`` /
   ``REDIS_PORT`` 覆寫(compose 內為服務名 ``redis``),預設仍 localhost。
2. ``resolve_stream_key(env, client)``:engine 每次跑產生的 stream key 帶隨機
   instance_id;backtest 把實際 key 寫到一個**已知 Redis key**(``LATEST_STREAM_KEY``)。
   API 啟動以 ``JIMQ_STREAM_KEY`` 設定串流來源:
   - 字面值 → 直接用該 key。
   - sentinel ``@latest`` → 從 Redis 的 ``LATEST_STREAM_KEY`` 讀實際 key。
   - 未設 → None(WS 端點仍可用,等灌入)。
"""

from __future__ import annotations

from app.ws.app_factory import (
    LATEST_STREAM_KEY,
    LATEST_SENTINEL,
    bus_redis_url,
    resolve_stream_key,
)


def test_bus_redis_url_defaults_localhost_db0():
    assert bus_redis_url({}) == "redis://localhost:6379/0"


def test_bus_redis_url_env_override():
    env = {"REDIS_HOST": "redis", "REDIS_PORT": "6380"}
    assert bus_redis_url(env) == "redis://redis:6380/0"


def test_resolve_stream_key_literal():
    env = {"JIMQ_STREAM_KEY": "trader-X:abc:stream"}
    assert resolve_stream_key(env, client=None) == "trader-X:abc:stream"


def test_resolve_stream_key_unset_is_none():
    assert resolve_stream_key({}, client=None) is None


class _FakeRedis:
    def __init__(self, value):
        self._value = value

    def get(self, key):
        assert key == LATEST_STREAM_KEY
        return self._value


def test_resolve_stream_key_latest_reads_well_known_key():
    env = {"JIMQ_STREAM_KEY": LATEST_SENTINEL}
    client = _FakeRedis(b"trader-BACKTESTER-001:uuid:stream")
    assert resolve_stream_key(env, client=client) == "trader-BACKTESTER-001:uuid:stream"


def test_resolve_stream_key_latest_missing_returns_none():
    env = {"JIMQ_STREAM_KEY": LATEST_SENTINEL}
    client = _FakeRedis(None)
    assert resolve_stream_key(env, client=client) is None
