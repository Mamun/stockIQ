"""
Backend configuration.

Reads from:
  config/indicators.yml          — MA periods, Fibonacci levels (shared with frontend)
  config/screeners.yml           — ticker universes, scan limits (backend-only)
  src/stockiq/backend/config/cache.yml — per-function TTL values (backend-only)

Exports:
  CACHE_TTL             — per-function cache TTL values (seconds)
  MA_PERIODS            — moving-average window sizes used in calculations
  FIB_LEVELS            — Fibonacci retracement levels used in calculations
  SPX_TICKERS           — S&P 500 ticker universe for scanners
  NASDAQ_100_TICKERS    — NASDAQ-100 ticker universe
  SCREENER_TICKER_COUNT — how many SPX tickers to scan (env-overridable)
"""

import os
from pathlib import Path

import yaml

_backend_dir = Path(__file__).parent
_root_config = Path(__file__).parent.parent.parent.parent.parent / "config"

# ── Cache TTLs (backend-only) ──────────────────────────────────────────────────
with open(_backend_dir / "cache.yml") as _f:
    _cache_raw: dict = yaml.safe_load(_f)

CACHE_TTL: dict[str, int] = {
    fn: ttl
    for section in _cache_raw.values()
    for fn, ttl in section.items()
}

# ── Shared indicator parameters ────────────────────────────────────────────────
with open(_root_config / "indicators.yml") as _f:
    _ind: dict = yaml.safe_load(_f)

MA_PERIODS: list[int]   = _ind["moving_averages"]["periods"]
FIB_LEVELS: list[float] = _ind["fibonacci"]["levels"]

# ── Screener universes (backend-only) ─────────────────────────────────────────
with open(_root_config / "screeners.yml") as _f:
    _scr: dict = yaml.safe_load(_f)

_screener = _scr["screener"]
SCREENER_TICKER_COUNT: int = int(
    os.environ.get("SCREENER_TICKER_COUNT", _screener["default_count"])
)
SPX_TICKERS: list[str]        = _screener["universe"][:SCREENER_TICKER_COUNT]
NASDAQ_100_TICKERS: list[str] = _scr["nasdaq_100"]
