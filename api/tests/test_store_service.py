"""卡 #8 — store 服務:從 ParquetDataCatalog 查歷史 bars(行為層測試)。

驗證 public interface(query_bars):
- 依 symbol + timeframe 查回 BarDTO 列表,映射正確。
- 依 [start, end] 起迄(epoch 奈秒)取回正確切片。
- 空區間回空列表。
- 未知 symbol / 未知 timeframe 回空列表(一致邊界)。
"""

from __future__ import annotations

from jimq_core.schemas import BarDTO

from app.services import store

# 與 conftest.fixture_catalog 一致。
SYMBOL = "BTCUSDT-PERP.BINANCE"
_BASE_MS = 1700000000000
BAR_TS_NS = [(_BASE_MS + i * 60_000) * 1_000_000 for i in range(5)]


def test_query_returns_all_bars_mapped_to_dto(fixture_catalog):
    bars = store.query_bars(SYMBOL, "1m", None, None, catalog_path=fixture_catalog)
    assert len(bars) == 5
    assert all(isinstance(b, BarDTO) for b in bars)
    first = bars[0]
    assert first.ts == BAR_TS_NS[0]
    assert first.time == BAR_TS_NS[0] // 1_000_000_000
    assert first.open == "37000.0"
    assert first.close == "37025.0"
    assert first.volume == "10.000"


def test_query_time_slice_inclusive(fixture_catalog):
    start, end = BAR_TS_NS[1], BAR_TS_NS[3]
    bars = store.query_bars(SYMBOL, "1m", start, end, catalog_path=fixture_catalog)
    assert [b.ts for b in bars] == BAR_TS_NS[1:4]


def test_empty_range_returns_empty_list(fixture_catalog):
    # 區間落在所有資料之後 → 空。
    future = BAR_TS_NS[-1] + 10 * 60_000_000_000
    bars = store.query_bars(SYMBOL, "1m", future, future + 1, catalog_path=fixture_catalog)
    assert bars == []


def test_unknown_symbol_returns_empty_list(fixture_catalog):
    bars = store.query_bars("ETHUSDT-PERP.BINANCE", "1m", None, None, catalog_path=fixture_catalog)
    assert bars == []


def test_unknown_timeframe_returns_empty_list(fixture_catalog):
    bars = store.query_bars(SYMBOL, "13m", None, None, catalog_path=fixture_catalog)
    assert bars == []
