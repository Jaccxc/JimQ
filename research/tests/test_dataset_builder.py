"""卡 #14 — deep module:dataset builder(catalog → jimq_core.features → 訓練資料集)。

行為驗證(透過 public interface ``build_dataset`` 與 pluggable 特徵/標籤介面),
不驗證實作細節:

- 從既有 ParquetDataCatalog 依 bar_type + [start, end] 讀 bars,輸出 Polars
  DataFrame,含時間索引欄(``ts``)、OHLCV、注入的特徵欄、注入的標籤欄。
- 特徵以使用者注入的 callable 計算(平台不硬編 alpha):``feature_fns`` 與
  ``label_fn`` 完全由呼叫端決定。
- 提供的 ``ema_feature`` factory 復用 ``jimq_core.features``,其輸出與 engine
  推論用的逐筆 ``ExponentialMovingAverage`` 對同一序列等價(train/serve parity)。
- 確定性:同輸入同輸出(連跑兩次 frame_equal)。
- 時間區間切片正確、列依 ts 單調遞增。
"""

from __future__ import annotations

import polars as pl

from jimq_core.features import ExponentialMovingAverage
from jimq_engine.catalog.ingest import (
    BAR_TYPE_1M,
    ingest_bars,
    ingest_funding,
)
from jimq_engine.catalog.instruments import btcusdt_perp_binance
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from jimq_research.data import build_dataset, ema_feature, funding_feature

_BASE_MS = 1700000000000

# 30 根連續 1m K 線(確定但有起伏的 close,讓 EMA/標籤非平凡)。
RAW_KLINES = [
    [
        _BASE_MS + i * 60_000,
        f"{37000 + (i % 7) * 3}.0",
        f"{37050 + (i % 7) * 3}.0",
        f"{36990 + (i % 7) * 3}.0",
        f"{37025 + (i % 5) * 4}.0",
        f"{10 + i}.000",
        _BASE_MS + i * 60_000 + 59_999,
        "0",
        1,
        "0",
        "0",
        "0",
    ]
    for i in range(30)
]

RAW_FUNDING = [
    {
        "symbol": "BTCUSDT",
        "fundingTime": _BASE_MS + i * 28_800_000,
        "fundingRate": "0.0001",
        "markPrice": "37000",
    }
    for i in range(3)
]


def _make_catalog(tmp_path) -> ParquetDataCatalog:
    catalog = ParquetDataCatalog(path=str(tmp_path / "catalog"))
    instrument = btcusdt_perp_binance()
    catalog.write_data([instrument])
    ingest_bars(catalog, RAW_KLINES, instrument)
    ingest_funding(catalog, RAW_FUNDING, instrument.id)
    return catalog


def test_build_returns_polars_with_time_index_and_ohlcv(tmp_path):
    catalog = _make_catalog(tmp_path)
    df = build_dataset(catalog, bar_type=BAR_TYPE_1M)

    assert isinstance(df, pl.DataFrame)
    # 時間索引 + OHLCV 至少存在。
    for col in ("ts", "open", "high", "low", "close", "volume"):
        assert col in df.columns
    assert df.height == 30
    # 依 ts 單調遞增。
    ts = df["ts"].to_list()
    assert ts == sorted(ts)
    assert ts[0] == _BASE_MS * 1_000_000  # 奈秒


def test_pluggable_feature_and_label_columns(tmp_path):
    catalog = _make_catalog(tmp_path)

    def my_label(frame: pl.DataFrame) -> pl.Series:
        # 下一根 close 相對本根的方向(使用者注入,平台不硬編)。
        nxt = frame["close"].shift(-1)
        return (nxt > frame["close"]).cast(pl.Int8).alias("label_up")

    df = build_dataset(
        catalog,
        bar_type=BAR_TYPE_1M,
        feature_fns=[ema_feature(period=5, source="close", name="ema5")],
        label_fn=my_label,
    )

    assert "ema5" in df.columns
    assert "label_up" in df.columns


def test_ema_feature_matches_jimq_core_incremental(tmp_path):
    """train/serve parity:builder 的 ema 特徵欄 == engine 逐筆 EMA。"""
    catalog = _make_catalog(tmp_path)

    df = build_dataset(
        catalog,
        bar_type=BAR_TYPE_1M,
        feature_fns=[ema_feature(period=5, source="close", name="ema5")],
    )

    closes = df["close"].to_list()
    ema = ExponentialMovingAverage(period=5)
    expected: list[float | None] = []
    for c in closes:
        ema.update_raw(c)
        expected.append(ema.value if ema.initialized else None)

    got = df["ema5"].to_list()
    assert len(got) == len(expected)
    for g, e in zip(got, expected):
        if e is None:
            assert g is None
        else:
            assert g is not None
            assert abs(g - e) < 1e-9


def test_deterministic_same_input_same_output(tmp_path):
    catalog = _make_catalog(tmp_path)
    df1 = build_dataset(
        catalog,
        bar_type=BAR_TYPE_1M,
        feature_fns=[ema_feature(period=5, source="close", name="ema5")],
    )
    df2 = build_dataset(
        catalog,
        bar_type=BAR_TYPE_1M,
        feature_fns=[ema_feature(period=5, source="close", name="ema5")],
    )
    assert df1.equals(df2)


def test_time_slice_start_end(tmp_path):
    catalog = _make_catalog(tmp_path)
    start_ns = (_BASE_MS + 5 * 60_000) * 1_000_000
    end_ns = (_BASE_MS + 9 * 60_000) * 1_000_000
    df = build_dataset(catalog, bar_type=BAR_TYPE_1M, start=start_ns, end=end_ns)

    assert df.height == 5
    assert df["ts"].to_list()[0] == start_ns
    assert df["ts"].to_list()[-1] == end_ns


def test_funding_feature_asof_joins_latest_rate(tmp_path):
    """funding_feature 把 catalog 的 funding rate 以 as-of(<=ts)併到每根 bar。

    fixture 的 funding 在 _BASE_MS 起 8h 一筆,30 根 1m bar 全落在第一個區間內,
    故每根 bar 的 funding_rate 應等於第一筆 rate(0.0001),不應有 null。
    """
    catalog = _make_catalog(tmp_path)
    df = build_dataset(
        catalog,
        bar_type=BAR_TYPE_1M,
        feature_fns=[funding_feature(catalog, name="funding_rate")],
    )
    assert "funding_rate" in df.columns
    rates = df["funding_rate"].to_list()
    assert all(r is not None for r in rates)
    assert all(abs(r - 0.0001) < 1e-12 for r in rates)


def test_no_feature_fns_yields_only_ohlcv(tmp_path):
    catalog = _make_catalog(tmp_path)
    df = build_dataset(catalog, bar_type=BAR_TYPE_1M)
    assert set(df.columns) == {"ts", "open", "high", "low", "close", "volume"}
