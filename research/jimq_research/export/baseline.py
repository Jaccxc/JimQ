"""卡 #18 — baseline stub 模型 + model artifact 序列化(export 層)。

╔══════════════════════════════════════════════════════════════════════════╗
║  USER REPLACEMENT POINT — 這不是真策略,是你要替換的骨架。                  ║
║                                                                            ║
║  ``train_baseline_stub`` 訓練一個 sklearn LogisticRegression 當 baseline,  ║
║  唯一目的:證明 PLUMBING 通(dataset→train→register→model 驅動 backtest）。  ║
║  它沒有 alpha。要做真研究時:                                                ║
║    - 換成你的真模型(序列模型 / RL policy / 多模態 …);                      ║
║    - 換成你的真特徵(在 dataset builder 與 ModelInferenceStrategy 兩端       ║
║      共用同一份 jimq_core.features,避免 train/serve skew);                  ║
║    - 換成你的真標籤 / 獎勵(label_fn / reward)。                            ║
║  只要產出的物件有 ``predict(features_dict) -> signal`` 介面,下游 plumbing   ║
║  (ModelInferenceStrategy / registry / backtest)完全不用改 —— 模型類型無關。 ║
╚══════════════════════════════════════════════════════════════════════════╝

序列化採 joblib(sklearn 慣例)。``PredictModel`` wrapper 把模型統一成
``predict(features: dict) -> signal`` 的介面,讓 ModelInferenceStrategy
不必知道底層是什麼框架(C8 可插拔)。磁碟佈局對齊 api ``ModelStore``:
``<models_root>/<name>/<version>/model.joblib``。
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import joblib
import numpy as np
import polars as pl

_ARTIFACT_FILENAME = "model.joblib"


class PredictModel:
    """把任意 sklearn-like 估計器包成 ``predict(features_dict) -> signal``。

    ModelInferenceStrategy 餵的是特徵 dict(``{"ema_fast": ..., ...}``);此 wrapper
    依固定 ``feature_cols`` 取值組成向量、呼叫底層 ``estimator.predict``,再把
    類別輸出映成交易訊號(1 → +1 做多 / 0 → -1 做空)。

    這是「模型類型無關」的接點:只要換掉底層 estimator(或整個 wrapper),
    ModelInferenceStrategy 不用改。輸出語意對齊 strategy 的 USER REPLACEMENT
    POINT #2(signal>0 做多 / <0 做空 / 0 不動)。
    """

    def __init__(self, estimator, feature_cols: Sequence[str]) -> None:
        self.estimator = estimator
        self.feature_cols = list(feature_cols)

    def predict(self, features: Mapping[str, float]) -> int:
        x = np.array([[float(features[c]) for c in self.feature_cols]], dtype=float)
        pred = int(self.estimator.predict(x)[0])
        # 二元分類 → 交易訊號:漲(1)做多、跌(0)做空。
        return 1 if pred == 1 else -1


def train_baseline_stub(
    dataset: pl.DataFrame,
    *,
    feature_cols: Sequence[str],
    label_col: str,
) -> PredictModel:
    """訓練佔位 baseline stub(LogisticRegression)。回傳 ``PredictModel`` wrapper。

    ⚠️ USER REPLACEMENT POINT(見模組頂註):這不是真策略。丟掉暖機期(特徵或
    標籤為 null 的列),用剩下的列 fit 一個 logistic regression。確定性:固定
    solver、無隨機(同輸入同模型)。
    """
    from sklearn.linear_model import LogisticRegression

    cols = list(feature_cols) + [label_col]
    clean = dataset.select(cols).drop_nulls()
    if clean.height == 0:
        raise ValueError("資料集去除 null 後為空;檢查暖機期 / 標籤建構。")

    x = clean.select(feature_cols).to_numpy().astype(float)
    y = clean[label_col].to_numpy().astype(int)

    # 退化標籤(單一類別)時 LogisticRegression 會炸 —— stub 給個明確錯誤。
    if len(set(y.tolist())) < 2:
        raise ValueError(
            "標籤只有單一類別,無法 fit 二元 baseline;調整標籤建構或區間。"
        )

    estimator = LogisticRegression(max_iter=1000)
    estimator.fit(x, y)
    return PredictModel(estimator, feature_cols=feature_cols)


def save_model_artifact(
    model: PredictModel,
    *,
    name: str,
    version: str,
    models_root: str | Path,
) -> Path:
    """把 ``model`` 序列化到 ``<models_root>/<name>/<version>/model.joblib``。

    回傳 artifact 目錄(對齊 api ``ModelStore.artifact_dir`` 慣例),供
    register 時寫進 model_registry.artifact_path。
    """
    artifact_dir = Path(models_root) / name / version
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_dir / _ARTIFACT_FILENAME)
    return artifact_dir


def load_model_artifact(artifact_dir: str | Path) -> PredictModel:
    """從 artifact 目錄載回 ``PredictModel``(有 ``predict`` 介面)。

    ModelInferenceStrategy 用此把 registry 取回的權重變成可推論物件。
    """
    path = Path(artifact_dir) / _ARTIFACT_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"no model artifact at {path}")
    return joblib.load(path)
