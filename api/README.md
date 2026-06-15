# jimq-api

JimQ FastAPI 後端。Fork 自 `benavlabs/FastAPI-boilerplate` **v0.15.0 classic**
(`src/app/` 佈局,MIT),剝除 user/tier/auth(見 decisions-confirmed B5)。
原始授權見 `LICENSE.boilerplate.md`。

## 結構

```
api/
├── alembic.ini            # 手寫 migration(鐵律 2,不 --autogenerate)
├── migrations/            # alembic env + 版本
└── src/app/
    ├── main.py            # create_application 入口
    ├── core/              # config(精簡)/setup/db/exceptions/utils.cache/logger
    ├── models/            # backtest_run(第一張應用資料表)
    ├── schemas/ crud/     # Pydantic + FastCRUD(沿用 posts 範本)
    └── api/v1/            # health + backtests(FastCRUD crud_router)
```

剝除項目(decisions-confirmed B5):users / posts / tiers / rate_limit /
login / logout / `core/security` / token_blacklist / admin(crudadmin)/
`scripts.create_first_*` / ARQ worker / auth deps。Redis cache 用獨立 DB index
(`REDIS_CACHE_DB`,預設 1),與 Nautilus bus(DB 0)隔離(鐵律 5)。

## 開發

```bash
# 從 repo root(uv workspace)
uv sync

# 開機
cd api && uv run uvicorn app.main:app --reload   # GET /health -> 200

# DB schema(手寫 migration,localhost only)
cd api && uv run alembic upgrade head

# 測試(快速離線切片)
uv run pytest api/tests
# 含 localhost Postgres round-trip
RUN_DB_TESTS=1 uv run pytest api/tests
```

設定預設值(localhost / postgres / 1234 / jimq）已對齊 docker-compose;如需覆寫,
於 `api/.env` 設定(見 `api/.env.example`)。
