"""
Local JSON cache for confirmed daily gap fill results.

Yahoo's daily OHLC often lacks enough future bars to confirm gaps for the most
recent 2-3 trading days (e.g. after a market holiday).  Once a gap date has 3
trading sessions of data after it, its fill status is permanent — we cache it
so the table never regresses to ⏳ Pending on a later load.

Cache location: ~/.stockiq/gap_cache.json
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

_CACHE_FILE = Path.home() / ".stockiq" / "gap_cache.json"
_KEEP_DAYS  = 30


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


def _prune(entries: dict) -> dict:
    cutoff = (date.today() - timedelta(days=_KEEP_DAYS)).isoformat()
    return {k: v for k, v in entries.items() if k >= cutoff}


def save_confirmed_gaps(gaps_df: pd.DataFrame, ticker: str = "SPY") -> None:
    """Persist confirmed rows to cache and drop anything older than 30 days."""
    raw = _load_raw()
    entries = raw.get(ticker, {})

    for idx, row in gaps_df.iterrows():
        if row.get("Gap Confirmed", False):
            entries[idx.strftime("%Y-%m-%d")] = {
                "gap_filled":    bool(row["Gap Filled"]),
                "gap_confirmed": True,
            }

    raw[ticker] = _prune(entries)
    _save_raw(raw)


def apply_gap_cache(gaps_df: pd.DataFrame, ticker: str = "SPY") -> pd.DataFrame:
    """Override ⏳ Pending rows with cached confirmed results, if available."""
    raw = _load_raw()
    entries = raw.get(ticker, {})
    if not entries:
        return gaps_df

    gaps_df = gaps_df.copy()
    for idx, row in gaps_df.iterrows():
        if not row.get("Gap Confirmed", True):
            date_str = idx.strftime("%Y-%m-%d")
            cached = entries.get(date_str)
            if cached and cached.get("gap_confirmed"):
                gaps_df.at[idx, "Gap Filled"]    = cached["gap_filled"]
                gaps_df.at[idx, "Gap Confirmed"]  = True

    return gaps_df
