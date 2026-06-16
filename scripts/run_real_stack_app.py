"""卡 #27 (P2-S1) 真資料 e2e — 單埠真全棧 app(history REST + live WS + 靜態 web)。

把**真** api 串流脊椎組成一個同源 app,供 Playwright 連真 web Live 頁佐證真
Binance testnet 即時資料(非 mock):
- ``GET /api/v1/bars`` — 真歷史 K 線 REST(``api.v1.bars`` router,讀 catalog)。
- ``GET /ws/stream`` — 真 WS gateway(``build_streaming_app`` lifespan:Redis DB0
  consumer ``@latest`` 解析 live 節點 stream key → normalize ``data.bars.`` →
  hub → ws)。
- 其餘 ``/`` 由 web ``dist/`` 靜態檔服務(SPA fallback 到 index.html)。

只連 localhost Redis DB0(鐵律 4/5;Binance testnet 為外部資料 venue)。⛔ data-only。
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.bars import router as bars_router
from app.ws.app_factory import make_streaming_lifespan, resolve_stream_key

import redis as redis_sync
from jimq_core.constants import REDIS_BUS_DB

from app.ws.stream import register_ws


def build_app(*, dist_dir: str, stream_key: str) -> FastAPI:
    app = FastAPI(lifespan=make_streaming_lifespan(stream_key=stream_key))
    # 真歷史 REST(同源 /api/v1/bars)。
    app.include_router(bars_router, prefix="/api/v1")
    # 真 WS gateway(同源 /ws/stream;讀 app.state.hub)。
    register_ws(app)

    dist = Path(dist_dir)
    index = dist / "index.html"

    @app.get("/")
    async def _root() -> FileResponse:  # noqa: D401
        return FileResponse(index)

    # 靜態資產(assets/ 等);未命中的前端路由由前面的 SPA fallback 處理。
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
    dist_dir = os.environ.get("WEB_DIST", str(Path(__file__).resolve().parents[1] / "web" / "dist"))
    port = int(os.environ.get("REAL_STACK_PORT", "8137"))

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
