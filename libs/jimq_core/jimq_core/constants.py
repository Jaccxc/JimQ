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
