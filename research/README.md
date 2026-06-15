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

## MLflow experiment tracking (#16)

`training/tracking.py` is a thin wrapper over MLflow. A `track_run` context
manager opens a run and logs params on entry; `log_metrics` / `log_params` /
`log_artifacts` log inside the block. `log_summary_to_mlflow` /
`track_summaries` map each `BacktestRunSummary` to one MLflow run
(params = strategy params + run identity, metrics = performance), and the batch
runner records every grid run automatically.

Tracking URI resolution: explicit arg > `MLFLOW_TRACKING_URI` env >
local sqlite fallback (`data/mlflow/mlflow.db`). MLflow 3.x disabled the file
tracking store, so the backend is always sqlite (local) or the docker server
(`http://localhost:5000`). Tests use a temp sqlite backend — fully offline,
no docker required.

```python
from jimq_research.training import track_run, log_metrics, track_summaries

with track_run("backtest", {"fast_period": 3, "slow_period": 8}) as run_id:
    log_metrics({"total_return": 0.012, "sharpe": 1.25})

# or record a whole grid of backtest summaries, one MLflow run each:
track_summaries(summaries, experiment="backtest")
```

Start the docker MLflow server (UI + REST API at http://localhost:5000;
sqlite backend store + proxied local artifact volume, localhost-only):

```bash
docker compose --profile research up -d mlflow
# then point research at it:
export MLFLOW_TRACKING_URI=http://localhost:5000
uv run python -m jimq_research.training.run_grid_demo --fast 3 5 --slow 8 13
```

## End-to-end research demo (#18)

`training/run_research_demo.py` stitches the **full research loop** end-to-end,
reusing every existing component (no rebuilt wheels):
dataset builder (#14) → train a clearly-labelled **stub** baseline (#18) →
register into the Postgres `model_registry` + save the artifact under
`data/models/<name>/<version>/` (#17) → run a **model-driven backtest** through
the generic `jimq_engine.strategies.ModelInferenceStrategy` (#4 engine) → log the
result as an MLflow run (#16).

The stub (LogisticRegression) only proves the **plumbing** is wired — it has no
alpha. `export/baseline.py` wraps any estimator into a `predict(features)->signal`
object, and `training/model_registry.py` registers metadata via SQLAlchemy Core
(app-level, schema owned by `api`'s hand-written Alembic). The strategy is
**model-type-agnostic** (C8): it loads any object with `predict` and computes
features in `on_bar` with the *same* `jimq_core.features` code as the dataset
builder (no train/serve skew).

```bash
cd research
uv run python -m jimq_research.training.run_research_demo
```

Full step-by-step (from zero to seeing the loop's results) + the **user
replacement points** (real model / features / labels / reward) are in
`docs/runbooks/20260616-research-demo.md`.

## Smoke test

```bash
cd research
uv run pytest                  # offline slices
RUN_DB_TESTS=1 uv run pytest   # + localhost Postgres persistence round-trip
```
