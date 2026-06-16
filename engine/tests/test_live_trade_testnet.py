"""卡 #28 (P2-S2) — Binance testnet **真 paper 單 round-trip** 整合測試(gated)。

需要:外網可達 Binance testnet + ``.env.afk`` 金鑰 + 本機 Redis(DB0)。
預設 **skip**;設 ``JIMQ_RUN_TESTNET=1`` 才跑(避免 CI/離線環境失敗)。

驗收(行為):跑 live 交易節點(data+exec testnet),ema_cross 在即時 bar 觸發交叉
**由策略本身下一筆新 paper 單**後,**真**訂單/成交事件落地本機 Redis Streams ——
出現由 **EMACross 策略**(strategy_id 非 ``EXTERNAL`` 且 ``reconciliation`` 為假)
發出的 ``events.order.`` / ``events.fills.`` 真事件(OrderFilled 帶 last_qty/last_px),
證明 paper 單真的送達 testnet 並成交(round-trip)。

⚠️ 不可只掃 ``events.order.`` / ``events.fills.`` 前綴就判綠:Nautilus 在
``reconciliation=True`` 下會把 testnet 上**既有殘留部位**以 ``strategy_id=EXTERNAL``、
``reconciliation=True`` 重新發成 ``OrderFilled``(last_qty>0、last_px>0)。若只掃前綴,
帳戶一有殘留部位即 false-green,根本沒驗到「策略本身下了一筆新單」。本測試因此**過濾掉**
reconciliation / EXTERNAL 事件,只認**策略原生**(strategy_id 以 ``EMACross`` 起頭、
``reconciliation`` 為假)的 order/fill,真正驗證策略下單行為。

⛔ testnet-only:節點硬性 ``BinanceEnvironment.TESTNET``;本測試亦驗 exec client
為 testnet,確保非真錢路徑。
"""

from __future__ import annotations

import os
import threading
import time

import pytest

redis = pytest.importorskip("redis")

pytestmark = pytest.mark.skipif(
    os.environ.get("JIMQ_RUN_TESTNET") != "1",
    reason="gated:設 JIMQ_RUN_TESTNET=1 並具外網+金鑰才跑真 testnet paper 單測試",
)


def _decode(v):
    return v.decode() if isinstance(v, (bytes, bytearray)) else v


def _scan_topics(client, key, prefix):
    """掃 stream key,回傳 topic 以 prefix 起頭的 (topic, payload_dict)。"""
    import msgspec

    out = []
    if not client.exists(key):
        return out
    for _id, fields in client.xrange(key):
        fields = {_decode(k): v for k, v in fields.items()}
        topic = _decode(fields.get("topic"))
        if not topic or not topic.startswith(prefix):
            continue
        try:
            payload = msgspec.msgpack.decode(fields.get("payload"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(payload, dict):
            out.append((topic, payload))
    return out


def _is_strategy_originated(payload: dict, strategy_prefix: str = "EMACross") -> bool:
    """事件是否由**策略本身**發出(而非 reconciliation 重發既有 EXTERNAL 部位)。

    Nautilus 在 ``reconciliation=True`` 下,會把 testnet 帳戶上**既有殘留部位**
    以 ``strategy_id=EXTERNAL``、``reconciliation=True`` 重新發成 OrderFilled
    (last_qty>0、last_px>0)。這類事件**不代表**策略下了新單,必須排除,否則
    帳戶有殘留部位時測試會 false-green。

    判定為策略原生 = ``reconciliation`` 為假 **且** ``strategy_id`` 以策略類名
    (``EMACross``)起頭、且非 ``EXTERNAL``。
    """
    recon = payload.get("reconciliation")
    # bus msgpack 序列化後 reconciliation 為真正的 bool;保險也擋字串 "True"。
    if recon is True or (isinstance(recon, str) and recon.lower() == "true"):
        return False
    sid = str(payload.get("strategy_id", ""))
    if sid == "EXTERNAL" or sid.upper() == "EXTERNAL":
        return False
    return sid.startswith(strategy_prefix)


def test_testnet_paper_order_round_trip_lands_in_redis():
    from dotenv import load_dotenv

    from nautilus_trader.adapters.binance import (
        BinanceLiveDataClientFactory,
        BinanceLiveExecClientFactory,
    )
    from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment
    from nautilus_trader.live.node import TradingNode

    from jimq_engine.nodes.live import (
        BINANCE,
        build_live_trade_node_config,
        credentials_from_env,
    )
    from scripts.run_live_trade import _stream_key_for_node
    from jimq_core.constants import REDIS_BUS_DB

    load_dotenv(".env.afk")
    api_key, api_secret = credentials_from_env()

    client = redis.Redis(host="localhost", port=6379, db=REDIS_BUS_DB)
    client.ping()

    # 短 EMA 週期使近期 1m bar 上更易觸發交叉 → 下 paper 單。
    config = build_live_trade_node_config(
        api_key=api_key,
        api_secret=api_secret,
        fast_period=2,
        slow_period=4,
    )
    # ⛔ 驗 exec client 確為 testnet(非真錢)。
    ec = config.exec_clients[str(BINANCE)]
    assert ec.environment == BinanceEnvironment.TESTNET

    node = TradingNode(config=config)
    node.add_data_client_factory(BINANCE.value, BinanceLiveDataClientFactory)
    node.add_exec_client_factory(BINANCE.value, BinanceLiveExecClientFactory)
    node.build()
    key = _stream_key_for_node(node)
    client.delete(key)

    t = threading.Thread(target=node.run, daemon=True)
    t.start()
    try:
        # 等多根真 1m bar 聚合 + 觸發交叉 + 下單成交回報;最久 ~6 分鐘。
        deadline = time.time() + 360
        strat_orders = []
        strat_fills = []
        while time.time() < deadline:
            # ⚠️ 只認**策略原生**事件(排除 reconciliation / EXTERNAL 重發),
            # 否則帳戶有殘留部位時會 false-green。
            strat_orders = [
                (t_, p) for (t_, p) in _scan_topics(client, key, "events.order.")
                if _is_strategy_originated(p)
            ]
            strat_fills = [
                (t_, p) for (t_, p) in _scan_topics(client, key, "events.fills.")
                if _is_strategy_originated(p)
            ]
            if strat_fills:
                break
            time.sleep(5)
        assert strat_orders, (
            f"未在 Redis stream {key} 看到**策略原生**(strategy_id=EMACross、"
            f"reconciliation=False)的 events.order. 訂單事件;策略未下新單"
            f"(reconciliation 重發既有 EXTERNAL 部位不算)"
        )
        assert strat_fills, (
            f"未在 Redis stream {key} 看到**策略原生** events.fills. 成交事件;"
            f"策略下的新 paper 單未成交(reconciliation 重發既有部位不算)"
        )
        topic, fill = strat_fills[0]
        assert str(fill.get("type", "")).endswith("Filled") or "Filled" in topic, fill
        assert float(fill.get("last_qty", 0)) > 0, fill
        assert float(fill.get("last_px", 0)) > 0, fill
        # ⛔ 雙重保險:選中的 fill 確為策略原生、非 reconciliation。
        assert fill.get("reconciliation") in (False, None, "False", "false"), fill
        assert str(fill.get("strategy_id", "")) != "EXTERNAL", fill
    finally:
        node.stop()
        time.sleep(1)
        node.dispose()
        client.delete(key)
        client.close()
