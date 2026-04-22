"""SPY-specific data assembly service."""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from stockiq.backend.config import OPTIONS_SPY_PROVIDERS, QUOTE_SPY_PROVIDERS
from stockiq.backend.data.spy import (
    fetch_put_call_ratio,
    fetch_put_call_ratio_cboe,
    fetch_spx_intraday,
    fetch_spx_quote,
    fetch_spx_quote_cboe,
    fetch_spy_options_data,
    fetch_spy_options_data_cboe,
)
from stockiq.backend.data.local_gap_cache import apply_gap_cache, save_confirmed_gaps
from stockiq.backend.data.local_ohlc_cache import enrich_with_cache
from stockiq.backend.data.yf_fetch import fetch_ohlcv
from stockiq.backend.models.indicators import compute_daily_gaps, compute_rsi, patch_today_gap
from stockiq.backend.models.options import (
    compute_max_pain, compute_oi_by_strike, label_expirations,
    compute_gex, compute_expected_move,
)

_QUOTE_FETCHERS = {
    "yahoo": fetch_spx_quote,
    "cboe":  fetch_spx_quote_cboe,
}
_OPTIONS_CHAIN_FETCHERS = {
    "yahoo": fetch_spy_options_data,
    "cboe":  fetch_spy_options_data_cboe,
}
_PCR_FETCHERS = {
    "yahoo": fetch_put_call_ratio,
    "cboe":  fetch_put_call_ratio_cboe,
}


def get_spy_quote() -> dict:
    """
    Live SPY quote — fetches all configured providers in parallel, returns the freshest result.
    Freshness is determined by the _ts (Unix timestamp) field each fetcher includes.
    Falls back to any non-empty result when timestamps are unavailable.
    """
    fetchers = [_QUOTE_FETCHERS[p] for p in QUOTE_SPY_PROVIDERS if p in _QUOTE_FETCHERS]
    if not fetchers:
        return {}

    results: list[dict] = []
    pool = ThreadPoolExecutor(max_workers=len(fetchers))
    try:
        futures = {pool.submit(f): f for f in fetchers}
        try:
            for future in as_completed(futures, timeout=12):
                try:
                    r = future.result()
                    if r.get("price", 0) > 0:
                        results.append(r)
                except Exception:
                    pass
        except TimeoutError:
            pass  # use whatever results arrived before timeout
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    if not results:
        return {}
    return max(results, key=lambda r: r.get("_ts", 0))


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


def get_put_call_ratio(scope: str = "daily") -> dict | None:
    """SPY put/call ratio with sentiment signal. scope: 'daily' | '7d' | '14d' | '21d' | 'monthly'."""
    for provider in OPTIONS_SPY_PROVIDERS:
        fetcher = _PCR_FETCHERS.get(provider)
        if fetcher:
            result = fetcher(scope=scope)
            if result and result.get("puts", 0) > 0 and result.get("calls", 0) > 0:
                return result
    return None


def get_spy_options_analysis(
    expiration: str = "",
    current_price: float = 0.0,
) -> dict | None:
    """
    Max pain + OI-by-strike for one SPY expiration.

    Returns:
        {
          "max_pain":    float         — strike where total OI dollar pain is minimised
          "oi_df":       DataFrame     — columns: strike, call_oi, put_oi (30 strikes around price)
          "expiration":  str           — ISO date used
          "expirations": list[str]     — all available ISO dates
          "exp_labels":  list[str]     — human-readable labels e.g. "Apr 25 (5d)"
        }
    or None if options data is unavailable.
    """
    def _has_oi(d: dict) -> bool:
        return bool(d) and (
            int(d["calls"]["openInterest"].sum()) + int(d["puts"]["openInterest"].sum()) > 0
        )

    data = None
    for provider in OPTIONS_SPY_PROVIDERS:
        fetcher = _OPTIONS_CHAIN_FETCHERS.get(provider)
        if fetcher:
            candidate = fetcher(expiration=expiration)
            if _has_oi(candidate):
                data = candidate
                break
    if not data:
        return None

    max_pain      = compute_max_pain(data["calls"], data["puts"])
    oi_df         = compute_oi_by_strike(data["calls"], data["puts"], current_price or max_pain)
    gex_df        = compute_gex(data["calls"], data["puts"], current_price or max_pain, data["expiration"])
    expected_move = compute_expected_move(data["calls"], data["puts"], current_price or max_pain)

    return {
        "max_pain":      max_pain,
        "oi_df":         oi_df,
        "gex_df":        gex_df,
        "expected_move": expected_move,
        "expiration":    data["expiration"],
        "expirations":   data["expirations"],
        "exp_labels":    label_expirations(data["expirations"]),
    }
