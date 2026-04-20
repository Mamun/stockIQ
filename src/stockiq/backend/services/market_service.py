"""Market-wide data service (indices, VIX, put/call ratio)."""

import pandas as pd

from stockiq.backend.data.market import (
    fetch_index_snapshot,
    fetch_put_call_ratio,
    fetch_vix_history,
    fetch_vix_ohlc,
)
from stockiq.backend.models.indicators import compute_daily_gaps

_VIX_ZONES = [
    (15,  "Calm"),
    (20,  "Normal"),
    (30,  "Elevated"),
    (float("inf"), "Extreme Fear"),
]


def _get_index_snapshot() -> pd.DataFrame:
    """Day-change snapshot for S&P 500, Nasdaq, Dow, Russell, SPY, QQQ, VIX. Cached 120 s."""
    return fetch_index_snapshot()


def get_vix_chart_df(period: str = "1y") -> pd.DataFrame:
    """SPY + VIX daily closes for dual-axis chart. Cached 1 hour."""
    return fetch_vix_history(period=period)


def get_vix_ohlc_df(period: str = "1y") -> pd.DataFrame:
    """VIX daily OHLC for gap table. Cached 1 hour."""
    return fetch_vix_ohlc(period=period)


def get_put_call_ratio(scope: str = "daily") -> dict | None:
    """SPY put/call ratio with sentiment signal. scope: 'daily' | 'monthly' | 'quarterly'."""
    return fetch_put_call_ratio(scope=scope)


def _get_vix_snapshot(period: str = "1y") -> dict:
    """
    VIX stats pre-computed from daily history.

    Returns:
        {
          "df":         DataFrame (SPY + VIX closes, for charting)
          "current":    float
          "prev_close": float
          "change":     float
          "high_52w":   float
          "low_52w":    float
          "avg":        float
          "zone":       "Calm" | "Normal" | "Elevated" | "Extreme Fear"
        }
    Returns an empty dict if data is unavailable.
    """
    df = fetch_vix_history(period=period)
    if df.empty or "VIX" not in df.columns:
        return {}

    vix       = df["VIX"]
    current   = float(vix.iloc[-1])
    prev      = float(vix.iloc[-2]) if len(vix) > 1 else current
    zone      = next(name for threshold, name in _VIX_ZONES if current < threshold)

    return {
        "df":         df,
        "current":    current,
        "prev_close": prev,
        "change":     round(current - prev, 2),
        "high_52w":   round(float(vix.max()), 2),
        "low_52w":    round(float(vix.min()), 2),
        "avg":        round(float(vix.mean()), 2),
        "zone":       zone,
    }


def get_vix_gap_history(period: str = "1y") -> pd.DataFrame:
    """VIX daily gap history computed from OHLC. Empty DataFrame if data unavailable."""
    df = fetch_vix_ohlc(period=period)
    if df.empty:
        return pd.DataFrame()
    return compute_daily_gaps(df)


def get_market_overview() -> dict:
    """
    Single call for all market-wide data needed at page load.

    Returns:
        {
          "indices": DataFrame  (index strip)
          "vix":     dict       (get_vix_snapshot result)
        }
    """
    return {
        "indices": _get_index_snapshot(),
        "vix":     _get_vix_snapshot("1y"),
    }
