"""SPX-universe scanners: candle screener, bounce, squeeze, Munger, analyst consensus."""

import pandas as pd

from stockiq.backend.data.screeners import (
    fetch_spx_bounce_radar_scan,
    fetch_spx_candle_momentum_scan,
    fetch_spx_forward_pe_scan,
    fetch_spx_munger_scan,
    fetch_spx_squeeze_scan,
    fetch_spx_strong_buy_scan,
    fetch_spx_strong_sell_scan,
)


def get_candle_momentum_scan() -> pd.DataFrame:
    """Weekly/monthly candle screener for S&P 500. Cached 1 hour."""
    return fetch_spx_candle_momentum_scan()


def get_bounce_radar_scan(threshold_pct: float = 5.0, top_n: int = 30) -> pd.DataFrame:
    """Stocks within ±threshold_pct of their 200-day MA, sorted by bounce score."""
    return fetch_spx_bounce_radar_scan(threshold_pct, top_n)


def get_squeeze_scan(
    rsi_min: float = 55.0,
    min_short_float: float = 0.5,
    top_n: int = 30,
) -> pd.DataFrame:
    """High-RSI stocks with meaningful short interest, sorted by squeeze score."""
    return fetch_spx_squeeze_scan(rsi_min, min_short_float, top_n)


def get_munger_strategy_scan(
    threshold_pct: float = 15.0,
    min_quality: float = 30.0,
    top_n: int = 30,
) -> pd.DataFrame:
    """Quality companies near their 200-week MA, sorted by Munger score."""
    return fetch_spx_munger_scan(threshold_pct, min_quality, top_n)


def get_strong_buy_scan(
    min_upside: float = 5.0,
    min_analysts: int = 5,
    max_rating: float = 2.5,
    top_n: int = 20,
) -> pd.DataFrame:
    """Analyst buy consensus candidates, sorted by SB score."""
    return fetch_spx_strong_buy_scan(min_upside, min_analysts, max_rating, top_n)


def get_forward_pe_scan(
    top_n: int = 30,
    max_fwd_pe: float = 25.0,
    min_fwd_pe: float = 0.0,
    min_eps_growth: float = 0.0,
) -> pd.DataFrame:
    """Forward P/E value-growth candidates, sorted by VG Score."""
    df = fetch_spx_forward_pe_scan()
    if df.empty:
        return df
    if min_fwd_pe > 0:
        df = df[df["Fwd P/E"].fillna(999) >= min_fwd_pe]
    if max_fwd_pe > 0:
        df = df[df["Fwd P/E"] <= max_fwd_pe]
    if min_eps_growth > 0:
        df = df[df["EPS Gr %"].fillna(-999) >= min_eps_growth]
    return df.head(top_n).reset_index(drop=True)


def get_strong_sell_scan(
    min_downside: float = 0.0,
    min_analysts: int = 1,
    min_rating: float = 2.5,
    top_n: int = 30,
) -> pd.DataFrame:
    """Analyst sell consensus candidates, sorted by SS score."""
    return fetch_spx_strong_sell_scan(min_downside, min_analysts, min_rating, top_n)
