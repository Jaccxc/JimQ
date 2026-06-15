"""store 服務 — 歷史 bars 查詢(卡 #8)。

直接用 nautilus ``ParquetDataCatalog`` 讀 ``data/catalog`` 的歷史 K 線,依
symbol + timeframe + 起迄(epoch 奈秒)查詢,映射成 ``jimq_core.schemas.BarDTO``。

設計:
- 純讀路徑,不動 DB / alembic(本卡無 schema 變更)。
- 此模組是**同步**的(nautilus catalog 讀取為同步阻塞);非阻塞包裝由
  endpoint 以 ``run_in_threadpool`` 負責(關注點分離)。
- 邊界一致:未知 symbol / 未知 timeframe / 空區間皆回空列表。

api 依賴 jimq_core + nautilus_trader,**不依賴 engine**(故 catalog 路徑與 BarType
慣例在此自行定義,與 engine 端定義保持一致)。
"""

from __future__ import annotations

from pathlib import Path

from jimq_core.schemas import BarDTO
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# repo 根的 data/catalog(store.py 位於 api/src/app/services/ → parents[4] = repo 根)。
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[4] / "data" / "catalog"

# 支援的 timeframe → Nautilus BarType 規格片段(對齊 engine ingest 慣例)。
_TIMEFRAME_TO_SPEC: dict[str, str] = {
    "1m": "1-MINUTE",
    "5m": "5-MINUTE",
}

# Nautilus BarType 字尾:LAST 價格、EXTERNAL 聚合(交易所給的 K 線)。
_BAR_TYPE_SUFFIX = "LAST-EXTERNAL"


def supported_timeframes() -> tuple[str, ...]:
    """回傳支援的 timeframe 代碼。"""
    return tuple(_TIMEFRAME_TO_SPEC)


def bar_type_str(symbol: str, timeframe: str) -> str | None:
    """組出 ``{symbol}-{spec}-LAST-EXTERNAL``;未知 timeframe 回 None。"""
    spec = _TIMEFRAME_TO_SPEC.get(timeframe)
    if spec is None:
        return None
    return f"{symbol}-{spec}-{_BAR_TYPE_SUFFIX}"


def query_bars(
    symbol: str,
    timeframe: str,
    start: int | None,
    end: int | None,
    *,
    catalog_path: str | Path | None = None,
) -> list[BarDTO]:
    """依 symbol + timeframe + [start, end](epoch 奈秒)查歷史 bars。

    回傳 ``BarDTO`` 列表(依 ts 升冪)。未知 symbol/timeframe、空區間皆回空列表。
    本函式為同步阻塞;呼叫端負責 threadpool 包裝。
    """
    bt_str = bar_type_str(symbol, timeframe)
    if bt_str is None:
        return []

    path = Path(catalog_path) if catalog_path is not None else DEFAULT_CATALOG_PATH
    if not path.exists():
        return []

    catalog = ParquetDataCatalog(path=str(path))
    bar_type = BarType.from_str(bt_str)
    bars: list[Bar] = catalog.query(
        data_cls=Bar,
        identifiers=[str(bar_type)],
        start=start,
        end=end,
    )
    return [BarDTO.from_nautilus_bar(b) for b in bars]
