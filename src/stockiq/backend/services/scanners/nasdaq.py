"""NASDAQ-100 scanners: RSI batch scan and pre-market movers."""

import pandas as pd

from stockiq.backend.data.screeners import (
    fetch_nasdaq_rsi_scan,
    fetch_premarket_history,
    fetch_premarket_scan,
)


def get_nasdaq_rsi_scan() -> pd.DataFrame:
    """NASDAQ-100 batch scan: RSI, MAs, trend, volume ratio."""
    return fetch_nasdaq_rsi_scan()


def get_premarket_scan() -> dict:
    """
    Pre-market movers + 7-day close history for NASDAQ-100.

    Returns:
        {"scan": DataFrame, "history": DataFrame}
    """
    return {
        "scan":    fetch_premarket_scan(),
        "history": fetch_premarket_history(),
    }
