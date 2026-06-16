"""jimq_core.constants — 共用常數(S0 佔位)。

目前僅定義 Redis DB index 隔離契約:Nautilus message bus/streams 與
boilerplate cache 必須使用不同的 Redis DB index(見 DEV_CONTRACT_AFK 鐵律 5
與 repo-structure-final 設計點 4)。實際數值與 .env / docker-compose 對齊。
"""

from __future__ import annotations

# Nautilus message bus / command streams 使用的 Redis DB index。
REDIS_BUS_DB: int = 0

# FastAPI boilerplate cache 使用的 Redis DB index(刻意與 bus 隔離)。
REDIS_CACHE_DB: int = 1

# --- 命令平面(B4;卡 #20 W1)------------------------------------------------
# 控制平面用 DB0(``REDIS_BUS_DB``)上的**另一條** Redis stream key,與事件
# stream(``trader-...:stream``)區隔:api 把命令信封 XADD 到此 key,engine
# 常駐 command worker 以 XREADGROUP 消費(解耦、可重播、可審計)。W2–W5 共用。
COMMAND_STREAM_KEY: str = "jimq:commands"

# run_backtest 命令的 ``command_type`` 契約字面值(大寫,對齊列舉欄位慣例)。
COMMAND_TYPE_RUN_BACKTEST: str = "RUN_BACKTEST"

# --- 研究 job 命令(卡 #23 W4)----------------------------------------------
# 從 web 觸發的研究 job(dataset build / 模型訓練)同走命令平面:api 建
# ``research_job`` 列(PENDING)+ XADD 命令信封到 ``COMMAND_STREAM_KEY``;research
# worker(獨立 venv)可 XREADGROUP 消費並回寫狀態。命令種類契約字面值(大寫):
COMMAND_TYPE_BUILD_DATASET: str = "BUILD_DATASET"
COMMAND_TYPE_TRAIN: str = "TRAIN"

# --- 策略控制命令(卡 #24 W5)----------------------------------------------
# 策略控制平面(start/stop/kill)同走命令平面:api(發布端)把控制命令信封
# XADD 到 ``COMMAND_STREAM_KEY``(與 run_backtest / research job 同 key,靠
# ``command_type`` 路由);engine 常駐 command worker XREADGROUP 消費並對
# backtest/sandbox 測試節點動作(真 live 節點控制屬 P2-S3)。命令種類契約字面值
# (大寫,對齊列舉欄位慣例):
COMMAND_TYPE_START_STRATEGY: str = "START_STRATEGY"
COMMAND_TYPE_STOP_STRATEGY: str = "STOP_STRATEGY"
# KILL 為 header 全域急停:停止策略 + 取消未成交單(對所有測試節點策略)。
COMMAND_TYPE_KILL: str = "KILL"

# command worker 的 Redis consumer group(多 worker 時 consumer 名可帶 pid)。
COMMAND_CONSUMER_GROUP: str = "jimq-engine"

# --- Live/Backtest 資料源隔離(卡 A)----------------------------------------
# 問題:live 與 backtest 共用單一 ``jimq:latest_stream_key`` + 單一熱重載 hub
# → 一跑 backtest,supervisor 把唯一 hub 切到 backtest stream,backtest 的
# buy/sell 漏進 Live 圖。解法:**雙 scope 並行消費** —— engine 依資料源把實際
# stream key 寫到不同的 latest-key;api 每 scope 各自 Hub + ConsumerSupervisor;
# 前端 WS 帶 scope。以下常數為 engine 發 key 端與 api 消費端的單一真相來源。

# 串流 scope 契約字面值(WS query ``scope`` 與 engine 發 key 端共用)。
STREAM_SCOPE_LIVE: str = "live"
STREAM_SCOPE_BACKTEST: str = "backtest"

# 各 scope 的 latest-stream-key(engine 寫、api @latest supervisor 讀)。
LIVE_LATEST_STREAM_KEY: str = "jimq:live:latest_stream_key"
BACKTEST_LATEST_STREAM_KEY: str = "jimq:backtest:latest_stream_key"

# 舊的單一 latest-key:保留供相容(舊路徑/手動工具仍可寫),前端改用分流 key。
LATEST_STREAM_KEY: str = "jimq:latest_stream_key"

# scope 字面值 → 對應 latest-key(api 雙 supervisor 與 engine 共用,避免漂移)。
SCOPE_LATEST_KEY: dict[str, str] = {
    STREAM_SCOPE_LIVE: LIVE_LATEST_STREAM_KEY,
    STREAM_SCOPE_BACKTEST: BACKTEST_LATEST_STREAM_KEY,
}
