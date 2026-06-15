"""jimq_core — JimQ 共用套件骨架(S0)。

匯出佔位模組 schemas / features / constants,供 engine 與 api 共用。
"""

from __future__ import annotations

__version__ = "0.1.0"

from jimq_core import constants, features, schemas

__all__ = ["constants", "features", "schemas", "__version__"]
