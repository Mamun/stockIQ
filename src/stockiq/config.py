"""
Frontend visual configuration.

Reads from:
  config/indicators.yml — MA periods + colors, Fibonacci levels + colors (shared with backend)
  config/ui.yml         — reversal patterns, chart period options (frontend-only)
"""
from pathlib import Path

import yaml

_cfg_dir = Path(__file__).parent.parent.parent / "config"

with open(_cfg_dir / "indicators.yml") as _f:
    _ind: dict = yaml.safe_load(_f)

with open(_cfg_dir / "ui.yml") as _f:
    _ui: dict = yaml.safe_load(_f)

# ── Moving averages ────────────────────────────────────────────────────────────
_ma = _ind["moving_averages"]
MA_PERIODS:   list[int]      = _ma["periods"]
MA_COLORS:    dict[int, str] = {int(k): v for k, v in _ma["colors"].items()}
MA200W_COLOR: str             = _ma["weekly_ma200_color"]

# ── Fibonacci ──────────────────────────────────────────────────────────────────
FIB_COLORS: list[str] = _ind["fibonacci"]["colors"]

# ── Reversal patterns ──────────────────────────────────────────────────────────
REVERSAL_PATTERNS: list[tuple] = [
    (p["col"], p["label"], p["bullish"], p["symbol"], p["color"])
    for p in _ui["reversal_patterns"]
]

# ── Chart period options ───────────────────────────────────────────────────────
PERIOD_OPTIONS: dict[str, int] = _ui["period_options"]
