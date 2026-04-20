"""
SPY dashboard facade — single import point for the landing page.

Composes from spy_service (SPY instrument data) and market_service
(market-wide context: VIX, indices, put/call ratio).

Frontend imports only from here; domain services remain independently
usable by ai_forecast_service and other consumers.
"""

from stockiq.backend.services.market_service import (
    get_market_overview,
    get_put_call_ratio,
    get_vix_chart_df,
    get_vix_gap_history,
    get_vix_ohlc_df,
)
from stockiq.backend.services.spy_service import (
    get_spy_chart_df,
    get_spy_gap_table_data,
    get_spy_quote,
)

__all__ = [
    # SPY instrument
    "get_spy_quote",
    "get_spy_chart_df",
    "get_spy_gap_table_data",
    # Market context
    "get_market_overview",
    "get_put_call_ratio",
    "get_vix_chart_df",
    "get_vix_gap_history",
    "get_vix_ohlc_df",
]
