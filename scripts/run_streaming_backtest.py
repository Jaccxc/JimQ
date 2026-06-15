"""卡 #5 — 啟用 Redis Streams 外部串流的 EMA backtest demo(可觀察驗證)。

從 catalog(或合成黃金交叉)讀 BTCUSDT-PERP 1m bars,以
``jimq_engine.streaming.redis_bus.build_streaming_engine`` 跑 backtest,使
bar/order/fill/position/account 事件序列化(msgpack)落地**本機 Redis Streams**
(REDIS_BUS_DB=0)。跑完印出 stream key、XLEN,及前若干筆事件 type 摘要,
供外部 redis-cli XRANGE/XLEN 觀察驗證(卡 #7 consumer 會反序列化消費)。

用法:
    uv run python scripts/run_streaming_backtest.py            # 讀真實 catalog
    uv run python scripts/run_streaming_backtest.py --synthetic
    uv run python scripts/run_streaming_backtest.py --keep     # 不清掉 stream key
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal

import msgspec

from jimq_engine.catalog.ingest import (
    BAR_TYPE_1M,
    ingest_bars,
    open_catalog,
    query_bars,
)
from jimq_engine.catalog.instruments import (
    BTCUSDT_PERP_BINANCE_ID,
    btcusdt_perp_binance,
)
from jimq_engine.streaming.redis_bus import build_streaming_engine, stream_key_for
from jimq_engine.strategies.ema_cross import EMACrossConfig
from jimq_core.constants import REDIS_BUS_DB

_BASE_MS = 1_700_000_000_000


def _synthetic_klines() -> list[list]:
    down = [40000.0 - i * 20 for i in range(15)]
    up = [down[-1] + i * 120 for i in range(1, 20)]
    prices = down + up
    out = []
    for i, p in enumerate(prices):
        ot = _BASE_MS + i * 60_000
        out.append([ot, f"{p}", f"{p + 5}", f"{p - 5}", f"{p}", "10.000",
                    ot + 59_999, "0", 1, "0", "0", "0"])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="streaming EMA backtest demo")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--keep", action="store_true", help="保留 stream key(預設清掉)")
    parser.add_argument("--fast", type=int, default=3)
    parser.add_argument("--slow", type=int, default=8)
    args = parser.parse_args()

    instrument = btcusdt_perp_binance()
    catalog = open_catalog()
    if args.synthetic:
        catalog.write_data([instrument])
        ingest_bars(catalog, _synthetic_klines(), instrument)

    bars = query_bars(catalog, bar_type=BAR_TYPE_1M)
    if not bars:
        raise SystemExit("catalog 無 bars,改用 --synthetic 或先跑 ingest_binance.py")

    config = EMACrossConfig(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        bar_type=BAR_TYPE_1M,
        fast_period=args.fast,
        slow_period=args.slow,
        trade_size=Decimal("0.100"),
        sl_pct=Decimal("0.01"),
        tp_pct=Decimal("0.02"),
    )

    engine = build_streaming_engine(instrument, bars, config)
    key = stream_key_for(engine)

    import time

    import redis

    client = redis.Redis(host="localhost", port=6379, db=REDIS_BUS_DB)
    for _ in range(50):
        if client.exists(key) and client.xlen(key) > 0:
            break
        time.sleep(0.05)

    xlen = client.xlen(key)
    print(f"stream key : {key}")
    print(f"REDIS_BUS_DB: {REDIS_BUS_DB}")
    print(f"XLEN       : {xlen}")

    types: Counter[str] = Counter()
    for _id, fields in client.xrange(key):
        fields = {k.decode(): v for k, v in fields.items()}
        obj = msgspec.msgpack.decode(fields["payload"])
        types[obj.get("type", "?")] += 1
    print("event type 計數:")
    for t, n in types.most_common():
        print(f"  {t:32s} {n}")

    print("\n外部觀察:")
    print(f"  redis-cli -n {REDIS_BUS_DB} XLEN '{key}'")
    print(f"  redis-cli -n {REDIS_BUS_DB} XRANGE '{key}' - + COUNT 5")

    if not args.keep:
        client.delete(key)
        print(f"\n已清掉 stream key:{key}(--keep 可保留)")
    client.close()
    engine.dispose()


if __name__ == "__main__":
    main()
