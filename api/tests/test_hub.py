"""卡 #7 — in-process pub/sub hub deep module 測試。

行為級驗收:
- 多訂閱者:同一 channel 的每個訂閱者都收到 publish 的信封。
- 多工:訂閱者只收到自己訂的 channel,不收別的 channel。
- 快照:hub 保留目前已知狀態(最近 bars / 最新 pnl / 最新 position),
  新連線可取得快照。
- 有界佇列溢出:訂閱者 queue 滿時溢出策略生效(drop-oldest;pnl/positions
  last-value-wins 合併)。
- last_seq 補洞:hub 保留近期信封 ring,可依 last_seq 回補缺口(不重複不遺漏)。
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.hub import Hub


def _env(channel: str, seq: int, **data) -> dict:
    return {"channel": channel, "seq": seq, "data": {**data}}


@pytest.mark.asyncio
async def test_multi_subscriber_same_channel_all_receive():
    """同一 channel 的多訂閱者都收到該 channel 的信封。"""
    hub = Hub()
    sub_a = hub.subscribe({"bars"})
    sub_b = hub.subscribe({"bars"})
    await hub.publish(_env("bars", 1, close="100"))

    a = await asyncio.wait_for(sub_a.queue.get(), 1)
    b = await asyncio.wait_for(sub_b.queue.get(), 1)
    assert a["seq"] == 1 and b["seq"] == 1


@pytest.mark.asyncio
async def test_multiplex_only_subscribed_channels():
    """訂閱者只收到自己訂的 channel。"""
    hub = Hub()
    bars_sub = hub.subscribe({"bars"})
    pnl_sub = hub.subscribe({"pnl"})
    await hub.publish(_env("bars", 1))
    await hub.publish(_env("pnl", 2))

    got_bars = await asyncio.wait_for(bars_sub.queue.get(), 1)
    got_pnl = await asyncio.wait_for(pnl_sub.queue.get(), 1)
    assert got_bars["channel"] == "bars"
    assert got_pnl["channel"] == "pnl"
    assert bars_sub.queue.empty()
    assert pnl_sub.queue.empty()


@pytest.mark.asyncio
async def test_snapshot_keeps_recent_bars_and_latest_pnl():
    """快照保留最近 bars(序)與最新 pnl(last-value)。"""
    hub = Hub(bars_history=3)
    for i in range(5):
        await hub.publish(_env("bars", i + 1, time=i, close=str(i)))
    await hub.publish(_env("pnl", 99, total="1000"))
    await hub.publish(_env("pnl", 100, total="1234"))

    snap = hub.snapshot({"bars", "pnl"})
    bars = [e for e in snap if e["channel"] == "bars"]
    pnls = [e for e in snap if e["channel"] == "pnl"]
    # 只留最近 3 根 bars(序保留)。
    assert [e["data"]["close"] for e in bars] == ["2", "3", "4"]
    # pnl last-value-wins:只留最新一筆。
    assert len(pnls) == 1 and pnls[0]["data"]["total"] == "1234"


@pytest.mark.asyncio
async def test_subscriber_receives_trades_channel():
    """卡 B:trades channel 的訂閱者收到 publish 的逐筆成交信封(多工不漏)。"""
    hub = Hub()
    sub = hub.subscribe({"trades"})
    await hub.publish(_env("trades", 1, time=100, price="40001.5"))
    got = await asyncio.wait_for(sub.queue.get(), 1)
    assert got["channel"] == "trades"
    assert got["data"]["price"] == "40001.5"


@pytest.mark.asyncio
async def test_snapshot_keeps_recent_trades_ring():
    """卡 B:trades 採小 ring 快照 —— 新連線取得近期幾筆成交(序保留)。

    讓 Live 圖一連上就反映形成中那根的最新跳動,不必空等下一筆 tick。
    """
    hub = Hub(trades_history=3)
    for i in range(5):
        await hub.publish(_env("trades", i + 1, time=i, price=str(i)))
    snap = hub.snapshot({"trades"})
    trades = [e for e in snap if e["channel"] == "trades"]
    # 只留最近 3 筆(序保留)。
    assert [e["data"]["price"] for e in trades] == ["2", "3", "4"]


@pytest.mark.asyncio
async def test_bounded_queue_drop_oldest_on_overflow():
    """有界佇列滿時丟最舊(bars 類:drop-oldest)。"""
    hub = Hub()
    sub = hub.subscribe({"bars"}, maxsize=2)
    for i in range(5):
        await hub.publish(_env("bars", i + 1, close=str(i)))

    drained = []
    while not sub.queue.empty():
        drained.append(sub.queue.get_nowait())
    seqs = [e["seq"] for e in drained]
    # queue 上限 2;丟最舊,保留最後兩筆。
    assert seqs == [4, 5]


@pytest.mark.asyncio
async def test_last_value_wins_coalesce_pnl():
    """pnl 溢出時合併:queue 內同 channel 只保留最新值(last-value-wins)。"""
    hub = Hub()
    sub = hub.subscribe({"pnl"}, maxsize=1, coalesce_channels={"pnl"})
    await hub.publish(_env("pnl", 1, total="100"))
    await hub.publish(_env("pnl", 2, total="200"))
    await hub.publish(_env("pnl", 3, total="300"))

    drained = []
    while not sub.queue.empty():
        drained.append(sub.queue.get_nowait())
    # 合併:只剩最新一筆。
    assert len(drained) == 1
    assert drained[0]["data"]["total"] == "300"
    assert drained[0]["seq"] == 3


@pytest.mark.asyncio
async def test_backfill_since_last_seq_no_dup_no_gap():
    """last_seq 補洞:回補 (last_seq, latest] 缺口,不重複不遺漏。"""
    hub = Hub(history=100)
    for i in range(10):
        await hub.publish(_env("bars", i + 1, close=str(i)))

    # client 最後看到 seq=6,重連回補 7..10。
    missed = hub.backfill_since(last_seq=6, channels={"bars"})
    assert [e["seq"] for e in missed] == [7, 8, 9, 10]


@pytest.mark.asyncio
async def test_backfill_respects_channel_filter():
    """補洞只回補訂閱的 channel。"""
    hub = Hub(history=100)
    await hub.publish(_env("bars", 1))
    await hub.publish(_env("pnl", 2))
    await hub.publish(_env("bars", 3))
    missed = hub.backfill_since(last_seq=0, channels={"bars"})
    assert [e["seq"] for e in missed] == [1, 3]


@pytest.mark.asyncio
async def test_clear_empties_snapshot_but_keeps_subscribers():
    """clear() 清空快照(bars/pnl/positions),但保留現有訂閱者連線。

    熱重載切 stream 後,新 WS client 不應收到上一個 run 的殘留 bars/部位/pnl,
    但已連上的訂閱者連線不該被斷(其 queue 之後仍能收新 run 的信封)。
    """
    hub = Hub()
    sub = hub.subscribe({"bars", "pnl", "positions"})
    await hub.publish(_env("bars", 1, close="100"))
    await hub.publish(_env("pnl", 2, total="500"))
    await hub.publish(_env("positions", 3, position_id="P-1", side="LONG"))
    # 排空訂閱者 queue(模擬已被送出的舊資料)。
    while not sub.queue.empty():
        sub.queue.get_nowait()
    assert hub.snapshot({"bars", "pnl", "positions"})  # 清前有東西

    hub.clear()

    # 快照歸零。
    assert hub.snapshot({"bars", "pnl", "positions"}) == []
    # backfill 也清空。
    assert hub.backfill_since(last_seq=0, channels={"bars", "pnl", "positions"}) == []
    # 訂閱者保留:clear 後 publish 新 run 的信封仍送達。
    await hub.publish(_env("bars", 1, close="200"))
    got = await asyncio.wait_for(sub.queue.get(), 1)
    assert got["data"]["close"] == "200"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    """unsubscribe 後不再收到新信封。"""
    hub = Hub()
    sub = hub.subscribe({"bars"})
    hub.unsubscribe(sub)
    await hub.publish(_env("bars", 1))
    assert sub.queue.empty()
