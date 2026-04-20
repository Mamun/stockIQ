"""
GCS-backed short interest cache.

Fields per ticker: shortPercentOfFloat, shortRatio, sharesShort, sharesShortPriorMonth
Updated monthly (SEC reporting cycle) via scripts/build_short_interest_cache.py.

GCS object path: screener/short_interest.json
Schema: {"AAPL": {"shortPercentOfFloat": 0.005, "shortRatio": 1.2, ...}, ...}
"""

import json
import logging
import os
from typing import TypedDict

logger = logging.getLogger(__name__)

_GCS_OBJECT = "screener/short_interest.json"
_cache: dict | None = None


class ShortInterestData(TypedDict):
    shortPercentOfFloat: float
    shortRatio: float
    sharesShort: int
    sharesShortPriorMonth: int


def get_short_interest() -> dict[str, ShortInterestData]:
    """Return short interest dict from GCS, or empty dict if unavailable."""
    global _cache
    if _cache is not None:
        return _cache

    bucket_name = os.environ.get("GCS_BUCKET", "").strip()
    if not bucket_name:
        logger.debug("GCS_BUCKET not set — short interest cache unavailable")
        return {}

    try:
        from google.cloud import storage

        client = storage.Client()
        blob   = client.bucket(bucket_name).blob(_GCS_OBJECT)

        if not blob.exists():
            logger.warning("GCS short interest not found at gs://%s/%s", bucket_name, _GCS_OBJECT)
            return {}

        _cache = json.loads(blob.download_as_text(encoding="utf-8"))
        logger.info("Loaded GCS short interest: %d tickers from gs://%s/%s",
                    len(_cache), bucket_name, _GCS_OBJECT)
    except Exception as exc:
        logger.warning("Failed to load GCS short interest (%s) — will retry next call", exc)
        return {}  # don't set _cache so the next call retries

    return _cache


def invalidate() -> None:
    global _cache
    _cache = None
