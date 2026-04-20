"""SPY-specific data assembly service."""

import pandas as pd

from stockiq.backend.data.yf_fetch import fetch_ohlcv
from stockiq.backend.data.local_gap_cache import apply_gap_cache, save_confirmed_gaps
from stockiq.backend.data.market import fetch_spx_intraday, fetch_spx_quote
from stockiq.backend.data.local_ohlc_cache import enrich_with_cache
from stockiq.backend.models.indicators import compute_daily_gaps, compute_rsi, patch_today_gap


def get_spy_quote() -> dict:
    """Live SPY price, change, high/low, volume. Cached 60 s."""
    return fetch_spx_quote()


def _get_spy_daily_df() -> pd.DataFrame:
    """Enriched 1-year daily SPY OHLCV (local-cache-filled). Cached 120 s."""
    return enrich_with_cache(fetch_spx_intraday(period="1y", interval="1d"), "SPY")


def get_spy_chart_df(period: str, interval: str) -> pd.DataFrame:
    """SPY OHLCV + RSI for any period/interval combination (chart display). Cached 120 s."""
    df = fetch_spx_intraday(period=period, interval=interval)
    if not df.empty:
        df = df.copy()
        df["RSI"] = compute_rsi(df)
    return df


def _get_spy_long_rsi() -> pd.Series:
    spy_long_df = fetch_ohlcv("SPY", 365)
    rsi = compute_rsi(spy_long_df)
    return rsi[~spy_long_df.index.duplicated(keep="last")]


def get_spy_gap_table_data() -> dict:
    """
    Fully assembled SPY gap table data.

    Returns:
        {
          "gaps_df":  DataFrame with Gap, RSI, Next Day columns
          "quote":    live quote dict
          "daily_df": enriched 1Y daily df (for AI forecast context)
        }
    """
    daily_df = _get_spy_daily_df()
    quote    = get_spy_quote()
    rsi_long = _get_spy_long_rsi()

    gaps_df = apply_gap_cache(patch_today_gap(compute_daily_gaps(daily_df), quote))
    save_confirmed_gaps(gaps_df)

    if not gaps_df.empty:
        last = gaps_df.index[-1]
        if quote.get("price"):
            gaps_df.at[last, "Close"] = round(float(quote["price"]), 2)
        if quote.get("day_high"):
            gaps_df.at[last, "High"] = round(float(quote["day_high"]), 2)
        if quote.get("day_low"):
            gaps_df.at[last, "Low"] = round(float(quote["day_low"]), 2)

    gaps_df["Next Close"] = gaps_df["Close"].shift(-1)
    gaps_df["Next Day"] = gaps_df.apply(
        lambda r: "▲" if (pd.notna(r["Next Close"]) and r["Next Close"] > r["Close"])
                  else ("▼" if (pd.notna(r["Next Close"]) and r["Next Close"] < r["Close"])
                  else "—"),
        axis=1,
    )

    gaps_df["RSI"] = rsi_long.reindex(gaps_df.index)

    return {"gaps_df": gaps_df, "quote": quote, "daily_df": daily_df}
