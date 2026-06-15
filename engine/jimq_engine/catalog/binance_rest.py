"""卡 #3 — Binance USD-M 期貨公開 REST adapter(純 I/O,無需 API key)。

職責邊界:只負責「抓 raw rows」,完全不做轉換(轉換在 transform.py)。
HTTP getter 可注入(``http``),預設用標準庫 urllib,讓測試可用 fake 注入、
不打真實網路。

公開 endpoint(免 API key):
- klines:        GET /fapi/v1/klines
- funding rate:  GET /fapi/v1/fundingRate
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Callable

BASE_URL = "https://fapi.binance.com"
KLINES_PATH = "/fapi/v1/klines"
FUNDING_PATH = "/fapi/v1/fundingRate"

# Binance kline interval → 毫秒(用於分頁推進)。
_INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
}

HttpGetter = Callable[[str, dict], list | dict]


def _urllib_get(url: str, params: dict, *, timeout: float = 30.0, retries: int = 3):
    """標準庫 HTTP GET → 解析 JSON。對 429/5xx 做簡單退避重試。"""
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "JimQ-ingest/0.1"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — adapter 邊界統一退避
            last_err = exc
            time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"Binance GET failed after {retries} retries: {full}") from last_err


class BinanceFuturesREST:
    """Binance USD-M 期貨公開 REST client。"""

    def __init__(
        self,
        http: HttpGetter | None = None,
        base_url: str = BASE_URL,
        kline_limit: int = 1500,
        funding_limit: int = 1000,
    ) -> None:
        self._http = http or _urllib_get
        self._base = base_url.rstrip("/")
        self._kline_limit = kline_limit
        self._funding_limit = funding_limit

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list]:
        """抓 [start_ms, end_ms] 區間的 klines raw rows,自動時間分頁。"""
        step = _INTERVAL_MS.get(interval, 60_000)
        url = self._base + KLINES_PATH
        cursor = start_ms
        out: list[list] = []
        while cursor <= end_ms:
            page = self._http(
                url,
                {
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": end_ms,
                    "limit": self._kline_limit,
                },
            )
            if not page:
                break
            out.extend(page)
            # 未滿頁 → 區間抓完。
            if len(page) < self._kline_limit:
                break
            # 推進到最後一根 openTime 之後一個 bar。
            cursor = int(page[-1][0]) + step
        return out

    def fetch_funding_rates(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> list[dict]:
        """抓 [start_ms, end_ms] 區間的 funding rate history raw rows,自動分頁。"""
        url = self._base + FUNDING_PATH
        cursor = start_ms
        out: list[dict] = []
        while cursor <= end_ms:
            page = self._http(
                url,
                {
                    "symbol": symbol,
                    "startTime": cursor,
                    "endTime": end_ms,
                    "limit": self._funding_limit,
                },
            )
            if not page:
                break
            out.extend(page)
            if len(page) < self._funding_limit:
                break
            cursor = int(page[-1]["fundingTime"]) + 1
        return out
