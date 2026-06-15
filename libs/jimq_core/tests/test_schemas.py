"""卡 #8 — 共用 bar DTO 契約(jimq_core.schemas.BarDTO)。

行為層測試(public interface):
- BarDTO 是 Pydantic v2 模型,欄位與前端 Lightweight Charts 對齊
  (time, open, high, low, close)外加 volume 與奈秒精度 ts。
- 可由 Nautilus ``Bar`` 物件映射(from_nautilus_bar),OHLCV 以字串保留精度,
  time 為 epoch 秒、ts 為 epoch 奈秒。
- 序列化(model_dump)輸出穩定的契約欄位。

DTO 為 engine/api/WS 共用契約,故測試放在 jimq_core(不依賴 nautilus 即可驗證
純 Pydantic 行為;映射測試另在依賴 nautilus 的環境驗證)。
"""

from __future__ import annotations

from jimq_core.schemas import BarDTO


def test_bardto_is_pydantic_v2_with_chart_fields():
    bar = BarDTO(
        ts=1700000000_000_000_000,
        time=1700000000,
        open="37000.0",
        high="37050.0",
        low="36990.0",
        close="37025.0",
        volume="10.000",
    )
    dumped = bar.model_dump()
    assert dumped == {
        "ts": 1700000000_000_000_000,
        "time": 1700000000,
        "open": "37000.0",
        "high": "37050.0",
        "low": "36990.0",
        "close": "37025.0",
        "volume": "10.000",
    }


def test_bardto_time_is_epoch_seconds_derived_from_ts():
    bar = BarDTO(
        ts=1700000060_000_000_000,
        time=1700000060,
        open="1",
        high="1",
        low="1",
        close="1",
        volume="0",
    )
    # time(秒)= ts(奈秒) // 1e9,供 Lightweight Charts 的 UTCTimestamp 使用。
    assert bar.time == bar.ts // 1_000_000_000
