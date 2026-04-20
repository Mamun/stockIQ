"""
GCS-backed analyst consensus cache.

Fields per ticker: recommendationMean, numberOfAnalystOpinions,
                   targetMeanPrice, targetHighPrice, targetLowPrice
Updated weekly (analyst consensus changes slowly) via scripts/build_analyst_consensus_cache.py.

Current price is intentionally NOT cached here — it's fetched live from OHLC batch downloads.

GCS object path: screener/analyst_consensus.json
Schema: {"AAPL": {"recommendationMean": 1.8, "numberOfAnalystOpinions": 42, ...}, ...}
"""

import json
import logging
import os
from typing import TypedDict

logger = logging.getLogger(__name__)

_GCS_OBJECT = "screener/analyst_consensus.json"
_cache: dict | None = None


class AnalystData(TypedDict):
    recommendationMean: float | None
    numberOfAnalystOpinions: int | None
    targetMeanPrice: float | None
    targetHighPrice: float | None
    targetLowPrice: float | None


def get_analyst_consensus() -> dict[str, AnalystData]:
    """Return analyst consensus dict from GCS, or empty dict if unavailable."""
    global _cache
    if _cache is not None:
        return _cache

    bucket_name = os.environ.get("GCS_BUCKET", "").strip()
    if not bucket_name:
        logger.debug("GCS_BUCKET not set — analyst consensus cache unavailable")
        return {}

    try:
        from google.cloud import storage

        client = storage.Client()
        blob   = client.bucket(bucket_name).blob(_GCS_OBJECT)

        if not blob.exists():
            logger.warning("GCS analyst consensus not found at gs://%s/%s", bucket_name, _GCS_OBJECT)
            return {}

        _cache = json.loads(blob.download_as_text(encoding="utf-8"))
        logger.info("Loaded GCS analyst consensus: %d tickers from gs://%s/%s",
                    len(_cache), bucket_name, _GCS_OBJECT)
    except Exception as exc:
        logger.warning("Failed to load GCS analyst consensus (%s) — will retry next call", exc)
        return {}  # don't set _cache so the next call retries

    return _cache


def invalidate() -> None:
    global _cache
    _cache = None
