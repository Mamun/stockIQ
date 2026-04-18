"""
Local JSON cache for recent daily OHLC bars.

Historical bars (any date before today) are immutable — caching them means
Yahoo's occasional gaps in the last 2-3 trading days never cause ⏳ Pending
status in the gap table, and the gap algorithm always has enough future bars
to confirm fill status.

Cache location : ~/.stockiq/ohlc_cache.json
Retention      : 45 trading days (30 display rows + 14 RSI warmup + buffer)
Today's bar    : never cached — still mutable while the market is open
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

_CACHE_FILE = Path.home() / ".stockiq" / "ohlc_cache.json"
_KEEP_DAYS  = 45
_OHLC_COLS  = ["Open", "High", "Low", "Close", "Volume"]


# ── low-level I/O ──────────────────────────────────────────────────────────────

def _load_raw() -> dict:
    if not _CACHE_FILE.exists():
        return {}
    try:
        return json.loads(_CACHE_FILE.read_text())
    except Exception:
        return {}


def _save_raw(data: dict) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(data, indent=2))


# ── public API ─────────────────────────────────────────────────────────────────

def load_ohlc_cache(ticker: str) -> pd.DataFrame:
    """Return cached OHLC as a DatetimeIndex DataFrame, or empty DataFrame."""
    raw = _load_raw()
    entries = raw.get(ticker, {})
    if not entries:
        return pd.DataFrame()

    rows = []
    for date_str, vals in entries.items():
        row = {"Date": pd.Timestamp(date_str)}
        row.update(vals)
        rows.append(row)

    df = pd.DataFrame(rows).set_index("Date").sort_index()
    df.index = pd.DatetimeIndex(df.index)
    return df


def _save_ohlc_rows(df: pd.DataFrame, ticker: str) -> None:
    """Write non-today rows from df into the cache, then prune to _KEEP_DAYS."""
    raw     = _load_raw()
    entries = raw.get(ticker, {})
    today   = date.today().isoformat()
    cutoff  = (date.today() - timedelta(days=_KEEP_DAYS)).isoformat()

    for idx, row in df.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        if date_str >= today:
            continue                       # today's bar is still mutable
        available = {c: float(row[c]) for c in _OHLC_COLS if c in row and pd.notna(row[c])}
        if available:
            entries[date_str] = available

    # prune entries older than _KEEP_DAYS
    raw[ticker] = {k: v for k, v in entries.items() if k >= cutoff}
    _save_raw(raw)


def enrich_with_cache(yahoo_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    1. Save yesterday-and-older rows from yahoo_df to the local cache.
    2. Load the cache and add any dates that Yahoo omitted (within the last
       _KEEP_DAYS days) back into the returned DataFrame.

    Returns a sorted DataFrame that is a superset of yahoo_df.
    """
    if yahoo_df.empty:
        return load_ohlc_cache(ticker)   # full fallback to cache

    _save_ohlc_rows(yahoo_df, ticker)

    cached_df = load_ohlc_cache(ticker)
    if cached_df.empty:
        return yahoo_df

    # Find dates the cache has that Yahoo dropped
    yahoo_dates  = set(yahoo_df.index.normalize())
    cached_dates = set(cached_df.index.normalize())
    missing      = cached_dates - yahoo_dates

    if not missing:
        return yahoo_df

    # Only restore dates within the retention window and before today
    today   = pd.Timestamp(date.today())
    cutoff  = today - pd.Timedelta(days=_KEEP_DAYS)
    restore = cached_df[
        cached_df.index.normalize().isin(missing) &
        (cached_df.index < today) &
        (cached_df.index >= cutoff)
    ]

    if restore.empty:
        return yahoo_df

    # Align columns — restore only the columns present in yahoo_df
    common_cols = [c for c in yahoo_df.columns if c in restore.columns]
    merged = pd.concat([yahoo_df, restore[common_cols]]).sort_index()
    return merged[~merged.index.duplicated(keep="last")]
