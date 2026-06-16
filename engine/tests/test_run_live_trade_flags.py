"""卡 #29 (P2-S3) — run_live_trade.py 風控旗標(--max-notional / --max-order-submit-rate)。

行為測試(透過 public arg parser interface,不啟動真節點 / 不連網):
- ``build_arg_parser()`` 解析 ``--max-notional`` 與 ``--max-order-submit-rate``。
- 預設值對齊 live 節點保守風控(DEFAULT_MAX_NOTIONAL_USDT / DEFAULT_MAX_ORDER_SUBMIT_RATE)。
- 覆寫旗標會反映在解析結果(供 main 傳入 build_live_trade_node_config)。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from jimq_engine.nodes.live import (
    DEFAULT_MAX_NOTIONAL_USDT,
    DEFAULT_MAX_ORDER_SUBMIT_RATE,
)

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_live_trade.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_live_trade_mod", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_live_trade_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_risk_flags_default_to_conservative_values():
    mod = _load_module()
    args = mod.build_arg_parser().parse_args([])
    assert args.max_notional == DEFAULT_MAX_NOTIONAL_USDT
    assert args.max_order_submit_rate == DEFAULT_MAX_ORDER_SUBMIT_RATE


def test_risk_flags_can_be_overridden():
    mod = _load_module()
    args = mod.build_arg_parser().parse_args(
        ["--max-notional", "250", "--max-order-submit-rate", "5/00:00:01"]
    )
    assert args.max_notional == 250
    assert args.max_order_submit_rate == "5/00:00:01"
