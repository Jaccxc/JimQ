"""卡 #7 — WebSocket 串流 gateway(多工 channel)。

端點 ``GET /ws/stream``(WebSocket;query 參數):
- ``channels``:逗號分隔要訂的 channel(bars/orders/fills/positions/pnl)。
- ``last_seq``(選):上次看到的 seq;連上先回補 ``(last_seq, latest]`` 缺口。
- ``heartbeat_s``(選):閒置心跳間隔(秒,預設 ``DEFAULT_HEARTBEAT_S``)。

連線流程:
1. 對 ``app.state.hub`` ``subscribe`` 訂閱的 channel(**先訂閱**,避免快照與
   後續 delta 之間漏事件);pnl/positions 用 last-value-wins coalesce。
2. 送**補洞**(若帶 last_seq)→ 送**快照**(目前已知狀態)→ 送 ``{"type":"live"}``
   分界;以上每筆帶 ``"snapshot": true``(快照)或原 seq(補洞)。
3. 進**串流迴圈**:從有界佇列取 delta 送出;閒置超過 heartbeat 間隔送 heartbeat。
   已在快照/補洞送過的 seq 不重送(去重,不重複不遺漏)。

斷線(``WebSocketDisconnect`` 或 cancel)時 ``unsubscribe`` 清掉訂閱。
有界佇列與溢出策略由 hub 的 ``Subscription`` 保證(drop-oldest / last-value-wins)。
"""

from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from jimq_core.constants import STREAM_SCOPE_LIVE

from ..services.hub import Hub

# 預設心跳間隔(秒)。
DEFAULT_HEARTBEAT_S = 15.0
# 每連線有界佇列大小(本地決策;溢出走 hub 的 drop-oldest / coalesce)。
DEFAULT_QUEUE_MAXSIZE = 256
# 快照採 last-value-wins coalesce 的 channel(高頻覆寫,只在意最新值)。
COALESCE_CHANNELS = frozenset({"pnl", "positions"})

# 對外路由路徑。
WS_PATH = "/ws/stream"


def _parse_channels(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {c.strip() for c in raw.split(",") if c.strip()}


async def _stream(ws: WebSocket, hub: Hub) -> None:
    params = ws.query_params
    channels = _parse_channels(params.get("channels"))
    if not channels:
        await ws.close(code=1008)  # policy violation:必須指定 channels。
        return
    last_seq = int(params.get("last_seq", 0) or 0)
    heartbeat_s = float(params.get("heartbeat_s", DEFAULT_HEARTBEAT_S))

    await ws.accept()
    sub = hub.subscribe(
        channels,
        maxsize=DEFAULT_QUEUE_MAXSIZE,
        coalesce_channels=channels & COALESCE_CHANNELS,
    )
    # 去重:快照/補洞送過的 seq 不在串流階段重送。
    sent_seqs: set[int] = set()
    try:
        # 1) 補洞(client 帶 last_seq 重連)。
        if last_seq > 0:
            for env in hub.backfill_since(last_seq=last_seq, channels=channels):
                await ws.send_json(env)
                sent_seqs.add(env["seq"])
        # 2) 快照(目前已知狀態)。
        for env in hub.snapshot(channels):
            if env["seq"] in sent_seqs:
                continue
            await ws.send_json({**env, "snapshot": True})
            sent_seqs.add(env["seq"])
        # 3) live 分界。
        await ws.send_json({"type": "live"})

        # 4) 串流迴圈:delta + 心跳。
        while True:
            try:
                env = await asyncio.wait_for(sub.queue.get(), timeout=heartbeat_s)
            except asyncio.TimeoutError:
                await ws.send_json({"type": "heartbeat", "ts": time.time()})
                continue
            if env["seq"] in sent_seqs:
                continue  # 已在快照/補洞送過,不重送。
            await ws.send_json(env)
            sent_seqs.add(env["seq"])
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(sub)


def _resolve_hub(ws: WebSocket) -> Hub:
    """依 ``scope`` query 取對應 scope 的 hub(卡 A:live/backtest 資料源隔離)。

    - ``app.state.scoped_hubs[scope]`` 存在 → 用該 scope hub(live / backtest)。
    - 未帶 scope / 未知 scope / 無 scoped_hubs(單 scope 部署)→ 退回
      ``app.state.hub``(現狀相容)。
    """
    state = ws.app.state
    scope = ws.query_params.get("scope", STREAM_SCOPE_LIVE)
    scoped = getattr(state, "scoped_hubs", None)
    if scoped is not None and scope in scoped:
        return scoped[scope]
    return state.hub


def register_ws(app: FastAPI) -> None:
    """把 WS gateway 掛到 FastAPI app(依 ``scope`` query 路由到對應 hub)。"""

    @app.websocket(WS_PATH)
    async def stream_endpoint(ws: WebSocket) -> None:  # noqa: D401
        hub = _resolve_hub(ws)
        await _stream(ws, hub)
