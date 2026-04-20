"""ETF momentum, RSI, and MA scanner."""

import pandas as pd

from stockiq.backend.data.screeners import fetch_etf_scan


def get_etf_scan(categories: tuple[str, ...] | None = None) -> pd.DataFrame:
    """ETF momentum/RSI/MA scan for ETF_UNIVERSE, optionally filtered by category."""
    return fetch_etf_scan(categories)
