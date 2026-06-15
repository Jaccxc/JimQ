"""卡 #14 — 訓練資料集 builder(catalog → jimq_core.features → Polars dataset)。

設計原則:

- **平台只提供框架,不硬編 alpha**。要算什麼特徵、什麼標籤完全由呼叫端透過
  ``feature_fns`` / ``label_fn`` 注入(pluggable callable 介面)。
- **復用 engine 的 catalog 查詢碼**:bars/funding 經 ``jimq_engine.catalog``
  讀回 Nautilus 物件(單一真相來源),再轉成 Polars DataFrame。
- **train/serve parity**:內建的 ``ema_feature`` factory 復用
  ``jimq_core.features``(engine Strategy 推論用的同一份 EMA 碼),消除
  train/serve skew。平台本身不偏好任何特徵。
- **確定性**:純函式管線(讀 → 轉 frame → 套 feature_fns → 套 label_fn),
  同輸入同輸出。

pluggable 介面契約::

    build_dataset(
        catalog, bar_type, start=None, end=None,
        feature_fns=[fn(df) -> pl.DataFrame | pl.Series, ...],
        label_fn=fn(df) -> pl.Series | pl.DataFrame | None,
    ) -> pl.DataFrame

每個 feature_fn 收到目前的 frame(時間索引 + OHLCV + 先前已算特徵),回傳:
- ``pl.Series``(具名):新增/取代該欄;或
- ``pl.DataFrame``:整批取代(進階用法,呼叫端自負對齊責任)。

輸出含時間索引欄 ``ts``(epoch 奈秒,對齊 Nautilus ``ts_init``)、OHLCV 浮點欄、
注入的特徵欄、注入的標籤欄;列依 ``ts`` 單調遞增。
"""

from __future__ import annotations

from typing import Callable, Sequence

import polars as pl
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from jimq_core.features import ExponentialMovingAverage
from jimq_engine.catalog.ingest import query_funding, query_bars
from jimq_engine.catalog.instruments import BTCUSDT_PERP_BINANCE_ID
from nautilus_trader.model.identifiers import InstrumentId

# 一個 feature_fn:吃目前 frame,回傳具名 Series(新欄)或整個 DataFrame。
FeatureFn = Callable[[pl.DataFrame], "pl.Series | pl.DataFrame"]
# label_fn:吃 frame,回傳具名 Series(標籤欄)、DataFrame 或 None。
LabelFn = Callable[[pl.DataFrame], "pl.Series | pl.DataFrame | None"]

_OHLCV_COLS = ("open", "high", "low", "close", "volume")


def _bars_to_frame(bars: Sequence[Bar]) -> pl.DataFrame:
    """把 Nautilus ``Bar`` 物件序列轉成 Polars DataFrame(時間索引 + OHLCV)。

    OHLCV 轉 float64 供下游數值特徵運算;``ts`` 為 epoch 奈秒(``ts_init``)。
    Nautilus catalog 查詢已依 ``ts_init`` 排序,這裡再保險排一次以確保確定性。
    """
    rows = {
        "ts": [int(b.ts_init) for b in bars],
        "open": [float(b.open) for b in bars],
        "high": [float(b.high) for b in bars],
        "low": [float(b.low) for b in bars],
        "close": [float(b.close) for b in bars],
        "volume": [float(b.volume) for b in bars],
    }
    schema = {
        "ts": pl.Int64,
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "volume": pl.Float64,
    }
    return pl.DataFrame(rows, schema=schema).sort("ts")


def _apply_feature(frame: pl.DataFrame, result: "pl.Series | pl.DataFrame") -> pl.DataFrame:
    """把 feature_fn 的回傳併回 frame。Series → 新增/取代具名欄;DataFrame → 取代。"""
    if isinstance(result, pl.DataFrame):
        return result
    if isinstance(result, pl.Series):
        if result.name == "" or result.name is None:
            raise ValueError("feature_fn returned an unnamed Series; use .alias(name)")
        return frame.with_columns(result)
    raise TypeError(
        f"feature_fn must return pl.Series or pl.DataFrame, got {type(result)!r}"
    )


def build_dataset(
    catalog: ParquetDataCatalog,
    bar_type: BarType,
    *,
    start: int | None = None,
    end: int | None = None,
    feature_fns: Sequence[FeatureFn] | None = None,
    label_fn: LabelFn | None = None,
) -> pl.DataFrame:
    """從 catalog 建構訓練就緒的 Polars 資料集。

    Args:
        catalog: 已開啟的 ParquetDataCatalog。
        bar_type: 要讀的 Nautilus ``BarType``。
        start / end: ``ts_init`` 奈秒區間(含端點),None 表不限。
        feature_fns: pluggable 特徵 callable 串列;依序套用,後者可看到前者結果。
        label_fn: pluggable 標籤 callable;在所有特徵之後套用一次。

    Returns:
        Polars DataFrame:時間索引 ``ts`` + OHLCV + 特徵欄 + 標籤欄,依 ``ts`` 升冪。
    """
    bars = query_bars(catalog, bar_type, start=start, end=end)
    frame = _bars_to_frame(bars)

    for fn in feature_fns or ():
        frame = _apply_feature(frame, fn(frame))

    if label_fn is not None:
        label = label_fn(frame)
        if isinstance(label, pl.DataFrame):
            frame = label
        elif isinstance(label, pl.Series):
            if label.name == "" or label.name is None:
                raise ValueError("label_fn returned an unnamed Series; use .alias(name)")
            frame = frame.with_columns(label)
        elif label is not None:
            raise TypeError(
                f"label_fn must return pl.Series, pl.DataFrame or None, got {type(label)!r}"
            )

    return frame


def ema_feature(
    period: int,
    source: str = "close",
    name: str | None = None,
) -> FeatureFn:
    """內建特徵 factory:對 ``source`` 欄算 EMA,復用 ``jimq_core.features``。

    這是消除 train/serve skew 的關鍵:此處逐筆 ``update_raw`` 與 engine Strategy
    推論用的是**同一份** :class:`jimq_core.features.ExponentialMovingAverage`,
    對同一序列產生位元等價結果。

    未 initialized(前 ``period - 1`` 筆)填 ``None``,讓下游自行決定如何處理
    暖機期(不硬編丟棄策略)。

    回傳一個 ``feature_fn``,可直接放進 ``build_dataset(feature_fns=[...])``。
    """
    col_name = name or f"ema_{source}_{period}"

    def _fn(frame: pl.DataFrame) -> pl.Series:
        ema = ExponentialMovingAverage(period=period)
        out: list[float | None] = []
        for x in frame[source].to_list():
            ema.update_raw(x)
            out.append(ema.value if ema.initialized else None)
        return pl.Series(name=col_name, values=out, dtype=pl.Float64)

    return _fn


def funding_feature(
    catalog: ParquetDataCatalog,
    instrument_id: InstrumentId = BTCUSDT_PERP_BINANCE_ID,
    name: str = "funding_rate",
) -> FeatureFn:
    """內建特徵 factory:把 catalog 的 funding rate 以 as-of join 併到每根 bar。

    funding 與 bar 是不同 cadence(永續 funding 通常 8h 一次,bar 1m),因此用
    backward as-of join:每根 bar 取「ts_init <= bar.ts 的最新一筆 funding rate」。
    bar 時間早於第一筆 funding 者填 ``None``(暖機期),不硬編填補策略。

    讀取走 ``jimq_engine.catalog.query_funding``(單一真相來源)。回傳 ``feature_fn``
    可放進 ``build_dataset(feature_fns=[...])``。funding 在此被當作「特徵」注入,
    平台不假設它一定要被使用(pluggable)。
    """

    def _fn(frame: pl.DataFrame) -> pl.DataFrame:
        if frame.height == 0:
            return frame.with_columns(pl.lit(None, dtype=pl.Float64).alias(name))
        bar_end = int(frame["ts"].max())
        updates = query_funding(catalog, instrument_id, start=None, end=bar_end)
        funding = pl.DataFrame(
            {
                "ts": [int(u.ts_init) for u in updates],
                name: [float(u.rate) for u in updates],
            },
            schema={"ts": pl.Int64, name: pl.Float64},
        ).sort("ts")
        if funding.height == 0:
            return frame.with_columns(pl.lit(None, dtype=pl.Float64).alias(name))
        return frame.sort("ts").join_asof(funding, on="ts", strategy="backward")

    return _fn
