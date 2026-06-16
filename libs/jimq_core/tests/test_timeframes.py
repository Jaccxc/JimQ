"""卡 #20 (W1) — timeframe ↔ Nautilus bar_type 共用映射。"""

from __future__ import annotations

import pytest

from jimq_core.timeframes import bar_type_for, supported_timeframes


def test_bar_type_for_minute_matches_catalog_convention():
    assert (
        bar_type_for("BTCUSDT-PERP.BINANCE", "1m")
        == "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"
    )


def test_bar_type_for_hour():
    assert (
        bar_type_for("BTCUSDT-PERP.BINANCE", "1h")
        == "BTCUSDT-PERP.BINANCE-1-HOUR-LAST-EXTERNAL"
    )


def test_unsupported_timeframe_raises():
    with pytest.raises(ValueError):
        bar_type_for("BTCUSDT-PERP.BINANCE", "7s")


def test_supported_timeframes_lists_literals():
    tfs = supported_timeframes()
    assert "1m" in tfs and "1h" in tfs
