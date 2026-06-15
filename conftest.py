"""pytest 根設定:把 repo 根加入 sys.path,讓 top-level ``scripts`` 套件可被測試 import。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
