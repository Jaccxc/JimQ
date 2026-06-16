"""卡 #30 (P2-S1b) 真資料 e2e — 單埠真全棧 app(Live 頁近期真 klines + live WS)。

延伸 #27 的真全棧脊椎,額外掛上 #30 的 **Live 頁近期真 klines** 端點,讓 web
Live 頁初始載入走真 ``/api/v1/live/bars``(testnet 期貨公開 klines,~66k)而非
2024 catalog,並由真 WS gateway 串真 live bar 逐根更新蠟燭:

- ``GET /api/v1/live/bars`` — #30 近期真 klines REST(``app.api.v1.live_bars``,
  api 直接 httpx 打 testnet.binancefuture.com 期貨公開 klines,免金鑰)。
- ``GET /api/v1/bars`` — 既有歷史 REST(Backtest 頁用;保留不動)。
- ``GET /ws/stream`` — 真 WS gateway(Redis DB0 consumer ``@latest`` 解析 live 節點
  stream key → normalize ``data.bars.`` → hub → ws)。
- 其餘 ``/`` 由 web ``dist/`` 靜態服務(SPA fallback)。

只連 localhost Redis DB0(鐵律 4/5;Binance testnet 為外部資料 venue)。⛔ data-only。
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import redis as redis_sync
from jimq_core.constants import REDIS_BUS_DB

from app.api.v1.bars import router as bars_router
from app.api.v1.live_bars import router as live_bars_router
from app.ws.app_factory import make_streaming_lifespan, resolve_stream_key
from app.ws.stream import register_ws


def build_app(*, dist_dir: str, stream_key: str) -> FastAPI:
    app = FastAPI(lifespan=make_streaming_lifespan(stream_key=stream_key))
    # #30 Live 頁近期真 klines(testnet 期貨公開,~66k 與 live 一致)。
    app.include_router(live_bars_router, prefix="/api/v1")
    # 既有歷史 REST(Backtest 頁;保留)。
    app.include_router(bars_router, prefix="/api/v1")
    # 真 WS gateway(同源 /ws/stream;讀 app.state.hub)。
    register_ws(app)

    dist = Path(dist_dir)
    index = dist / "index.html"

    @app.get("/")
    async def _root() -> FileResponse:  # noqa: D401
        return FileResponse(index)

    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def _spa(full_path: str) -> FileResponse:  # noqa: D401, ARG001
        candidate = dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    return app


def main() -> None:
    os.environ.setdefault("JIMQ_STREAM_KEY", "@latest")
    dist_dir = os.environ.get(
        "WEB_DIST", str(Path(__file__).resolve().parents[1] / "web" / "dist")
    )
    port = int(os.environ.get("REAL_STACK_PORT", "8138"))

    client = redis_sync.Redis(host="localhost", port=6379, db=REDIS_BUS_DB)
    stream_key = resolve_stream_key(client=client)
    if not stream_key:
        raise SystemExit("無法解析 @latest stream key;先起 live 節點(run_live_data.py)")
    print(f"resolved live stream key = {stream_key}")
    client.close()

    app = build_app(dist_dir=dist_dir, stream_key=stream_key)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
