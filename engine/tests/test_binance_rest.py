"""卡 #3 — Binance public REST adapter(I/O 隔離)。

不打真實網路:注入一個 fake HTTP getter 驗證 adapter 的行為:
- 組對正確的 endpoint 與參數
- 對 klines 做時間分頁(limit 上限後續抓)
- 回傳的是 raw rows(交給純 transform 處理)
"""

from __future__ import annotations

from jimq_engine.catalog.binance_rest import BinanceFuturesREST


class FakeHttp:
    """記錄請求並依序回傳預先排好的 JSON 回應。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []  # (url, params)

    def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        return self._responses.pop(0)


def _kline_row(open_ms):
    return [open_ms, "1", "2", "0.5", "1.5", "10", open_ms + 59999, "0", 1, "0", "0", "0"]


def test_fetch_klines_paginates_until_range_covered():
    # 第一頁回 2 根(滿頁=limit),第二頁回 1 根(未滿頁→停)。
    page1 = [_kline_row(1000), _kline_row(61000)]
    page2 = [_kline_row(121000)]
    http = FakeHttp([page1, page2])
    client = BinanceFuturesREST(http=http, kline_limit=2)

    rows = client.fetch_klines("BTCUSDT", "1m", start_ms=1000, end_ms=200000)

    # 全部 raw rows 串起來
    assert [r[0] for r in rows] == [1000, 61000, 121000]
    # 第一次呼叫打 klines endpoint,帶 symbol/interval/startTime/limit
    url, params = http.calls[0]
    assert url.endswith("/fapi/v1/klines")
    assert params["symbol"] == "BTCUSDT"
    assert params["interval"] == "1m"
    assert params["startTime"] == 1000
    assert params["limit"] == 2
    # 第二頁 startTime 應推進到上一頁最後一根之後
    assert http.calls[1][1]["startTime"] > 61000


def test_fetch_klines_single_page_no_extra_call():
    page1 = [_kline_row(1000)]  # 未滿頁
    http = FakeHttp([page1])
    client = BinanceFuturesREST(http=http, kline_limit=500)
    rows = client.fetch_klines("BTCUSDT", "1m", start_ms=1000, end_ms=200000)
    assert len(rows) == 1
    assert len(http.calls) == 1


def test_fetch_funding_rates():
    resp = [
        {"symbol": "BTCUSDT", "fundingTime": 1000, "fundingRate": "0.0001", "markPrice": "1"},
    ]
    http = FakeHttp([resp])
    client = BinanceFuturesREST(http=http)
    rows = client.fetch_funding_rates("BTCUSDT", start_ms=0, end_ms=2000)
    assert rows == resp
    url, params = http.calls[0]
    assert url.endswith("/fapi/v1/fundingRate")
    assert params["symbol"] == "BTCUSDT"
