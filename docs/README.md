# JimQ 文件索引

> JimQ:以 NautilusTrader 為基底的量化交易平台。目標 — 用量化交易盡可能賺錢,含 DL/RL 與另類資料整合。
> 命名規則:文件以時間戳 + 短訊息命名(`YYYYMMDD-HHMM-短訊息.md`)。

## 🔴 AFK 回來先看這裡
- **[`decisions-to-grill.md`](./decisions-to-grill.md)** — 所有待你拍板的決策清單,設計給 `/grill-me` 用。建議直接執行 `/grill-me`。

## 研究(research/)— NautilusTrader 能力調查
- [`20260616-nautilus-core.md`](./research/20260616-nautilus-core.md) — 核心架構:Rust 核心 + Python、引擎、MessageBus、領域模型、Actor/Strategy、backtest/live parity、Parquet catalog。
- [`20260616-nautilus-ml-rl.md`](./research/20260616-nautilus-ml-rl.md) — ⭐ ML/DL/RL 整合。**關鍵發現:無原生 RL gym wrapper,`run()` 與 `step()` 阻抗不匹配。**
- [`20260616-nautilus-infra.md`](./research/20260616-nautilus-infra.md) — Redis/Postgres/ZeroMQ、TradingNode 部署、adapters、串流、uv 安裝。
- [`20260616-frontend-viz.md`](./research/20260616-frontend-viz.md) — Vue3 + FastAPI dashboard、Lightweight Charts、WebSocket、Redis Streams 橋接。

## 設計(design/)
- [`20260616-1200-architecture-overview.md`](./design/20260616-1200-architecture-overview.md) — 系統架構總覽、元件圖、docker 服務、分期路線圖。
- [`20260616-1210-tech-stack-decisions.md`](./design/20260616-1210-tech-stack-decisions.md) — ADR 草案(AD-1~AD-13),每條含立場/理由/待確認。
- [`20260616-1220-repo-structure.md`](./design/20260616-1220-repo-structure.md) — monorepo + uv workspace 資料夾規劃。

## 目前狀態
- ✅ 研究完成(4 份)、架構草案完成、決策清單就緒。
- ⏳ **尚未寫任何程式碼**。等 `/grill-me` 確認決策後才進入 Phase 0 地基。

## 核心結論速覽
1. **Nautilus 做確定性事件引擎 + research→live parity + 擬真執行**;不硬塞 RL `step()` 訓練。
2. **RL:獨立 Gym 環境訓練 + Nautilus 部署**(無原生 gym 支援)。
3. **Redis Streams 是引擎與外圍的唯一接縫**;ZeroMQ 第一期可能不需要。
4. **Postgres 只放我們自己的應用資料**,不當 Nautilus cache(未成熟)。
5. **先打通最簡策略的端到端垂直切片**,再加 RL 與另類資料。
