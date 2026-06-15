# jimq_research

JimQ RL/ML research package. **Isolated venv** — intentionally NOT a member of
the root uv workspace (heavy CUDA/torch deps stay isolated; see decisions C2/C7
and `docs/design/20260616-1845-repo-structure-final.md`).

## Setup

```bash
cd research
uv sync            # provisions research/.venv with the full research stack
```

CPU-only torch is pinned via the `pytorch-cpu` index for lightweight,
import-level use. GPU/CUDA wheels are deferred until actual training needs them.

## Layout

| Subpackage | Purpose |
|---|---|
| `data/`     | catalog Parquet -> Polars features / labels |
| `envs/`     | custom thin perp Gymnasium environments |
| `models/`   | sequence / policy / multimodal models (each independent) |
| `training/` | Stable-Baselines3 + MLflow training loops |
| `export/`   | trained weights + metadata -> model store |

Shared feature code comes from `jimq_core` (local path dependency) to eliminate
train/serve skew with the trading engine.

## Smoke test

```bash
cd research
uv run pytest
```
