# JimQ engine 容器(卡 #10)— 一次性 job:ingest 一小段歷史 + 跑啟用 Redis
# Streams 的 EMA backtest,把事件灌進本機本棧 Redis(bus DB0),並 --publish-key
# 寫 LATEST_STREAM_KEY 供 API @latest 解析。build context = repo 根。
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY libs/jimq_core/pyproject.toml libs/jimq_core/README.md ./libs/jimq_core/
COPY engine/pyproject.toml engine/README.md ./engine/
COPY api/pyproject.toml api/README.md api/LICENSE.boilerplate.md ./api/

COPY libs/jimq_core/jimq_core ./libs/jimq_core/jimq_core
COPY engine/jimq_engine ./engine/jimq_engine
COPY scripts ./scripts

# engine + core(redis 也在 engine deps);--no-dev。
RUN uv sync --package jimq-engine --no-dev --frozen

# redis 套件(streaming backtest 腳本直接用 redis client 觀察/發佈 key)。
RUN uv pip install "redis>=5"

COPY infra/docker/engine/run-demo.sh /usr/local/bin/jimq-engine-demo
RUN chmod +x /usr/local/bin/jimq-engine-demo

# data/catalog 掛 volume(與 api 共享,讓 REST /bars 讀到同一份歷史)。
ENV PYTHONPATH=/app
ENTRYPOINT ["/usr/local/bin/jimq-engine-demo"]
