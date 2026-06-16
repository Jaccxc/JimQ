"""卡 #30 (P2-S1b) — GET /api/v1/live/bars 端點(Live 頁近期真 klines)。

Live 頁初始載入不再用 2024 回測 catalog;改載**近期真實** klines —— 從 Binance
USDT-M 期貨 **testnet** 公開 klines REST(``testnet.binancefuture.com/fapi/v1/klines``)
取最近 N 根,映射成共用契約 ``jimq_core.schemas.BarDTO`` 回出。與 live WS bar
**同 venue(testnet)**,價位一致(~66k),消除 40k/66k 斷裂。

設計(對齊 mlflow proxy 慣例,本地決策):
- api **不 import engine**(保持精簡;engine 為另一 workspace 套件):直接用注入的
  async httpx client 打公開 klines REST。
- **公開端點免金鑰**:klines 為公開資料,不需 API key(⛔ 本卡仍 read-only,不下單)。
- **注入 HTTP client**:``get_klines_http`` 依賴回 async httpx client,測試 override
  成 fake(不需真網路)。
- symbol 形如 ``BTCUSDT-PERP.BINANCE``(前端 instrument_id)→ 取 raw ``BTCUSDT``
  打 klines。
- 映射:klines raw row ``[openTime_ms, open, high, low, close, volume, ...]`` →
  BarDTO ``ts``(epoch 奈秒)、``time``(epoch 秒,餵 LWC)、字串 OHLCV 保留精度。
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from jimq_core.schemas import BarDTO

router = APIRouter(prefix="/live", tags=["live"])

# 同 live 資料節點 venue:Binance USDT-M 期貨 **testnet** 公開 klines。
# 價位才與 live 串流一致(~66k)。
TESTNET_KLINES_URL = "https://testnet.binancefuture.com/fapi/v1/klines"

_MS_PER_SEC = 1_000
_NS_PER_MS = 1_000_000


def get_klines_http() -> Any:
    """注入 async HTTP client(httpx;測試可 override 成 fake)。"""
    return httpx.AsyncClient(timeout=15.0)


def _raw_symbol(symbol: str) -> str:
    """前端 instrument_id(``BTCUSDT-PERP.BINANCE``)→ Binance raw symbol(``BTCUSDT``)。"""
    base = symbol.split(".", 1)[0]  # 去掉 .BINANCE venue 後綴
    return base.replace("-PERP", "").replace("-", "")


def _row_to_dto(row: list) -> BarDTO:
    """Binance klines raw row → BarDTO(字串 OHLCV 保留交易所精度)。"""
    open_ms = int(row[0])
    return BarDTO(
        ts=open_ms * _NS_PER_MS,
        time=open_ms // _MS_PER_SEC,
        open=str(row[1]),
        high=str(row[2]),
        low=str(row[3]),
        close=str(row[4]),
        volume=str(row[5]),
    )


@router.get(
    "/bars",
    response_model=list[BarDTO],
    summary="Live 頁近期真 klines(testnet 期貨公開 REST → BarDTO)",
)
async def get_live_bars(
    symbol: str = Query(..., description="如 BTCUSDT-PERP.BINANCE"),
    timeframe: str = Query("1m", description="Binance kline interval,如 1m / 5m"),
    limit: int = Query(500, ge=1, le=1500, description="取最近 N 根(Binance 上限 1500)"),
    client=Depends(get_klines_http),
) -> list[BarDTO]:
    """從 testnet 期貨公開 klines 取最近 ``limit`` 根,回 BarDTO 列表。"""
    try:
        resp = await client.get(
            TESTNET_KLINES_URL,
            params={
                "symbol": _raw_symbol(symbol),
                "interval": timeframe,
                "limit": limit,
            },
        )
        resp.raise_for_status()
        rows = resp.json()
    finally:
        await client.aclose()
    return [_row_to_dto(r) for r in rows]
