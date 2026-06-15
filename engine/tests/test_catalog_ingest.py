"""卡 #3 — deep module:transform → 寫入 ParquetDataCatalog → 依時間區間查回。

用小 fixture(不打網路)做確定性測試:
- 寫入後可查回(roundtrip)
- 依 instrument + 起迄時間取回正確切片
- 查回結果依 ts_init 單調遞增
"""

from __future__ import annotations

from nautilus_trader.persistence.catalog import ParquetDataCatalog

from jimq_engine.catalog.ingest import (
    BAR_TYPE_1M,
    ingest_bars,
    ingest_funding,
    query_bars,
    query_funding,
)
from jimq_engine.catalog.instruments import btcusdt_perp_binance

# 5 根連續 1m K 線(openTime 每根 +60s)
_BASE_MS = 1700000000000
RAW_KLINES = [
    [
        _BASE_MS + i * 60_000,
        f"{37000 + i}.0",
        f"{37050 + i}.0",
        f"{36990 + i}.0",
        f"{37025 + i}.0",
        "10.000",
        _BASE_MS + i * 60_000 + 59_999,
        "0",
        1,
        "0",
        "0",
        "0",
    ]
    for i in range(5)
]

RAW_FUNDING = [
    {"symbol": "BTCUSDT", "fundingTime": _BASE_MS + i * 28_800_000, "fundingRate": "0.0001", "markPrice": "37000"}
    for i in range(3)
]


def _new_catalog(tmp_path) -> ParquetDataCatalog:
    return ParquetDataCatalog(path=str(tmp_path / "catalog"))


def test_bars_roundtrip_query_all(tmp_path):
    catalog = _new_catalog(tmp_path)
    instrument = btcusdt_perp_binance()
    catalog.write_data([instrument])

    n = ingest_bars(catalog, RAW_KLINES, instrument)
    assert n == 5

    got = query_bars(catalog)
    assert len(got) == 5
    ts = [b.ts_init for b in got]
    assert ts == sorted(ts)


def test_bars_query_time_slice(tmp_path):
    catalog = _new_catalog(tmp_path)
    instrument = btcusdt_perp_binance()
    ingest_bars(catalog, RAW_KLINES, instrument)

    # 取中間 3 根:索引 1..3
    start_ns = (_BASE_MS + 1 * 60_000) * 1_000_000
    end_ns = (_BASE_MS + 3 * 60_000) * 1_000_000
    got = query_bars(catalog, start=start_ns, end=end_ns)

    assert len(got) == 3
    assert got[0].ts_init == start_ns
    assert got[-1].ts_init == end_ns
    assert str(got[0].open) == "37001.0"


def test_funding_roundtrip(tmp_path):
    catalog = _new_catalog(tmp_path)
    instrument = btcusdt_perp_binance()

    n = ingest_funding(catalog, RAW_FUNDING, instrument.id)
    assert n == 3

    got = query_funding(catalog)
    assert len(got) == 3
    ts = [u.ts_init for u in got]
    assert ts == sorted(ts)


def test_bar_type_default_is_1m_external():
    assert str(BAR_TYPE_1M) == "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"


def test_ingest_bars_idempotent_overwrite(tmp_path):
    """重複灌同一段資料不應產生重複列(idempotent / 可安全覆寫)。"""
    catalog = _new_catalog(tmp_path)
    instrument = btcusdt_perp_binance()

    ingest_bars(catalog, RAW_KLINES, instrument)
    ingest_bars(catalog, RAW_KLINES, instrument)

    got = query_bars(catalog)
    assert len(got) == 5
