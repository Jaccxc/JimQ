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

# command worker 的 Redis consumer group(多 worker 時 consumer 名可帶 pid)。
COMMAND_CONSUMER_GROUP: str = "jimq-engine"
