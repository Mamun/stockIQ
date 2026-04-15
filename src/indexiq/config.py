"""
Application configuration loaded from config/app.yml.

All other modules import from here as before — nothing else changes.
To adjust colours, periods, tickers, or patterns edit config/app.yml.
"""
import os
from pathlib import Path

import yaml

_cfg_path = Path(__file__).parent.parent.parent / "config" / "app.yml"
with open(_cfg_path) as _f:
    _cfg: dict = yaml.safe_load(_f)

# ── Moving averages ────────────────────────────────────────────────────────────
_ma = _cfg["moving_averages"]
MA_PERIODS: list[int]       = _ma["periods"]
MA_COLORS:  dict[int, str]  = {int(k): v for k, v in _ma["colors"].items()}
MA200W_COLOR: str            = _ma["weekly_ma200_color"]

# ── Fibonacci ──────────────────────────────────────────────────────────────────
FIB_LEVELS: list[float] = _cfg["fibonacci"]["levels"]
FIB_COLORS: list[str]   = _cfg["fibonacci"]["colors"]

# ── Reversal patterns ──────────────────────────────────────────────────────────
# Preserved as list-of-tuples: (col, label, bullish, symbol, color)
REVERSAL_PATTERNS: list[tuple] = [
    (p["col"], p["label"], p["bullish"], p["symbol"], p["color"])
    for p in _cfg["reversal_patterns"]
]

# ── Screener ticker pool ───────────────────────────────────────────────────────
_screener = _cfg["screener"]
SCREENER_TICKER_COUNT: int  = int(os.environ.get("SCREENER_TICKER_COUNT", _screener["default_count"]))
SPX_TICKERS: list[str]      = _screener["universe"][:SCREENER_TICKER_COUNT]

# ── Chart period options ───────────────────────────────────────────────────────
PERIOD_OPTIONS: dict[str, int] = _cfg["period_options"]
