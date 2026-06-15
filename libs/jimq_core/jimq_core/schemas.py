"""jimq_core.schemas — 共用 DTO schema。

engine / api / WS 串流共用的 Pydantic v2 契約。

``BarDTO``(卡 #8):歷史/即時 K 線的傳輸物件,欄位與前端 Lightweight Charts
對齊(``time, open, high, low, close``),另帶 ``volume`` 與奈秒精度 ``ts``:

- ``ts``:epoch 奈秒(對應 Nautilus ``Bar.ts_init``),保留全精度供回放對齊。
- ``time``:epoch 秒,直接餵 Lightweight Charts 的 ``UTCTimestamp``。
- OHLCV 以字串保留交易所精度(避免浮點誤差;前端自行 parseFloat)。

``from_nautilus_bar`` 把 Nautilus ``Bar`` 映射成 DTO;為避免 jimq_core 硬依賴
nautilus_trader,僅在型別註解使用 ``TYPE_CHECKING`` 匯入(實際呼叫端帶入物件)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:  # pragma: no cover - 僅供型別檢查,執行期不匯入 nautilus
    from nautilus_trader.model.data import Bar

# 奈秒 → 秒。
_NS_PER_SEC = 1_000_000_000


class BarDTO(BaseModel):
    """單根 K 線的共用傳輸物件(Lightweight Charts 對齊)。"""

    model_config = ConfigDict(frozen=True)

    ts: int
    """epoch 奈秒(Nautilus ts_init)。"""

    time: int
    """epoch 秒(Lightweight Charts UTCTimestamp)。"""

    open: str
    high: str
    low: str
    close: str
    volume: str

    @classmethod
    def from_nautilus_bar(cls, bar: "Bar") -> "BarDTO":
        """從 Nautilus ``Bar`` 映射成 DTO。OHLCV 以字串保留精度。"""
        ts = int(bar.ts_init)
        return cls(
            ts=ts,
            time=ts // _NS_PER_SEC,
            open=str(bar.open),
            high=str(bar.high),
            low=str(bar.low),
            close=str(bar.close),
            volume=str(bar.volume),
        )
