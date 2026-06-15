"""jimq_engine.catalog — Binance ingest 與 ParquetDataCatalog 工具(卡 #3)。

模組分層:
- instruments  : Nautilus instrument 定義(BTCUSDT-PERP.BINANCE)。
- transform    : 純函式 raw Binance → Nautilus 物件(無 I/O)。
- binance_rest : 公開 REST adapter(I/O 隔離,getter 可注入)。
- ingest       : 轉換結果 → catalog 寫入 + 時間區間查詢(idempotent)。
"""

from __future__ import annotations
