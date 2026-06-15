"""卡 #3 — 把轉換後的 Nautilus 物件寫入 ParquetDataCatalog,並提供查詢。

職責邊界:
- 本模組只碰「轉換結果 → catalog」與「catalog → 查詢」,不打網路。
- 寫入要求 ts_init 單調遞增(transform 已排序)。
- ingest_* 為 idempotent:先刪掉本批涵蓋的 ts_init 區間再寫,重複執行不產生重複列。

catalog 路徑慣例:data/catalog(對齊 repo 結構文件)。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from nautilus_trader.model.data import Bar, BarType, FundingRateUpdate
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from jimq_engine.catalog.instruments import BTCUSDT_PERP_BINANCE_ID
from jimq_engine.catalog.transform import (
    funding_history_to_updates,
    klines_to_bars,
)

# 預設 catalog 路徑(repo 根的 data/catalog;data/ 已 gitignore)。
DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "catalog"
)

# BTCUSDT-PERP 的標準 bar 類型。
BAR_TYPE_1M = BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL")
BAR_TYPE_5M = BarType.from_str("BTCUSDT-PERP.BINANCE-5-MINUTE-LAST-EXTERNAL")


def open_catalog(path: str | os.PathLike | None = None) -> ParquetDataCatalog:
    """開啟(必要時建立)本地 ParquetDataCatalog。

    路徑優先序:顯式 ``path`` > ``JIMQ_CATALOG_PATH`` 環境變數 > repo 預設
    ``data/catalog``。env 覆寫讓全棧容器(卡 #10)engine 與 api 指向同一份共享
    catalog volume(``/data/catalog``),不破壞既有本機開發預設。
    """
    if path is not None:
        catalog_path = Path(path)
    elif os.environ.get("JIMQ_CATALOG_PATH"):
        catalog_path = Path(os.environ["JIMQ_CATALOG_PATH"])
    else:
        catalog_path = DEFAULT_CATALOG_PATH
    catalog_path.mkdir(parents=True, exist_ok=True)
    return ParquetDataCatalog(path=str(catalog_path))


def _write_idempotent(
    catalog: ParquetDataCatalog,
    data_cls: type,
    objects: list,
    identifier: str,
) -> int:
    """刪掉本批 ts_init 區間後再寫,確保可重複執行不重複。"""
    if not objects:
        return 0
    start = objects[0].ts_init
    end = objects[-1].ts_init
    catalog.delete_data_range(
        data_cls=data_cls, identifier=identifier, start=start, end=end
    )
    catalog.write_data(objects)
    return len(objects)


def ingest_bars(
    catalog: ParquetDataCatalog,
    raw_klines: Sequence[Sequence],
    instrument: Instrument,
    bar_type: BarType = BAR_TYPE_1M,
) -> int:
    """轉換 klines → Bar 並寫入 catalog;回傳寫入筆數。"""
    bars = klines_to_bars(raw_klines, bar_type, instrument)
    return _write_idempotent(catalog, Bar, bars, str(bar_type))


def ingest_funding(
    catalog: ParquetDataCatalog,
    raw_funding: Sequence[dict],
    instrument_id: InstrumentId,
) -> int:
    """轉換 funding history → FundingRateUpdate 並寫入 catalog;回傳寫入筆數。"""
    updates = funding_history_to_updates(raw_funding, instrument_id)
    return _write_idempotent(
        catalog, FundingRateUpdate, updates, str(instrument_id)
    )


def query_bars(
    catalog: ParquetDataCatalog,
    bar_type: BarType = BAR_TYPE_1M,
    start: int | None = None,
    end: int | None = None,
) -> list[Bar]:
    """依 bar_type + [start, end] 區間(ts_init, ns)查回 Bar 切片。"""
    return catalog.query(
        data_cls=Bar,
        identifiers=[str(bar_type)],
        start=start,
        end=end,
    )


def query_funding(
    catalog: ParquetDataCatalog,
    instrument_id: InstrumentId = BTCUSDT_PERP_BINANCE_ID,
    start: int | None = None,
    end: int | None = None,
) -> list[FundingRateUpdate]:
    """依 instrument + [start, end] 區間查回 FundingRateUpdate 切片。"""
    return catalog.query(
        data_cls=FundingRateUpdate,
        identifiers=[str(instrument_id)],
        start=start,
        end=end,
    )
