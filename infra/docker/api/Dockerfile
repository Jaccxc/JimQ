# JimQ API 容器(卡 #10)。build context = repo 根。
# 啟動先 alembic upgrade head(鐵律 2:migration 已手寫,只跑 upgrade),再 uvicorn。
# uv workspace:api 依賴 jimq_core(workspace member)+ nautilus_trader。
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:/root/.local/bin:$PATH"

# uv(版本對齊本機 0.11.x)。
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv

WORKDIR /app

# 1) 先放 workspace 解析所需的 pyproject + lock(最大化 layer cache)。
COPY pyproject.toml uv.lock README.md ./
COPY libs/jimq_core/pyproject.toml libs/jimq_core/README.md ./libs/jimq_core/
COPY engine/pyproject.toml engine/README.md ./engine/
COPY api/pyproject.toml api/README.md api/LICENSE.boilerplate.md ./api/

# 2) 放套件原始碼(編輯安裝需要實際檔案存在)。
COPY libs/jimq_core/jimq_core ./libs/jimq_core/jimq_core
COPY engine/jimq_engine ./engine/jimq_engine
COPY api/src ./api/src
COPY api/alembic.ini ./api/
COPY api/migrations ./api/migrations

# 3) 只裝 api 套件(含 jimq_core 傳遞依賴);--no-dev 不裝測試 deps。
RUN uv sync --package jimq-api --no-dev --frozen

# 啟動腳本:alembic upgrade head -> uvicorn。
COPY infra/docker/api/entrypoint.sh /usr/local/bin/jimq-api-entrypoint
RUN chmod +x /usr/local/bin/jimq-api-entrypoint

EXPOSE 8000
WORKDIR /app/api
ENV PYTHONPATH=/app/api/src
ENTRYPOINT ["/usr/local/bin/jimq-api-entrypoint"]
