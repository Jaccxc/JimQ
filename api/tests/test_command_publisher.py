"""卡 #20 (W1) — 命令平面發布端(services.command_publisher)。

行為層測試(public interface):
- ``build_run_backtest_command``:把 launcher 請求欄位 + 預建 run_id 組成
  ``RunBacktestCommand`` 信封,自動帶上 correlation_id(若未給則生成)。
- ``publish_command``:把信封 XADD 到 Redis command stream(``COMMAND_STREAM_KEY``,
  DB0 的另一條 key,與事件 stream 區隔),payload 為 JSON 字串、可無損還原。

用 fake redis(只實作 xadd / xrange)驗證行為,不需真 Redis —— 發布端契約
獨立於 broker。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from jimq_core.constants import COMMAND_STREAM_KEY, COMMAND_TYPE_RUN_BACKTEST
from jimq_core.schemas import RunBacktestCommand

from app.services.command_publisher import (
    build_run_backtest_command,
    publish_command,
)


class _FakeRedis:
    """最小 async redis stub:記錄 xadd 的 (key, fields)。"""

    def __init__(self) -> None:
        self.entries: list[tuple[str, dict]] = []

    async def xadd(self, key, fields, **kwargs):  # noqa: ANN001
        self.entries.append((key, dict(fields)))
        return f"0-{len(self.entries)}"


def test_build_command_assembles_envelope_with_run_id():
    cmd = build_run_backtest_command(
        run_id=7,
        symbol="BTCUSDT-PERP.BINANCE",
        timeframe="1m",
        strategy="ema_cross",
        params={"fast_period": 3, "slow_period": 8},
        start=datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC),
        end=datetime(2023, 11, 14, 23, 13, 20, tzinfo=UTC),
        correlation_id="corr-xyz",
    )
    assert isinstance(cmd, RunBacktestCommand)
    assert cmd.command_type == COMMAND_TYPE_RUN_BACKTEST
    assert cmd.run_id == 7
    assert cmd.correlation_id == "corr-xyz"
    assert cmd.strategy == "ema_cross"


def test_build_command_generates_correlation_id_when_absent():
    cmd = build_run_backtest_command(
        run_id=1,
        symbol="BTCUSDT-PERP.BINANCE",
        timeframe="1m",
        strategy="ema_cross",
        params={},
        start=datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC),
        end=datetime(2023, 11, 14, 23, 13, 20, tzinfo=UTC),
    )
    assert cmd.correlation_id  # 非空
    assert isinstance(cmd.correlation_id, str)


async def test_publish_command_xadds_json_envelope_to_command_stream():
    client = _FakeRedis()
    cmd = build_run_backtest_command(
        run_id=42,
        symbol="BTCUSDT-PERP.BINANCE",
        timeframe="1m",
        strategy="ema_cross",
        params={"fast_period": 3, "slow_period": 8},
        start=datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC),
        end=datetime(2023, 11, 14, 23, 13, 20, tzinfo=UTC),
        correlation_id="corr-42",
    )
    entry_id = await publish_command(client, cmd)

    assert entry_id
    assert len(client.entries) == 1
    key, fields = client.entries[0]
    # 命令平面用 DB0 的另一條 stream key,與事件 stream 區隔(B4)。
    assert key == COMMAND_STREAM_KEY
    # payload 為 JSON 字串,可無損還原成同一信封(api 發布 -> engine worker 消費)。
    restored = RunBacktestCommand.model_validate_json(fields["payload"])
    assert restored == cmd
    # 信封同時帶上頂層 command_type field,供消費端快速路由(無需先 parse payload)。
    assert fields["command_type"] == COMMAND_TYPE_RUN_BACKTEST
    # JSON payload 確實是字串。
    assert json.loads(fields["payload"])["run_id"] == 42
