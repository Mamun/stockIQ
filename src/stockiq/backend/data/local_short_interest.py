"""
Local short interest cache.

Fields per ticker: shortPercentOfFloat, shortRatio, sharesShort, sharesShortPriorMonth

Populated by: scripts/build_short_interest_cache.py (run monthly)
Cache file:   cache/screener/short_interest.json
"""

import json
import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent.parent.parent.parent / "cache" / "screener" / "short_interest.json"
_cache: dict | None = None


class ShortInterestData(TypedDict):
    shortPercentOfFloat: float
    shortRatio: float
    sharesShort: int
    sharesShortPriorMonth: int


def get_short_interest() -> dict[str, ShortInterestData]:
    """Return short interest dict from local cache, or empty dict if unavailable."""
    global _cache
    if _cache is not None:
        return _cache

    if not _CACHE_FILE.exists():
        logger.debug("Short interest cache not found at %s — run scripts/build_short_interest_cache.py", _CACHE_FILE)
        return {}

    try:
        _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        logger.info("Loaded short interest: %d tickers from %s", len(_cache), _CACHE_FILE)
    except Exception as exc:
        logger.warning("Failed to load short interest cache (%s)", exc)
        return {}

    return _cache


def invalidate() -> None:
    global _cache
    _cache = None
