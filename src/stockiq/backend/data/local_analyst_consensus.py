"""
Local analyst consensus cache.

Fields per ticker: recommendationMean, numberOfAnalystOpinions,
                   targetMeanPrice, targetHighPrice, targetLowPrice

Populated by: scripts/build_analyst_consensus_cache.py (run weekly)
Cache file:   cache/screener/analyst_consensus.json
"""

import json
import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent.parent.parent.parent / "cache" / "screener" / "analyst_consensus.json"
_cache: dict | None = None


class AnalystData(TypedDict):
    recommendationMean: float | None
    numberOfAnalystOpinions: int | None
    targetMeanPrice: float | None
    targetHighPrice: float | None
    targetLowPrice: float | None


def get_analyst_consensus() -> dict[str, AnalystData]:
    """Return analyst consensus dict from local cache, or empty dict if unavailable."""
    global _cache
    if _cache is not None:
        return _cache

    if not _CACHE_FILE.exists():
        logger.debug("Analyst consensus cache not found at %s — run scripts/build_analyst_consensus_cache.py", _CACHE_FILE)
        return {}

    try:
        _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        logger.info("Loaded analyst consensus: %d tickers from %s", len(_cache), _CACHE_FILE)
    except Exception as exc:
        logger.warning("Failed to load analyst consensus cache (%s)", exc)
        return {}

    return _cache


def invalidate() -> None:
    global _cache
    _cache = None
