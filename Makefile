# JimQ — 常用指令。輸入 `make` 看清單。
# 全棧 = redis / postgres / api / web / command-worker(docker compose)。
# 開瀏覽器一律 http://127.0.0.1:8080
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down build logs exp full-restart ps live paper reload

help: ## 顯示這份清單
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  make %-13s %s\n", $$1, $$2}'

up: ## 起全棧 → 開 http://127.0.0.1:8080(首次自動 build)
	$(COMPOSE) up -d
	@echo "✅ 全棧已起 → 開 http://127.0.0.1:8080"

down: ## 停全棧(資料保留)
	$(COMPOSE) down

build: ## 改了程式碼後重建 api/web/engine 映像
	$(COMPOSE) build

logs: ## 跟看全棧 log(Ctrl-C 離開,不會停服務)
	$(COMPOSE) logs -f

exp: ## 跑一次回測實驗:灌真歷史 + EMA backtest → 重整儀表板
	$(COMPOSE) --profile demo run --rm engine
	$(COMPOSE) restart api
	@echo "✅ 回測完成 → 開 http://127.0.0.1:8080 看 K 線 + 進出場"

full-restart: ## 砍掉重練:down → build → up → logs
	$(COMPOSE) down
	$(COMPOSE) build
	$(COMPOSE) up -d
	@echo "✅ 重建完成 → 開 http://127.0.0.1:8080,以下是 log:"
	$(COMPOSE) logs -f

ps: ## 看服務狀態
	$(COMPOSE) ps

# ── live(連 Binance testnet,需 .env.afk 金鑰;先 make up)──────────
# 用法:此終端跑 make live(或 paper)→ 另開終端跑一次 make reload → 開瀏覽器。
live: ## 接 testnet 真即時 K 線(read-only,不下單)
	@echo "ℹ️  資料開始流入後,另開終端跑一次 'make reload',再開 http://127.0.0.1:8080 → Live 頁"
	uv run python scripts/run_live_data.py

paper: ## testnet paper 下單(⛔ 假錢,真在 testnet 成交)
	@echo "ℹ️  下單開始後,另開終端跑一次 'make reload',再開 http://127.0.0.1:8080 → Live 頁"
	uv run python scripts/run_live_trade.py

reload: ## live/paper 開跑後,讓儀表板接上本次串流(跑一次)
	$(COMPOSE) restart api
	@echo "✅ 儀表板已接上 → 開 http://127.0.0.1:8080"
