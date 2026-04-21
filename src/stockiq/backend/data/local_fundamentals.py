"""
Local fundamentals cache (Munger-style quality metrics).

Fields per ticker: returnOnEquity, profitMargins, revenueGrowth, debtToEquity, earningsGrowth

Populated by: scripts/build_fundamentals_cache.py (run quarterly after earnings)
Cache file:   cache/screener/fundamentals.json
"""

import json
import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent.parent.parent.parent / "cache" / "screener" / "fundamentals.json"
_cache: dict | None = None


class FundamentalsData(TypedDict):
    returnOnEquity: float | None
    profitMargins: float | None
    revenueGrowth: float | None
    debtToEquity: float | None
    earningsGrowth: float | None


def get_fundamentals() -> dict[str, FundamentalsData]:
    """Return fundamentals dict from local cache, or empty dict if unavailable."""
    global _cache
    if _cache is not None:
        return _cache

    if not _CACHE_FILE.exists():
        logger.debug("Fundamentals cache not found at %s — run scripts/build_fundamentals_cache.py", _CACHE_FILE)
        return {}

    try:
        _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        logger.info("Loaded fundamentals: %d tickers from %s", len(_cache), _CACHE_FILE)
    except Exception as exc:
        logger.warning("Failed to load fundamentals cache (%s)", exc)
        return {}

    return _cache


def invalidate() -> None:
    global _cache
    _cache = None
