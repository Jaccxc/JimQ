"""卡 #28 (P2-S2) — Binance testnet **live 交易節點** entrypoint(下 paper 單)。

連 Binance USDT-M Futures **testnet**(假錢),掛 data + exec client,跑 ema_cross
策略在即時 1m bar 上下小額 paper 單(0.001 BTC bracket);訂單/成交/部位/PnL 事件
序列化落地**本機 Redis Streams**(DB0)→ consumer → WS → Live 頁面板顯示真 live 值。
並把實際 stream key 發布到 **live scope** latest-key ``jimq:live:latest_stream_key``
(卡 A;供 API live scope supervisor 解析、前端 Live 頁即時訂閱,與 backtest 隔離)。
mode badge 依此判定 LIVE-TESTNET。

用法:
    uv run python scripts/run_live_trade.py                 # 連真 testnet(需外網)
    uv run python scripts/run_live_trade.py --fast 3 --slow 8 --trade-size 0.001
    uv run python scripts/run_live_trade.py --duration 180  # 跑 180s 後自動停(驗 round-trip)

金鑰:從 ``.env.afk`` 的 ``BINANCE_TESTNET_KEY`` / ``BINANCE_TESTNET_SECRET`` 讀
(``credentials_from_env``;**絕不硬編、絕不 commit**)。Ctrl-C 優雅停止並清掉
published key。

⛔ 最高優先安全:程式硬性 ``BinanceEnvironment.TESTNET``(假錢);任何非 testnet
設定由 ``assert_testnet_only`` 拋例外阻擋。嚴禁 mainnet / 真實資金。
"""

from __future__ import annotations

import argparse
import os
import signal
import threading
import time

import redis as redis_sync
from dotenv import load_dotenv

from jimq_core.constants import LIVE_LATEST_STREAM_KEY, REDIS_BUS_DB

from nautilus_trader.adapters.binance import (
    BinanceLiveDataClientFactory,
    BinanceLiveExecClientFactory,
)
from nautilus_trader.live.node import TradingNode

from jimq_engine.nodes.live import (
    BINANCE,
    DEFAULT_BAR_SPEC,
    DEFAULT_FAST_PERIOD,
    DEFAULT_MAX_NOTIONAL_USDT,
    DEFAULT_MAX_ORDER_SUBMIT_RATE,
    DEFAULT_PAPER_TRADE_SIZE,
    DEFAULT_SLOW_PERIOD,
    build_live_trade_node_config,
    credentials_from_env,
)

# 卡 A:live/paper 交易資料源把實際 stream key 寫到 **live scope** latest-key,
# api 的 live scope supervisor 才 watch 它(與 backtest 隔離)。
LATEST_STREAM_KEY = LIVE_LATEST_STREAM_KEY


def _redis_host_port() -> tuple[str, int]:
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    return host, port


def _stream_key_for_node(node: TradingNode, streams_prefix: str = "stream") -> str:
    """live 節點事件落地的 Redis stream key(對齊 #5 結構)。"""
    return f"trader-{node.trader_id}:{node.instance_id}:{streams_prefix}"


def build_arg_parser() -> argparse.ArgumentParser:
    """組裝 CLI 參數解析器(可單獨測試風控旗標,不啟動節點)。"""
    parser = argparse.ArgumentParser(description="Binance testnet live 交易節點(paper 單)")
    parser.add_argument("--bar-spec", default=DEFAULT_BAR_SPEC)
    parser.add_argument("--trade-size", default=DEFAULT_PAPER_TRADE_SIZE)
    parser.add_argument("--fast", type=int, default=DEFAULT_FAST_PERIOD)
    parser.add_argument("--slow", type=int, default=DEFAULT_SLOW_PERIOD)
    # 卡 #29 風控旗標(Nautilus 原生 RiskEngine):
    parser.add_argument(
        "--max-notional",
        type=int,
        default=DEFAULT_MAX_NOTIONAL_USDT,
        help="每單名目上限(USDT);超限單由 RiskEngine DENIED 不送 venue",
    )
    parser.add_argument(
        "--max-order-submit-rate",
        default=DEFAULT_MAX_ORDER_SUBMIT_RATE,
        help="下單頻率上限 throttler(如 10/00:00:01)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="跑 N 秒後自動停止(0=不限,Ctrl-C 停)",
    )
    parser.add_argument(
        "--no-publish-key",
        action="store_true",
        help=f"不把 stream key 寫到 {LATEST_STREAM_KEY}",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    # 從 .env.afk 載入金鑰(若存在);否則期望已在環境。
    load_dotenv(".env.afk")
    api_key, api_secret = credentials_from_env()

    redis_host, redis_port = _redis_host_port()
    # ⛔ build_live_trade_node_config 內含 assert_testnet_only;非 testnet 直接拋。
    config = build_live_trade_node_config(
        api_key=api_key,
        api_secret=api_secret,
        bar_spec=args.bar_spec,
        trade_size=args.trade_size,
        fast_period=args.fast,
        slow_period=args.slow,
        redis_host=redis_host,
        redis_port=redis_port,
        max_notional=args.max_notional,
        max_order_submit_rate=args.max_order_submit_rate,
    )

    node = TradingNode(config=config)
    node.add_data_client_factory(BINANCE.value, BinanceLiveDataClientFactory)
    node.add_exec_client_factory(BINANCE.value, BinanceLiveExecClientFactory)
    node.build()

    key = _stream_key_for_node(node)
    client = redis_sync.Redis(host=redis_host, port=redis_port, db=REDIS_BUS_DB)
    if not args.no_publish_key:
        client.set(LATEST_STREAM_KEY, key)
        print(f"published key -> {LATEST_STREAM_KEY} = {key}")
    print("⛔ TESTNET-ONLY:Binance USDT-M Futures testnet(假錢)live 交易節點啟動")
    print(f"stream key = {key}  REDIS_BUS_DB={REDIS_BUS_DB} host={redis_host}:{redis_port}")
    print(f"strategy=ema_cross fast={args.fast} slow={args.slow} trade_size={args.trade_size}")
    print(
        f"risk: max_notional={args.max_notional} USDT "
        f"max_order_submit_rate={args.max_order_submit_rate}"
    )

    def _on_signal(_signum, _frame):  # noqa: ANN001
        node.stop()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    # --duration:背景計時器到點優雅停止(用於 round-trip 驗證跑固定時長)。
    if args.duration > 0:
        def _auto_stop() -> None:
            time.sleep(args.duration)
            print(f"達 --duration {args.duration}s,停止節點")
            node.stop()

        threading.Thread(target=_auto_stop, daemon=True).start()

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
