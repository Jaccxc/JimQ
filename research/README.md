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
| `training/` | Stable-Baselines3 + MLflow training loops; **batch backtest runner** (#15) |
| `export/`   | trained weights + metadata -> model store |

Shared feature code comes from `jimq_core` (local path dependency) to eliminate
train/serve skew with the trading engine.

## Batch backtest runner (#15)

`training/batch_backtest.py` runs an EMA param grid over the shared
ParquetDataCatalog by reusing the engine's `build_engine` (BacktestNode path),
producing one shared `jimq_core.schemas.BacktestRunSummary` per combo
(return / sharpe / max-drawdown / num-trades / final-balance).
`training/store.py` persists each summary into the localhost Postgres
`backtest_run` table via SQLAlchemy Core (app-level INSERT; schema is owned by
`api` and migrated with hand-written Alembic) and queries a `run_group` cohort
back for comparison.

```python
from jimq_engine.catalog.ingest import BAR_TYPE_1M, open_catalog
from jimq_research.training import run_grid, persist_summaries, query_runs, local_engine_url

summaries = run_grid(open_catalog(), param_grid={"fast_period": [3, 5], "slow_period": [8, 13]},
                     bar_type=BAR_TYPE_1M, timeframe="1m", run_group="grid-1")
url = local_engine_url()
persist_summaries(summaries, engine_url=url)
rows = query_runs(url, run_group="grid-1")   # compare runs
```

Runnable demo (persists to Postgres, prints a comparison table):

```bash
cd research
uv run python -m jimq_research.training.run_grid_demo --fast 3 5 --slow 8 13
```

## Smoke test

```bash
cd research
uv run pytest                  # offline slices
RUN_DB_TESTS=1 uv run pytest   # + localhost Postgres persistence round-trip
```
