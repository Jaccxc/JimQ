#!/usr/bin/env sh
# JimQ engine demo job(卡 #10):一次性跑「ingest 歷史 → 串流 EMA backtest」。
#
# 流程:
#   1) 等本棧 Redis(bus DB0)就緒。
#   2) 若 catalog 尚無 1m bars(且未 --skip-ingest),從 Binance public REST 灌
#      一小段 BTCUSDT-PERP 1m 歷史(INGEST_START..INGEST_END)。
#   3) 跑啟用 Redis Streams 的 EMA backtest:--keep 保留 stream、--publish-key 寫
#      LATEST_STREAM_KEY(API @latest 解析)。consumer 有足夠時間消費(#5 Rust MPSC
#      非同步 flush;stream 落地後才結束本 job)。
#
# 環境變數:
#   REDIS_HOST / REDIS_PORT — 本棧 redis 服務名(compose 注入)。
#   INGEST_START / INGEST_END — UTC YYYY-MM-DD(預設 2024-01-01..2024-01-02)。
#   EMA_FAST / EMA_SLOW — EMA 週期(預設 3 / 8,短歷史也能觸發交叉)。
#   JIMQ_SYNTHETIC=1 — 跳過 Binance,改用合成黃金交叉(離線可重現)。
set -eu

REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
INGEST_START="${INGEST_START:-2024-01-01}"
INGEST_END="${INGEST_END:-2024-01-02}"
EMA_FAST="${EMA_FAST:-3}"
EMA_SLOW="${EMA_SLOW:-8}"

echo "[engine] waiting for redis ${REDIS_HOST}:${REDIS_PORT} ..."
i=0
until python -c "
import os, socket, sys
s = socket.socket(); s.settimeout(2)
try:
    s.connect((os.environ.get('REDIS_HOST','redis'), int(os.environ.get('REDIS_PORT','6379')))); s.close()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
  i=$((i+1)); [ "$i" -ge 30 ] && { echo "[engine] redis 未就緒" >&2; exit 1; }; sleep 2
done

if [ "${JIMQ_SYNTHETIC:-0}" = "1" ]; then
  echo "[engine] JIMQ_SYNTHETIC=1 — 合成黃金交叉 backtest(離線可重現)"
  exec python scripts/run_streaming_backtest.py --synthetic --keep --publish-key \
    --fast "$EMA_FAST" --slow "$EMA_SLOW"
fi

# 真實 BTCUSDT-PERP 歷史(Binance public REST;免 API key,不碰 DB)。
echo "[engine] ingest BTCUSDT-PERP 1m ${INGEST_START}..${INGEST_END}(Binance public REST)..."
if ! python scripts/ingest_binance.py --start "$INGEST_START" --end "$INGEST_END" --intervals 1m; then
  echo "[engine] Binance ingest 失敗(可能無外網);改用合成資料 fallback" >&2
  exec python scripts/run_streaming_backtest.py --synthetic --keep --publish-key \
    --fast "$EMA_FAST" --slow "$EMA_SLOW"
fi

echo "[engine] streaming EMA backtest(真歷史 → Redis Streams)..."
exec python scripts/run_streaming_backtest.py --keep --publish-key \
  --fast "$EMA_FAST" --slow "$EMA_SLOW"
