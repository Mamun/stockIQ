"""
Scanner service package.

All scanner endpoints are importable directly from this package:

    from stockiq.backend.services.scanners import get_bounce_radar_scan
    from stockiq.backend.services.scanners import get_candle_momentum_scan

To add a new scanner:
  1. Create (or extend) a module in this package for its domain (spx, nasdaq, etf, …)
  2. Add one function that calls the data layer
  3. Re-export it here in __all__
"""

from stockiq.backend.config import SCREENER_TICKER_COUNT

from .etf import get_etf_scan
from .nasdaq import get_nasdaq_rsi_scan, get_premarket_scan
from .spx import (
    get_bounce_radar_scan,
    get_munger_strategy_scan,
    get_candle_momentum_scan,
    get_squeeze_scan,
    get_strong_buy_scan,
    get_strong_sell_scan,
)


def get_screener_info() -> dict:
    """Screener runtime configuration for display in the UI."""
    return {"ticker_count": SCREENER_TICKER_COUNT}


__all__ = [
    # SPX
    "get_candle_momentum_scan",
    "get_bounce_radar_scan",
    "get_squeeze_scan",
    "get_munger_strategy_scan",
    "get_strong_buy_scan",
    "get_strong_sell_scan",
    # NASDAQ
    "get_nasdaq_rsi_scan",
    "get_premarket_scan",
    # ETF
    "get_etf_scan",
    # Config
    "get_screener_info",
]
