"""Single-stock analysis service."""

import pandas as pd

from stockiq.backend.data.yf_fetch import fetch_ohlcv, get_company_name, search_companies
from stockiq.backend.models.indicators import (
    compute_buying_pressure,
    compute_daily_gaps,
    compute_fibonacci,
    compute_mas,
    compute_rsi,
    compute_weekly_ma200,
    detect_reversal_patterns,
    patch_today_gap,
)
from stockiq.backend.models.signals import find_crosses, overall_signal, signal_score


def search_stocks(query: str) -> list[dict]:
    """Yahoo Finance company search. Returns list of {symbol, name, exchange, type}."""
    return search_companies(query)


def get_stock_df(ticker: str) -> pd.DataFrame:
    """
    5-year OHLCV with all indicators pre-computed (MAs, weekly MA200, RSI, patterns).
    Raises on fetch failure; returns empty DataFrame if no data.
    """
    raw = fetch_ohlcv(ticker, 1825)
    if raw.empty:
        return raw
    df = compute_mas(raw)
    df["MA200W"] = compute_weekly_ma200(df)
    df["RSI"]    = compute_rsi(df)
    df           = detect_reversal_patterns(df)
    return df


def get_stock_signal(df: pd.DataFrame) -> dict:
    """
    Compute buy/sell signal from the latest two rows of a pre-computed indicator df.

    Returns:
        {score, label, color, reasons, latest (Series), prev (Series)}
    """
    latest = df.iloc[-1]
    prev   = df.iloc[-2]
    score, reasons = signal_score(latest, prev)
    label, color   = overall_signal(score)
    return {
        "score":   score,
        "label":   label,
        "color":   color,
        "reasons": reasons,
        "latest":  latest,
        "prev":    prev,
    }


def get_stock_fibonacci(df: pd.DataFrame) -> dict:
    """Fibonacci retracement levels for the given OHLCV DataFrame."""
    return compute_fibonacci(df)


def get_stock_gaps(df: pd.DataFrame, quote: dict) -> pd.DataFrame:
    """Daily gap history with today's gap patched from a live quote dict."""
    return patch_today_gap(compute_daily_gaps(df), quote)


def get_stock_crosses(df: pd.DataFrame) -> tuple:
    """Golden-cross and death-cross dates for the given indicator DataFrame."""
    return find_crosses(df)


def get_buying_pressure(df: pd.DataFrame, timeframe: str = "monthly") -> dict:
    """BX signal for the given timeframe: 'monthly' | 'weekly' | 'daily'."""
    return compute_buying_pressure(df, timeframe)


def get_company_display_name(ticker: str) -> str:
    """Fetch long company name; falls back to ticker on error."""
    return get_company_name(ticker)
