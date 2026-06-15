"""歷史 bars REST 端點(卡 #8)。

``GET /api/v1/bars`` — query 參數 symbol / timeframe / start / end,回傳共用契約
``jimq_core.schemas.BarDTO`` 列表(對齊前端 Lightweight Charts)。

read 路徑非阻塞:同步的 catalog 讀取(store.query_bars)以 ``run_in_threadpool``
包裝,避免阻塞 event loop(鐵律:read 路徑非阻塞)。

catalog 路徑預設為 store.DEFAULT_CATALOG_PATH;可由 ``JIMQ_CATALOG_PATH`` 環境
變數覆寫(部署/測試指向不同 catalog)。
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from jimq_core.schemas import BarDTO

from ...services import store

router = APIRouter(tags=["bars"])


def _catalog_path() -> str | None:
    """請求時解析 catalog 路徑覆寫(None → store 預設)。"""
    return os.environ.get("JIMQ_CATALOG_PATH") or None


@router.get("/bars", response_model=list[BarDTO])
async def get_bars(
    symbol: str = Query(..., description="如 BTCUSDT-PERP.BINANCE"),
    timeframe: str = Query(..., description="如 1m / 5m"),
    start: int | None = Query(None, description="起始 epoch 奈秒(含)"),
    end: int | None = Query(None, description="結束 epoch 奈秒(含)"),
) -> list[BarDTO]:
    """查一段歷史 K 線。未知 symbol/timeframe 或空區間回空列表。"""
    return await run_in_threadpool(
        store.query_bars,
        symbol,
        timeframe,
        start,
        end,
        catalog_path=_catalog_path(),
    )
