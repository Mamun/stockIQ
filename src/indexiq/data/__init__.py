"""
data package — re-exports all public fetch functions so existing imports remain unchanged.

Sub-modules:
  data.fetch      — raw OHLCV and company search
  data.market     — live SPY/VIX/index quotes
  data.screeners  — scanner functions (bounce, squeeze, munger, strong buy/sell, screener)
"""
from indexiq.data.fetch import fetch_ohlcv, get_company_name, search_companies
from indexiq.data.market import (
    fetch_index_snapshot,
    fetch_spx_intraday,
    fetch_spx_quote,
    fetch_vix_history,
    fetch_vix_ohlc,
)
from indexiq.data.screeners import (
    fetch_bounce_candidates,
    fetch_munger_candidates,
    fetch_nasdaq_oversold,
    fetch_nasdaq_rsi_scan,
    fetch_premarket_history,
    fetch_premarket_scan,
    fetch_spx_recommendations,
    fetch_squeeze_candidates,
    fetch_strong_buy_candidates,
    fetch_strong_sell_candidates,
)

__all__ = [
    "fetch_ohlcv",
    "get_company_name",
    "search_companies",
    "fetch_index_snapshot",
    "fetch_spx_intraday",
    "fetch_spx_quote",
    "fetch_vix_history",
    "fetch_vix_ohlc",
    "fetch_bounce_candidates",
    "fetch_munger_candidates",
    "fetch_spx_recommendations",
    "fetch_squeeze_candidates",
    "fetch_strong_buy_candidates",
    "fetch_strong_sell_candidates",
    "fetch_nasdaq_oversold",
    "fetch_nasdaq_rsi_scan",
    "fetch_premarket_scan",
    "fetch_premarket_history",
]
