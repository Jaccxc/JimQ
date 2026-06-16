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
from nautilus_trader.adapters.binance.config import BinanceDataClientConfig
from nautilus_trader.common import Environment
from nautilus_trader.common.actor import Actor, ActorConfig
from nautilus_trader.config import (
    ImportableActorConfig,
    InstrumentProviderConfig,
    LiveDataEngineConfig,
    LoggingConfig,
    TradingNodeConfig,
)
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import Venue

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
        message_bus=streaming_message_bus_config(
            host=redis_host, port=redis_port
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
