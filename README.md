# JimQ

以 [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) 為基底的量化交易平台。
目標:用量化交易盡可能賺錢 — 支援 live 交易、backtesting、策略開發,並整合 DL/RL 與另類資料。

## 狀態
🚧 **設計階段。尚無程式碼。** 研究與架構草案已完成,等決策拍板後進入 Phase 0 地基。

## 規劃技術棧
- **引擎**:NautilusTrader(Rust 核心 + Python),uv 管理,Docker 部署
- **狀態/串流**:Redis(Cache + MessageBus Streams)
- **應用資料**:PostgreSQL
- **後端**:FastAPI(REST + WebSocket gateway)
- **前端**:Vue 3 + Vite + TS + Pinia + Lightweight Charts(K 線視覺化)
- **研究**:PyTorch + Gym/RL(GPU)

## 文件
所有研究、架構與決策見 **[`docs/`](./docs/)**。從 [`docs/README.md`](./docs/README.md) 開始。

⚠️ 待決策清單:**[`docs/decisions-to-grill.md`](./docs/decisions-to-grill.md)**(設計給 `/grill-me`)。
