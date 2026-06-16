"""卡 #27 (P2-S1) — Binance testnet **live 資料節點** entrypoint(可起停)。

連 Binance USDT-M Futures **testnet**,訂閱 BTCUSDT-PERP 即時 bar,把事件序列化
落地**本機 Redis Streams**(DB0),並把實際 stream key 發布到 **live scope**
latest-key ``jimq:live:latest_stream_key``(卡 A;供 API live scope supervisor
解析、前端 Live 頁即時訂閱,與 backtest 隔離)。
mode badge 依此判定 LIVE-TESTNET(節點在跑 = live 來源)。

用法:
    uv run python scripts/run_live_data.py                 # 連真 testnet(需外網)
    uv run python scripts/run_live_data.py --bar-spec 1-MINUTE-LAST-EXTERNAL

金鑰:從 ``.env.afk`` 的 ``BINANCE_TESTNET_KEY`` / ``BINANCE_TESTNET_SECRET`` 讀
(``credentials_from_env``;**絕不硬編、絕不 commit**)。Ctrl-C 優雅停止並清掉
published key。⛔ data-only,不下任何單。
"""

from __future__ import annotations

import argparse
import os
import signal

import redis as redis_sync
from dotenv import load_dotenv

from jimq_core.constants import LIVE_LATEST_STREAM_KEY, REDIS_BUS_DB

from nautilus_trader.adapters.binance import BinanceLiveDataClientFactory
from nautilus_trader.live.node import TradingNode

from jimq_engine.nodes.live import (
    BINANCE,
    DEFAULT_BAR_SPEC,
    build_live_data_node_config,
    credentials_from_env,
)

# 卡 A:live 資料源把實際 stream key 寫到 **live scope** latest-key,api 的 live
# scope supervisor 才 watch 它(與 backtest 隔離,Live 圖不混入 backtest)。
LATEST_STREAM_KEY = LIVE_LATEST_STREAM_KEY


def _redis_host_port() -> tuple[str, int]:
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    return host, port


def _stream_key_for_node(node: TradingNode, streams_prefix: str = "stream") -> str:
    """live 節點事件落地的 Redis stream key(對齊 #5 結構)。

    Nautilus 在 use_trader_prefix 開啟時把 ``trader`` 前綴與 trader_id 以 ``-`` 連,
    其餘段以 ``:`` 連:``trader-{trader_id}:{instance_id}:{streams_prefix}``。
    """
    return f"trader-{node.trader_id}:{node.instance_id}:{streams_prefix}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Binance testnet live 資料節點")
    parser.add_argument("--bar-spec", default=DEFAULT_BAR_SPEC)
    parser.add_argument(
        "--no-publish-key",
        action="store_true",
        help=f"不把 stream key 寫到 {LATEST_STREAM_KEY}",
    )
    args = parser.parse_args()

    # 從 .env.afk 載入金鑰(若存在);否則期望已在環境。
    load_dotenv(".env.afk")
    api_key, api_secret = credentials_from_env()

    redis_host, redis_port = _redis_host_port()
    config = build_live_data_node_config(
        api_key=api_key,
        api_secret=api_secret,
        bar_spec=args.bar_spec,
        redis_host=redis_host,
        redis_port=redis_port,
    )

    node = TradingNode(config=config)
    node.add_data_client_factory(BINANCE.value, BinanceLiveDataClientFactory)
    node.build()

    key = _stream_key_for_node(node)
    client = redis_sync.Redis(host=redis_host, port=redis_port, db=REDIS_BUS_DB)
    if not args.no_publish_key:
        client.set(LATEST_STREAM_KEY, key)
        print(f"published key -> {LATEST_STREAM_KEY} = {key}")
    print(f"live 資料節點啟動(Binance testnet);stream key = {key}")
    print(f"REDIS_BUS_DB={REDIS_BUS_DB} host={redis_host}:{redis_port}")

    def _on_signal(_signum, _frame):  # noqa: ANN001
        node.stop()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        node.run()
    finally:
        if not args.no_publish_key:
            try:
                client.delete(LATEST_STREAM_KEY)
            except Exception:  # noqa: BLE001
                pass
        client.close()
        node.dispose()


if __name__ == "__main__":
    main()
