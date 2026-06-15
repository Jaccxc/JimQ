"""jimq_core.features — 共用特徵庫(S0 佔位)。

反 train/serve skew 的基石:engine Strategy 推論與 research env 訓練共用同一
特徵建構碼。後續切片於此實作特徵函式。
"""

from __future__ import annotations
