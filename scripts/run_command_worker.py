"""卡 #20 (W1) — engine 常駐 command worker entrypoint。

啟動控制平面消費端:連本機 Redis(DB0)消費 command stream
(``jimq:commands``),收到 run_backtest 命令時跑啟用 Redis Streams 的 backtest、
把事件 stream key 發布到 ``jimq:latest_stream_key``(供 API @latest 解析、前端
即時訂閱),並以 app 級 SQLAlchemy 回寫 backtest_run 狀態。

用法:
    uv run python scripts/run_command_worker.py

環境(皆 localhost 預設;鐵律 4):
    REDIS_HOST / REDIS_PORT     — Redis(bus DB0 + command stream)
    POSTGRES_* / DATABASE_URL   — backtest_run 狀態回寫的 Postgres
    JIMQ_CATALOG_PATH           — ParquetDataCatalog 路徑(可選)

可作為 docker service(engine 新 entrypoint)。Ctrl-C 優雅停止。
"""

from __future__ import annotations

import asyncio
import logging
import os

import redis as redis_sync
import redis.asyncio as aioredis

from jimq_core.constants import REDIS_BUS_DB

from jimq_engine.catalog.ingest import open_catalog
from jimq_engine.control.status_writer import StatusWriter, backtest_run_db_url
from jimq_engine.control.trade_writer import TradeWriter
from jimq_engine.control.worker import run_command_worker


def _redis_host_port() -> tuple[str, int]:
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    return host, port


async def _main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    log = logging.getLogger("jimq.command_worker")

    host, port = _redis_host_port()
    # socket_timeout 須 > XREADGROUP block(預設 5s),否則阻塞讀會被 client 逾時。
    aredis = aioredis.from_url(
        f"redis://{host}:{port}/{REDIS_BUS_DB}", socket_timeout=30
    )
    sync_redis = redis_sync.Redis(host=host, port=port, db=REDIS_BUS_DB)
    writer = StatusWriter(backtest_run_db_url())
    trade_writer = TradeWriter(backtest_run_db_url())  # 卡 #21:成交持久化
    catalog = open_catalog()

    stop = asyncio.Event()
    log.info("command worker 啟動(Redis %s:%s DB%s);等待命令…", host, port, REDIS_BUS_DB)
    try:
        await run_command_worker(
            aredis,
            sync_redis=sync_redis,
            writer=writer,
            catalog=catalog,
            redis_host=host,
            redis_port=port,
            stop_event=stop,
            trade_writer=trade_writer,
        )
    finally:
        await aredis.aclose()
        sync_redis.close()
        await writer.aclose()
        await trade_writer.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
