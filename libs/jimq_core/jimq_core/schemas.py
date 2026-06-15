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

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:  # pragma: no cover - 僅供型別檢查,執行期不匯入 nautilus
    from nautilus_trader.model.data import Bar

# 奈秒 → 秒。
_NS_PER_SEC = 1_000_000_000

# WS 多工 channel 名稱(共用契約)。consumer/hub/ws gateway 與前端共用。
Channel = Literal["bars", "orders", "fills", "positions", "pnl"]


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


def bar_event_data(payload: Mapping[str, Any]) -> dict[str, Any]:
    """把 Nautilus ``Bar`` 串流 payload(已反序列化的 dict)補上 BarDTO 對齊欄位。

    串流 payload 帶字串 OHLCV 與字串 ``ts_init``(epoch 奈秒);此函式回傳要
    併入 WS ``data`` 的補強欄位:``ts``(int 奈秒)與 ``time``(int epoch 秒,
    直接餵 Lightweight Charts ``UTCTimestamp``)。OHLCV 維持字串保留精度。
    """
    ts = int(payload["ts_init"])
    return {"ts": ts, "time": ts // _NS_PER_SEC}


class StreamEnvelope(BaseModel):
    """WS 串流信封共用契約 ``{channel, seq, data}``(卡 #7)。

    consumer 正規化後發出、hub 派送、ws gateway 推給 client 的統一外殼。
    - ``channel``:多工 channel(bars/orders/fills/positions/pnl)。
    - ``seq``:consumer 端單調序號(client 用於 last_seq 補洞)。
    - ``data``:正規化後的事件 payload(bars 帶 BarDTO 對齊欄位;其餘事件
      帶 Nautilus 純量 dict 並保留 ``type`` 供 client 分辨子型別)。
    """

    model_config = ConfigDict(frozen=True)

    channel: Channel
    seq: int
    data: dict[str, Any]


class BacktestRunSummary(BaseModel):
    """一次 backtest run 的摘要(卡 #15;engine/research/api 共用契約)。

    攜帶 run 身份(策略 / instrument / bar_type / timeframe / 區間 / 策略參數)
    與結果指標(報酬 / Sharpe / 最大回撤 / 成交筆數 / 最終餘額)。批量 backtest
    runner 對參數網格每組產出一個 summary,持久化到 Postgres ``backtest_run``。

    - 金額 / 比率以 ``Decimal`` 保留精度,對齊 DB 端 ``NUMERIC``(鐵律 10);
    - ``params`` 為本質非結構化的策略參數 payload(對齊 DB ``params`` JSONB);
    - ``run_group`` 標記同一次網格批跑的多筆 run,供查詢 / 比較(單跑為 ``None``)。

    純 Pydantic,不依賴 nautilus 或 sqlalchemy —— 故可放在共用的 jimq_core。
    """

    model_config = ConfigDict(frozen=True)

    strategy_name: str
    instrument_id: str
    bar_type: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    params: dict[str, Any] = Field(default_factory=dict)

    total_return: Decimal | None = None
    sharpe: Decimal | None = None
    max_drawdown: Decimal | None = None
    num_trades: int | None = None
    final_balance: Decimal | None = None

    run_group: str | None = None
