"""卡 #20 (W1) — engine 常駐 command worker。

控制平面消費端:常駐 loop 以 ``XREADGROUP`` 消費 Redis command stream
(``COMMAND_STREAM_KEY``,DB0 上與事件 stream 區隔的另一條 key)。收到
run_backtest 命令時:

1. 依命令的 ``strategy`` 名 + ``params`` 用 strategy factory 建策略(ema_cross 先行)。
2. 依 ``symbol`` + ``timeframe`` 解析 instrument / bar_type,從 catalog 查區間 bars。
3. 跑**啟用 Redis Streams** 的 backtest(復用 #5 串流路徑;事件進 DB0 事件 stream)。
4. 把實際事件 stream key 發布到 ``LATEST_STREAM_KEY``(供 API @latest 解析、前端訂閱)。
5. 用 app 級 SQLAlchemy 回寫 backtest_run status:RUNNING → COMPLETED / FAILED。

關注點分離(利測試):
- ``parse_command_entry``:純解析一筆 stream entry → ``RunBacktestCommand``。
- ``handle_run_backtest``:跑一個命令的完整 side-effect(可單獨整合測試)。
- ``run_command_worker``:常駐 XREADGROUP loop(entrypoint / docker service)。

只連 localhost(鐵律 4);命令平面與事件 bus 共用 DB0,靠 key 區隔(B4)。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from jimq_core.constants import (
    COMMAND_CONSUMER_GROUP,
    COMMAND_STREAM_KEY,
    COMMAND_TYPE_RUN_BACKTEST,
)
from jimq_core.schemas import RunBacktestCommand
from jimq_core.timeframes import bar_type_for

from jimq_engine.catalog.ingest import open_catalog, query_bars
from jimq_engine.catalog.instruments import instrument_for
from jimq_engine.control.factory import build_strategy
from jimq_engine.control.status_writer import StatusWriter, backtest_run_db_url
from jimq_engine.streaming.redis_bus import (
    build_streaming_engine_with_strategy,
    stream_key_for,
)

logger = logging.getLogger(__name__)

# engine 把實際事件 stream key 寫到此已知 key(供 API @latest 解析;對齊
# api/src/app/ws/app_factory.py 與 scripts/run_streaming_backtest.py)。
LATEST_STREAM_KEY = "jimq:latest_stream_key"

_NS_PER_SEC = 1_000_000_000


def _decode(v: Any) -> Any:
    return v.decode() if isinstance(v, (bytes, bytearray)) else v


def parse_command_entry(
    entry: tuple[Any, Mapping[Any, Any]]
) -> RunBacktestCommand | None:
    """把一筆 command stream entry 解析成 ``RunBacktestCommand``。

    非 run_backtest 命令、或 payload 無法解析 → 回 None(安全略過)。
    """
    _entry_id, fields = entry
    fields = {_decode(k): _decode(v) for k, v in fields.items()}
    if fields.get("command_type") != COMMAND_TYPE_RUN_BACKTEST:
        return None
    payload = fields.get("payload")
    if not payload:
        return None
    try:
        return RunBacktestCommand.model_validate_json(payload)
    except Exception:  # noqa: BLE001 — 壞 payload 不可信,略過。
        logger.warning("無法解析 command payload,略過")
        return None


def _publish_latest_key(redis_client: Any, key: str) -> None:
    """把事件 stream key 寫到 LATEST_STREAM_KEY(同步 redis client)。"""
    try:
        redis_client.set(LATEST_STREAM_KEY, key)
    except Exception:  # noqa: BLE001
        logger.warning("發布 latest stream key 失敗:%s", key)


def _extract_metrics(engine: Any) -> dict[str, Any]:
    """從跑完的引擎抽結果指標(成交筆數)。最小集合;之後可擴充 return/sharpe。"""
    metrics: dict[str, Any] = {}
    try:
        metrics["num_trades"] = len(engine.cache.positions_closed())
    except Exception:  # noqa: BLE001
        pass
    return metrics


async def handle_run_backtest(
    command: RunBacktestCommand,
    *,
    writer: StatusWriter,
    catalog: Any,
    redis_client: Any,
    redis_host: str = "localhost",
    redis_port: int = 6379,
) -> str:
    """跑一個 run_backtest 命令的完整 side-effect;回傳事件 stream key。

    status RUNNING → (跑串流 backtest + 發布 stream key) → COMPLETED;
    任何例外 → FAILED 並 re-raise。``catalog`` 已開;``redis_client`` 為同步
    redis(發布 latest key 用)。
    """
    await writer.mark_running(command.run_id)
    try:
        instrument = instrument_for(command.symbol)
        bt = bar_type_for(command.symbol, command.timeframe)
        start_ns = int(command.start.timestamp() * _NS_PER_SEC)
        end_ns = int(command.end.timestamp() * _NS_PER_SEC)
        from nautilus_trader.model.data import BarType

        bars = query_bars(catalog, bar_type=BarType.from_str(bt), start=start_ns, end=end_ns)
        if not bars:
            # 區間內無資料時退而求整段(小 backtest / demo 友善);仍為真實 bars。
            bars = query_bars(catalog, bar_type=BarType.from_str(bt))
        if not bars:
            raise RuntimeError(
                f"catalog 無 {bt} bars(symbol={command.symbol});先 ingest 或灌合成資料"
            )

        strategy = build_strategy(
            command.strategy,
            instrument_id=command.symbol,
            bar_type=bt,
            params=command.params,
        )

        # 在 thread 跑(Nautilus 引擎為同步、CPU bound),不阻塞 worker event loop。
        engine = await asyncio.to_thread(
            build_streaming_engine_with_strategy,
            instrument,
            bars,
            strategy,
            redis_host=redis_host,
            redis_port=redis_port,
        )
        key = stream_key_for(engine)
        _publish_latest_key(redis_client, key)

        metrics = _extract_metrics(engine)
        await asyncio.to_thread(engine.dispose)
        await writer.mark_completed(command.run_id, metrics=metrics)
        logger.info("run %s COMPLETED;stream key=%s", command.run_id, key)
        return key
    except Exception:
        logger.exception("run %s FAILED", command.run_id)
        await writer.mark_failed(command.run_id)
        raise


# --- 常駐 loop --------------------------------------------------------------

CONSUMER_NAME = "worker-1"


async def _ensure_group(client: Any, stream_key: str, group: str) -> None:
    try:
        await client.xgroup_create(stream_key, group, id="$", mkstream=True)
    except Exception as exc:  # noqa: BLE001 — BUSYGROUP = 已存在,正常。
        if "BUSYGROUP" not in str(exc):
            raise


async def run_command_worker(
    aredis: Any,
    *,
    sync_redis: Any,
    writer: StatusWriter,
    catalog: Any = None,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    group: str = COMMAND_CONSUMER_GROUP,
    consumer: str = CONSUMER_NAME,
    stream_key: str = COMMAND_STREAM_KEY,
    block_ms: int = 5000,
    stop_event: asyncio.Event | None = None,
) -> None:
    """常駐 XREADGROUP loop:消費 command stream → 解析 → handle → ack。

    ``aredis``:async Redis(消費命令);``sync_redis``:同步 Redis(發布 latest
    stream key);``writer``:狀態回寫。``catalog`` 未給時用預設(env/JIMQ_CATALOG_PATH)。
    """
    if catalog is None:
        catalog = open_catalog()
    await _ensure_group(aredis, stream_key, group)
    while stop_event is None or not stop_event.is_set():
        try:
            resp = await aredis.xreadgroup(
                group, consumer, {stream_key: ">"}, count=1, block=block_ms
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("command XREADGROUP 失敗;退避後重試")
            await asyncio.sleep(0.5)
            continue
        if not resp:
            continue
        for _key, entries in resp:
            for entry in entries:
                entry_id = entry[0]
                command = parse_command_entry(entry)
                if command is not None:
                    try:
                        await handle_run_backtest(
                            command,
                            writer=writer,
                            catalog=catalog,
                            redis_client=sync_redis,
                            redis_host=redis_host,
                            redis_port=redis_port,
                        )
                    except Exception:  # noqa: BLE001 — handler 已回寫 FAILED;不讓 loop 崩。
                        logger.exception("處理命令失敗(已標 FAILED),繼續")
                try:
                    await aredis.xack(stream_key, group, entry_id)
                except Exception:  # noqa: BLE001
                    logger.debug("command xack 失敗(entry=%s)", entry_id)
