"""jimq_research — JimQ RL/ML research package.

Lives in an isolated venv (heavy CUDA/torch deps), intentionally NOT part of the
root uv workspace. Shares feature code with the trading engine via ``jimq_core``
to eliminate train/serve skew.

Subpackages:
- ``data``     : catalog Parquet -> Polars features / labels
- ``envs``     : custom thin perp Gymnasium environments
- ``models``   : sequence / policy / multimodal models (each independent)
- ``training`` : Stable-Baselines3 + MLflow training loops
- ``export``   : weights + metadata -> model store
"""

__version__ = "0.1.0"
