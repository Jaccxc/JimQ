"""data — catalog Parquet -> Polars features / labels(卡 #14)。

公開介面:

- ``build_dataset``:catalog → jimq_core.features → 訓練就緒 Polars 資料集,
  特徵/標籤以 pluggable callable 注入(平台不硬編 alpha)。
- ``ema_feature``:內建特徵 factory,復用 ``jimq_core.features``(train/serve parity)。
- 型別別名 ``FeatureFn`` / ``LabelFn`` 供呼叫端標註自訂特徵/標籤函式。
"""

from jimq_research.data.builder import (
    FeatureFn,
    LabelFn,
    build_dataset,
    ema_feature,
)

__all__ = ["build_dataset", "ema_feature", "FeatureFn", "LabelFn"]
