"""Screeners package — domain-split screener functions with backward-compatible exports."""

from .candle     import fetch_candle_momentum_scan
from .momentum   import (
    fetch_bounce_radar_scan,
    fetch_nasdaq_rsi_scan,
    fetch_premarket_scan,
    fetch_premarket_history,
)
from .volatility import fetch_squeeze_scan
from .fundamental import fetch_munger_strategy_scan
from .analyst    import fetch_strong_buy_scan, fetch_strong_sell_scan
from .etf        import fetch_etf_scan
from ._shared    import ETF_UNIVERSE

__all__ = [
    "fetch_candle_momentum_scan",
    "fetch_bounce_radar_scan",
    "fetch_nasdaq_rsi_scan",
    "fetch_premarket_scan",
    "fetch_premarket_history",
    "fetch_squeeze_scan",
    "fetch_munger_strategy_scan",
    "fetch_strong_buy_scan",
    "fetch_strong_sell_scan",
    "fetch_etf_scan",
    "ETF_UNIVERSE",
]
