"""export — trained weights + metadata -> model store(卡 #18）。

公開介面:

- ``train_baseline_stub``:訓練佔位 baseline stub 模型(USER REPLACEMENT POINT)。
- ``save_model_artifact`` / ``load_model_artifact``:序列化 / 載回(對齊 api
  ModelStore 的 ``data/models/<name>/<version>/`` 磁碟慣例)。
- ``PredictModel``:把模型統一成 ``predict(features_dict) -> signal`` 介面
  (模型類型無關 / C8 可插拔)。
"""

from jimq_research.export.baseline import (
    PredictModel,
    load_model_artifact,
    save_model_artifact,
    train_baseline_stub,
)

__all__ = [
    "PredictModel",
    "train_baseline_stub",
    "save_model_artifact",
    "load_model_artifact",
]
