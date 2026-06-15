"""卡 #18 — baseline stub 模型 + model store glue 行為測試。

行為(透過 public interface,不驗實作細節):

- ``train_baseline_stub(dataset)`` 從 Polars 資料集(特徵欄 + 標籤欄)訓練一個
  **明確標註為佔位 stub** 的 baseline 模型,回傳一個有 ``predict`` 介面的物件
  (模型類型無關 — ModelInferenceStrategy 只需 predict)。
- ``save_model_artifact`` 把訓練好的模型序列化到
  ``data/models/<name>/<version>/``(對齊 api ModelStore 的磁碟慣例)。
- ``load_model_artifact`` 把它載回成同樣有 ``predict`` 的物件(round-trip)。
- predict 對相同特徵列確定(同輸入同輸出)。

stub 的重點是證明 PLUMBING 通(dataset→train→序列化→載回→predict),不是 alpha。
"""

from __future__ import annotations

import polars as pl

from jimq_research.export import (
    load_model_artifact,
    save_model_artifact,
    train_baseline_stub,
)


def _toy_dataset() -> pl.DataFrame:
    # 兩個特徵 + 二元標籤;可線性分開,確保 stub 能 fit(只為 plumbing)。
    rows = []
    for i in range(40):
        f1 = float(i)
        f2 = float(40 - i)
        label = 1 if f1 > f2 else 0
        rows.append({"ema_fast": f1, "ema_slow": f2, "label_up": label})
    return pl.DataFrame(rows)


def test_train_returns_predict_capable_model():
    model = train_baseline_stub(
        _toy_dataset(),
        feature_cols=["ema_fast", "ema_slow"],
        label_col="label_up",
    )
    assert hasattr(model, "predict"), "stub 必須提供 predict 介面(模型類型無關)"

    # 餵一列特徵 dict(ModelInferenceStrategy 餵的就是 dict)→ 回傳純量訊號。
    out = model.predict({"ema_fast": 39.0, "ema_slow": 1.0})
    assert out is not None


def test_predict_is_deterministic():
    model = train_baseline_stub(
        _toy_dataset(),
        feature_cols=["ema_fast", "ema_slow"],
        label_col="label_up",
    )
    feat = {"ema_fast": 30.0, "ema_slow": 10.0}
    assert model.predict(feat) == model.predict(feat)


def test_save_and_load_roundtrip(tmp_path):
    model = train_baseline_stub(
        _toy_dataset(),
        feature_cols=["ema_fast", "ema_slow"],
        label_col="label_up",
    )
    feat = {"ema_fast": 35.0, "ema_slow": 5.0}
    before = model.predict(feat)

    artifact_dir = save_model_artifact(
        model, name="baseline-stub", version="test", models_root=tmp_path
    )
    # 對齊 api ModelStore 磁碟慣例:data/models/<name>/<version>/。
    assert artifact_dir == tmp_path / "baseline-stub" / "test"
    assert any(artifact_dir.iterdir()), "artifact 目錄應有序列化檔案"

    reloaded = load_model_artifact(artifact_dir)
    assert hasattr(reloaded, "predict")
    assert reloaded.predict(feat) == before, "round-trip 後 predict 應一致"
