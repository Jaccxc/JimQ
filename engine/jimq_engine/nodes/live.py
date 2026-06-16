"""卡 #27 (P2-S1) — Binance USDT-M Futures testnet **live 資料節點**。

組裝一個 data-only 的 Nautilus ``TradingNode``:用 BinanceLiveDataClientFactory
連 **testnet**(USDT-M Futures),訂閱 BTCUSDT-PERP 即時 bar(內部聚合),把事件
經 Nautilus MessageBus 序列化(msgpack)落地**本機 Redis Streams**(DB0),供既有
consumer(#7)→ WS gateway → 前端 chart 顯示真即時資料。

設計:
- **復用 #5 串流脊椎**:``streaming.redis_bus.streaming_message_bus_config()`` 直接
  當 live 節點的 MessageBusConfig(同一份 Redis Streams 設定;types_filter 排
  QuoteTick/TradeTick 高頻 tick 避免淹沒,只串 bar 級事件)。
- **data-only**:只加 data client,**不加 exec client**(本卡只接 read-only 市場
  資料,⛔ 不下任何單;下單在 P2-S2/S3)。
- 訂閱由一個輕量 ``BarSubscriberActor`` 在 ``on_start`` 觸發 ``subscribe_bars``;
  bar 事件以 ``data.bars.{bar_type}`` topic 發佈,對應下游 consumer 的 bars channel。
- 金鑰只從參數/env(``BINANCE_TESTNET_KEY`` / ``BINANCE_TESTNET_SECRET``)注入,
  **絕不硬編、絕不 commit**(issue #25 不加硬編 default)。
- 只連 localhost Redis(鐵律 4/5;Binance testnet 為外部 venue API,屬資料來源,允許)。
"""

from __future__ import annotations

import os

from nautilus_trader.adapters.binance.common.enums import (
    BinanceAccountType,
    BinanceEnvironment,
    BinanceKeyType,
)
from nautilus_trader.adapters.binance.config import (
    BinanceDataClientConfig,
    BinanceExecClientConfig,
)
from nautilus_trader.common import Environment
from nautilus_trader.common.actor import Actor, ActorConfig
from nautilus_trader.config import (
    ImportableActorConfig,
    ImportableStrategyConfig,
    InstrumentProviderConfig,
    LiveDataEngineConfig,
    LiveExecEngineConfig,
    LiveRiskEngineConfig,
    LoggingConfig,
    TradingNodeConfig,
)
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId, Venue

from jimq_engine.catalog.instruments import BTCUSDT_PERP_BINANCE_ID
from jimq_engine.streaming.redis_bus import streaming_message_bus_config

BINANCE = Venue("BINANCE")

# live 資料節點的 trader_id(與 backtester 區隔;LIVE-TESTNET 來源辨識)。
LIVE_TRADER_ID = "JIMQ-LIVE-001"

# 訂閱的 bar 規格:1 分鐘 LAST 價、EXTERNAL(由 venue 聚合 / adapter 內部聚合)。
DEFAULT_BAR_SPEC = "1-MINUTE-LAST-EXTERNAL"


def btcusdt_perp_bar_type(bar_spec: str = DEFAULT_BAR_SPEC) -> BarType:
    """BTCUSDT-PERP.BINANCE 的 BarType(預設 1分 LAST EXTERNAL)。

    str 形如 ``BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL``,Nautilus 以
    ``data.bars.{bar_type}`` topic 發佈 → 對應下游 consumer 的 bars channel 前綴。
    """
    return BarType.from_str(f"{BTCUSDT_PERP_BINANCE_ID}-{bar_spec}")


class BarSubscriberConfig(ActorConfig, frozen=True):
    """BarSubscriberActor 設定:要訂閱的 bar_type 字串。"""

    bar_type: str


class TradeTickSubscriberConfig(ActorConfig, frozen=True):
    """TradeTickSubscriberActor 設定:要訂閱 TradeTick 的 instrument_id 字串。"""

    trade_tick_instrument_id: str


class TradeTickSubscriberActor(Actor):
    """卡 B(Live 次秒 tick)— data-only actor:訂閱 BTCUSDT-PERP **逐筆成交** TradeTick。

    ⛔ 最高優先鐵律:**tick 純視覺,絕不進策略**。本 actor 不持任何交易邏輯、
    不下單、不重算 EMA —— 它只是讓 live data client 把 TradeTick 推進 MessageBus
    (→ Redis Streams ``data.trades.{venue}.{symbol}`` topic → consumer 'trades'
    channel → 前端),供前端把每筆成交價聚合到「形成中、尚未收線」那根 1m K 線的
    視覺更新。策略決策仍只在 1m bar 收線時跑一次(EMACross.on_bar 不變),
    保住回測/live parity。
    """

    def __init__(self, config: TradeTickSubscriberConfig) -> None:
        super().__init__(config)
        self._instrument_id = InstrumentId.from_str(config.trade_tick_instrument_id)

    def on_start(self) -> None:
        self.subscribe_trade_ticks(self._instrument_id)

    def on_trade_tick(self, tick) -> None:  # noqa: ANN001 — Nautilus callback
        # ⛔ 純記錄,不進策略;事件由 MessageBus 外部串流落地 Redis(僅供視覺)。
        self.log.debug(f"live trade tick: {tick!r}")


class BarSubscriberActor(Actor):
    """data-only actor:啟動時訂閱指定 bar_type 的即時 bar(不下單)。

    Nautilus live data client 連上 venue 後,actor 的 ``subscribe_bars`` 讓引擎
    把該 bar_type 的即時 bar 推進 MessageBus(→ Redis Streams)。不持有任何
    交易邏輯,純資料訂閱(P2-S2 起才接策略/下單)。
    """

    def __init__(self, config: BarSubscriberConfig) -> None:
        super().__init__(config)
        self._bar_type = BarType.from_str(config.bar_type)

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)

    def on_bar(self, bar) -> None:  # noqa: ANN001 — Nautilus callback
        # 純記錄;事件由 MessageBus 外部串流落地 Redis(下游消費)。
        self.log.info(f"live bar: {bar!r}")


def _trade_tick_actor_config(
    instrument_id: str = str(BTCUSDT_PERP_BINANCE_ID),
) -> ImportableActorConfig:
    """卡 B:訂 BTCUSDT-PERP TradeTick 的 data-only actor 設定(視覺次秒串流)。

    ⛔ 純視覺:逐筆成交經 MessageBus → Redis ``data.trades.`` topic → 前端;
    不進策略決策路徑。data 與 trade 節點共用此 actor。
    """
    return ImportableActorConfig(
        actor_path=f"{TradeTickSubscriberActor.__module__}:{TradeTickSubscriberActor.__qualname__}",
        config_path=f"{TradeTickSubscriberConfig.__module__}:{TradeTickSubscriberConfig.__qualname__}",
        config={"trade_tick_instrument_id": instrument_id},
    )


def binance_testnet_data_client_config(
    *, api_key: str, api_secret: str
) -> BinanceDataClientConfig:
    """Binance USDT-M Futures **testnet** data client 設定(HMAC 金鑰)。

    金鑰由參數注入(實務從 ``.env.afk`` 的 ``BINANCE_TESTNET_KEY`` /
    ``BINANCE_TESTNET_SECRET`` 讀);**不硬編、不 commit**。
    """
    return BinanceDataClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        key_type=BinanceKeyType.HMAC,
        account_type=BinanceAccountType.USDT_FUTURES,
        environment=BinanceEnvironment.TESTNET,
        instrument_provider=InstrumentProviderConfig(load_all=True),
    )


def build_live_data_node_config(
    *,
    api_key: str,
    api_secret: str,
    bar_spec: str = DEFAULT_BAR_SPEC,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    trader_id: str = LIVE_TRADER_ID,
) -> TradingNodeConfig:
    """組裝 data-only live 節點的 ``TradingNodeConfig``(Binance testnet)。

    - environment = LIVE(走 live engine + adapter)。
    - 一個 BINANCE data client(testnet / USDT_FUTURES / HMAC)。
    - **無 exec client**(不下單)。
    - message_bus = #5 可重用 streaming 設定(Redis Streams DB0,排高頻 tick)。
    - 一個 BarSubscriberActor 訂閱 BTCUSDT-PERP bar。
    """
    bar_type = f"{BTCUSDT_PERP_BINANCE_ID}-{bar_spec}"
    return TradingNodeConfig(
        trader_id=trader_id,
        environment=Environment.LIVE,
        logging=LoggingConfig(log_level="INFO"),
        # 卡 B:include_trade_ticks=True → bus 放行 TradeTick(只排 QuoteTick),
        # 逐筆成交序列化進 Redis 供前端視覺聚合(⛔ tick 純視覺,不進策略)。
        message_bus=streaming_message_bus_config(
            host=redis_host, port=redis_port, include_trade_ticks=True
        ),
        data_engine=LiveDataEngineConfig(),
        data_clients={
            str(BINANCE): binance_testnet_data_client_config(
                api_key=api_key, api_secret=api_secret
            ),
        },
        # ⛔ 無 exec_clients:本卡只接 read-only 資料,不下任何單。
        actors=[
            ImportableActorConfig(
                actor_path=f"{BarSubscriberActor.__module__}:{BarSubscriberActor.__qualname__}",
                config_path=f"{BarSubscriberConfig.__module__}:{BarSubscriberConfig.__qualname__}",
                config={"bar_type": bar_type},
            ),
            # 卡 B:額外訂 TradeTick(視覺次秒串流;不進策略)。
            _trade_tick_actor_config(),
        ],
    )


def credentials_from_env() -> tuple[str, str]:
    """從 env 讀 Binance testnet HMAC 金鑰(``.env.afk`` 載入後)。

    缺金鑰時拋 ``RuntimeError``(不提供任何硬編 default;絕不 commit 金鑰)。
    """
    key = os.environ.get("BINANCE_TESTNET_KEY")
    secret = os.environ.get("BINANCE_TESTNET_SECRET")
    if not key or not secret:
        raise RuntimeError(
            "缺 BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET;"
            "請在 .env.afk 設定(絕不 commit 金鑰)"
        )
    return key, secret


# ====================================================================== #
# 卡 #28 (P2-S2) — Binance testnet **live 交易節點**(data + exec,下 paper 單)
# ====================================================================== #

# 預設 paper 單規格(小額,假錢):0.001 BTC,SL/TP 寬鬆,確保近期交叉能成交。
DEFAULT_PAPER_TRADE_SIZE = "0.001"
# fast/slow EMA 預設(短週期,使近期 1m bar 上更易觸發交叉 → 可驗 round-trip)。
DEFAULT_FAST_PERIOD = 3
DEFAULT_SLOW_PERIOD = 8

# 卡 #29 (P2-S3) 風控預設(Nautilus 原生 RiskEngine;不自造平行風控)。
# 名目上限:保守 200 USDT。對應 0.001 BTC(@ ~數萬 USDT)安全範圍 + buffer;
# 超過此名目的單會被 RiskEngine DENIED(MAX_NOTIONAL_EXCEEDED),不送到 venue。
DEFAULT_MAX_NOTIONAL_USDT = 200
# 下單頻率上限(throttler):保守 10 單/秒(Nautilus 預設為 100/秒,過鬆)。
DEFAULT_MAX_ORDER_SUBMIT_RATE = "10/00:00:01"


def build_risk_engine_config(
    *,
    max_notional: int = DEFAULT_MAX_NOTIONAL_USDT,
    max_order_submit_rate: str = DEFAULT_MAX_ORDER_SUBMIT_RATE,
    instrument_id: str = str(BTCUSDT_PERP_BINANCE_ID),
) -> LiveRiskEngineConfig:
    """組裝 Nautilus 原生 **LiveRiskEngineConfig**(名目上限 + 下單頻率上限)。

    - ``max_notional_per_order``:{instrument_id: 上限 USDT};超限單被 RiskEngine
      DENIED,不送 venue(風控攔截真行為由 backtest 引擎驗證,不需 testnet)。
    - ``max_order_submit_rate``:throttler 頻率上限字串(如 ``"10/00:00:01"``)。
    - ⛔ ``bypass=False``:風控不可被繞過(否則上限形同虛設)。
    """
    return LiveRiskEngineConfig(
        bypass=False,
        max_notional_per_order={instrument_id: max_notional},
        max_order_submit_rate=max_order_submit_rate,
    )


class MainnetBlockedError(RuntimeError):
    """⛔ 最高優先安全:偵測到非 testnet(mainnet / LIVE / DEMO)交易設定時拋出。"""


def assert_testnet_only(environment) -> None:  # noqa: ANN001 — BinanceEnvironment
    """硬性 testnet-only 閘:任何非 ``BinanceEnvironment.TESTNET`` 一律拒絕。

    ⛔ 本卡只在 Binance USDT-M Futures **testnet**(假錢)下單。對 LIVE(真盤
    mainnet)/ DEMO 一律拋 ``MainnetBlockedError``,程式硬性阻擋真錢交易。
    """
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

    if environment != BinanceEnvironment.TESTNET:
        raise MainnetBlockedError(
            "⛔ 阻擋非 testnet 交易設定:本卡硬性 testnet-only(假錢),"
            f"拒絕 environment={environment!r}(僅允許 BinanceEnvironment.TESTNET)。"
            "嚴禁 mainnet / 真實資金。"
        )


def binance_testnet_exec_client_config(
    *, api_key: str, api_secret: str
) -> BinanceExecClientConfig:
    """Binance USDT-M Futures **testnet** exec client 設定(HMAC 金鑰)。

    ⛔ 硬性 ``BinanceEnvironment.TESTNET``;金鑰由參數注入(實務從 env 讀),
    不硬編、不 commit。本 client 負責把 paper 單送達 testnet 並回報成交/部位。
    """
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

    return BinanceExecClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        key_type=BinanceKeyType.HMAC,
        account_type=BinanceAccountType.USDT_FUTURES,
        environment=BinanceEnvironment.TESTNET,  # ⛔ 永遠 testnet
        instrument_provider=InstrumentProviderConfig(load_all=True),
        use_reduce_only=True,
    )


def ema_cross_strategy_config(
    *,
    bar_spec: str = DEFAULT_BAR_SPEC,
    trade_size: str = DEFAULT_PAPER_TRADE_SIZE,
    fast_period: int = DEFAULT_FAST_PERIOD,
    slow_period: int = DEFAULT_SLOW_PERIOD,
    use_bracket: bool = False,
) -> ImportableStrategyConfig:
    """ema_cross 策略的 ImportableStrategyConfig(與 backtest 共用同碼)。

    只換 adapter/設定(live testnet vs backtest catalog),策略邏輯不變 →
    research↔live parity。小額 paper 單(0.001 BTC),短 EMA 週期使近期 1m
    bar 上更易觸發交叉,利 round-trip 驗證。

    ``use_bracket=False``(live 預設):下純 MARKET 進場單。Binance USDT-M Futures
    adapter 不支援 bracket 的 OCO 條件單(本地 RiskEngine 會 OrderDenied
    ``UNSUPPORTED_OCO_CONDITIONAL_ORDERS``,單根本送不到 venue),故 live testnet
    路徑用純市價單才能真送達成交完成 round-trip。交叉偵測邏輯與 backtest 共用 → parity。
    """
    bar_type = f"{BTCUSDT_PERP_BINANCE_ID}-{bar_spec}"
    return ImportableStrategyConfig(
        strategy_path="jimq_engine.strategies.ema_cross:EMACross",
        config_path="jimq_engine.strategies.ema_cross:EMACrossConfig",
        config={
            "instrument_id": str(BTCUSDT_PERP_BINANCE_ID),
            "bar_type": bar_type,
            "fast_period": fast_period,
            "slow_period": slow_period,
            "trade_size": trade_size,
            "use_bracket": use_bracket,
        },
    )


def build_live_trade_node_config(
    *,
    api_key: str,
    api_secret: str,
    bar_spec: str = DEFAULT_BAR_SPEC,
    trade_size: str = DEFAULT_PAPER_TRADE_SIZE,
    fast_period: int = DEFAULT_FAST_PERIOD,
    slow_period: int = DEFAULT_SLOW_PERIOD,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    trader_id: str = LIVE_TRADER_ID,
    environment=None,  # noqa: ANN001 — BinanceEnvironment;預設 TESTNET
    reconciliation: bool = True,
    use_bracket: bool = False,
    max_notional: int = DEFAULT_MAX_NOTIONAL_USDT,
    max_order_submit_rate: str = DEFAULT_MAX_ORDER_SUBMIT_RATE,
) -> TradingNodeConfig:
    """組裝 **live 交易節點** ``TradingNodeConfig``(Binance testnet;下 paper 單)。

    與 #27 data-only 不同:本卡同時掛 **data + exec** client(testnet /
    USDT_FUTURES / HMAC),並掛 ema_cross 策略下小額 paper 單。

    - environment = LIVE(走 live engine + adapter)。
    - data client + exec client 皆 BINANCE testnet。
    - LiveExecEngineConfig 開 reconciliation(重啟對帳)。
    - LiveRiskEngineConfig(卡 #29):名目上限 + 下單頻率上限(Nautilus 原生 RiskEngine;
      超限單 DENIED 不送 venue)。
    - message_bus = #5 streaming(Redis Streams DB0):訂單/成交/部位/PnL 事件
      落地 Redis → consumer → WS → Live 頁面板顯示真 live 值。
    - ⛔ ``assert_testnet_only`` 硬性阻擋非 testnet(真錢 mainnet)。
    """
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

    if environment is None:
        environment = BinanceEnvironment.TESTNET
    # ⛔ 最高優先安全:非 testnet 一律拒絕(硬性阻擋真錢)。
    assert_testnet_only(environment)

    data_cfg = binance_testnet_data_client_config(
        api_key=api_key, api_secret=api_secret
    )
    exec_cfg = binance_testnet_exec_client_config(
        api_key=api_key, api_secret=api_secret
    )
    # 雙重保險:再次確認組出的 client 確為 testnet。
    assert_testnet_only(data_cfg.environment)
    assert_testnet_only(exec_cfg.environment)

    return TradingNodeConfig(
        trader_id=trader_id,
        environment=Environment.LIVE,
        logging=LoggingConfig(log_level="INFO"),
        # 卡 B:include_trade_ticks=True → bus 放行 TradeTick(視覺次秒串流;
        # ⛔ 策略仍只訂 1m bar,tick 不進策略決策,保住回測/live parity)。
        message_bus=streaming_message_bus_config(
            host=redis_host, port=redis_port, include_trade_ticks=True
        ),
        data_engine=LiveDataEngineConfig(),
        exec_engine=LiveExecEngineConfig(reconciliation=reconciliation),
        # 卡 #29:Nautilus 原生風控(名目上限 + 下單頻率),超限單被 RiskEngine deny。
        risk_engine=build_risk_engine_config(
            max_notional=max_notional,
            max_order_submit_rate=max_order_submit_rate,
        ),
        data_clients={str(BINANCE): data_cfg},
        exec_clients={str(BINANCE): exec_cfg},
        # 卡 B:額外掛 TradeTick 視覺訂閱 actor(data-only;⛔ 不進策略)。
        actors=[_trade_tick_actor_config()],
        strategies=[
            ema_cross_strategy_config(
                bar_spec=bar_spec,
                trade_size=trade_size,
                fast_period=fast_period,
                slow_period=slow_period,
                use_bracket=use_bracket,
            ),
        ],
    )
