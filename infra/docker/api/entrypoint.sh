#!/usr/bin/env sh
# JimQ API 啟動(卡 #10):等 postgres ready → alembic upgrade head → uvicorn。
# 鐵律 2:只跑已手寫的 migration upgrade,絕不 --autogenerate / 直接 DDL。
set -eu

echo "[jimq-api] waiting for postgres ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432} ..."
# 用 python 探測(slim 無 pg_isready);最多 ~60s。
i=0
until python -c "
import os, socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect((os.environ.get('POSTGRES_HOST','postgres'), int(os.environ.get('POSTGRES_PORT','5432'))))
    s.close()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
  i=$((i+1))
  if [ "$i" -ge 30 ]; then
    echo "[jimq-api] postgres 未就緒,放棄等待" >&2
    break
  fi
  sleep 2
done

echo "[jimq-api] running alembic upgrade head ..."
alembic upgrade head

echo "[jimq-api] starting uvicorn ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
