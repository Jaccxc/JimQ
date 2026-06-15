"""卡 #5 — Nautilus MessageBus 外部串流到本機 Redis Streams。

把 backtest(及未來 live)的引擎事件(Bar、OrderFilled、Position 開/變/平、
AccountState/PnL)經 Nautilus MessageBus 序列化(msgpack)寫入本機 Redis
Streams(``REDIS_BUS_DB=0``),供下游 consumer(卡 #7)反序列化重播。

設計:
- ``streaming_message_bus_config()`` 是**可重用**的 MessageBusConfig 工廠,
  backtest 與 live(TradingNode)共用同一份串流設定。
- ``stream_per_topic=False``:單一 stream key 聚合所有 topic(Redis 建議值),
  外部以 ``XRANGE``/``XREAD`` 取得。
- ``types_filter`` 用 Nautilus 型別排除高頻 tick(QuoteTick/TradeTick),避免
  把 bar 級策略不需要的高頻資料灌進 stream。
- stream key 結構:``trader-{trader_id}:{instance_id}:{streams_prefix}``
  (``use_trader_prefix``+``use_trader_id``+``use_instance_id`` 全開;Nautilus
  以 ``-`` 連 trader 前綴與 trader_id,其餘段以 ``:`` 連接)。

只連 localhost(鐵律 4),Redis 走本機 docker-compose(鐵律 5),
bus 用 DB0(``REDIS_BUS_DB``)。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.config import (
    DatabaseConfig,
    LoggingConfig,
    MessageBusConfig,
)
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import Bar, QuoteTick, TradeTick
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Money

from jimq_core.constants import REDIS_BUS_DB
from jimq_engine.nodes.backtest import default_fill_model
from jimq_engine.strategies.ema_cross import EMACross, EMACrossConfig

BINANCE = Venue("BINANCE")

# 串流 stream key 的 prefix 段(預設 Nautilus 值,顯式固定以利下游契約)。
STREAMS_PREFIX = "stream"

# 排除的高頻型別(Nautilus 型別)。bar 級策略不需要,避免污染 stream。
HIGH_FREQUENCY_TYPES: tuple[type, ...] = (QuoteTick, TradeTick)


def streaming_message_bus_config(
    *,
    host: str = "localhost",
    port: int = 6379,
    streams_prefix: str = STREAMS_PREFIX,
) -> MessageBusConfig:
    """可重用的 Redis Streams MessageBus 設定(backtest + live 共用)。

    - ``database``:本機 Redis(DB0 = ``REDIS_BUS_DB``;Nautilus Redis backend
      預設連 DB0)。只連 localhost。
    - ``encoding='msgpack'``:下游 consumer 用 msgpack 反序列化。
    - ``stream_per_topic=False``:單 key 聚合,外部 ``XRANGE`` 取整串。
    - key 結構 ``trader:{trader_id}:{instance_id}:{streams_prefix}``。
    - ``types_filter``:排除 QuoteTick/TradeTick 等高頻型別。
    """
    assert REDIS_BUS_DB == 0, "Nautilus Redis backend 預設 DB0;REDIS_BUS_DB 須為 0"
    return MessageBusConfig(
        database=DatabaseConfig(type="redis", host=host, port=port),  # 本機 DB0

        encoding="msgpack",
        stream_per_topic=False,
        use_trader_prefix=True,
        use_trader_id=True,
        use_instance_id=True,
        streams_prefix=streams_prefix,
        types_filter=list(HIGH_FREQUENCY_TYPES),
    )


def stream_key_for(engine: BacktestEngine, *, streams_prefix: str = STREAMS_PREFIX) -> str:
    """回傳該引擎事件落地的 Redis stream key。

    Nautilus 在 ``use_trader_prefix`` 開啟時把 ``trader`` 前綴與 trader_id 以
    ``-`` 連接,其餘段以 ``:`` 連接,故結構為:
    ``trader-{trader_id}:{instance_id}:{streams_prefix}``。
    """
    return f"trader-{engine.trader_id}:{engine.instance_id}:{streams_prefix}"


def build_streaming_engine(
    instrument: Instrument,
    bars: Sequence[Bar],
    config: EMACrossConfig,
    *,
    trader_id: str = "BACKTESTER-001",
    starting_usdt: Decimal = Decimal("1_000_000"),
    leverage: Decimal = Decimal("10"),
    random_seed: int = 42,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    streams_prefix: str = STREAMS_PREFIX,
) -> BacktestEngine:
    """組裝並 run 一個**啟用 Redis Streams 外部串流**的 BacktestEngine。

    與 ``nodes.backtest.build_engine`` 同樣的確定性 venue(NETTING + MARGIN +
    固定種子 FillModel),額外掛上 ``streaming_message_bus_config()``,使事件
    序列化落地本機 Redis Streams。回傳已 run 完的引擎(供取報表 / 取 stream key)。
    """
    engine_config = BacktestEngineConfig(
        trader_id=trader_id,
        logging=LoggingConfig(bypass_logging=True),
        message_bus=streaming_message_bus_config(
            host=redis_host,
            port=redis_port,
            streams_prefix=streams_prefix,
        ),
    )
    engine = BacktestEngine(config=engine_config)
    engine.add_venue(
        venue=BINANCE,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USDT,
        starting_balances=[Money(starting_usdt, USDT)],
        default_leverage=leverage,
        fill_model=default_fill_model(random_seed),
    )
    engine.add_instrument(instrument)
    engine.add_data(list(bars))
    engine.add_strategy(EMACross(config=config))
    engine.run()
    return engine
