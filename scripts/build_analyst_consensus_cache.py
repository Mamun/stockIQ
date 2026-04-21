"""
Build analyst consensus cache.

Fetches recommendationMean, numberOfAnalystOpinions, targetMeanPrice,
targetHighPrice, targetLowPrice for every SPX ticker via yfinance.

Analyst consensus updates weekly — run this once a week.
Current price is intentionally excluded; it's fetched live in the app.

Usage (from project root):
    python scripts/build_analyst_consensus_cache.py

Writes to: cache/screener/analyst_consensus.json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yfinance as yf

from stockiq.backend.config import SPX_TICKERS  # noqa: E402

_OUTPUT_FILE = Path(__file__).parent.parent / "cache" / "screener" / "analyst_consensus.json"
_BATCH_SIZE  = 10
_BATCH_PAUSE = 3.0

_FIELDS = [
    "recommendationMean",
    "numberOfAnalystOpinions",
    "targetMeanPrice",
    "targetHighPrice",
    "targetLowPrice",
]


def fetch_analyst_consensus(tickers: list[str]) -> dict[str, dict]:
    data: dict[str, dict] = {}
    total = len(tickers)

    for i in range(0, total, _BATCH_SIZE):
        batch = tickers[i : i + _BATCH_SIZE]
        print(f"  Fetching batch {i // _BATCH_SIZE + 1} / {-(-total // _BATCH_SIZE)}"
              f"  ({batch[0]} … {batch[-1]})")

        for ticker in batch:
            try:
                info = yf.Ticker(ticker).info
                data[ticker] = {field: info.get(field) for field in _FIELDS}
            except Exception as exc:
                print(f"    WARNING: {ticker} failed — {exc}")
                data[ticker] = {field: None for field in _FIELDS}

        if i + _BATCH_SIZE < total:
            time.sleep(_BATCH_PAUSE)

    return data


def main() -> None:
    tickers = SPX_TICKERS
    print(f"Building analyst consensus cache for {len(tickers)} tickers → {_OUTPUT_FILE}\n")

    data = fetch_analyst_consensus(tickers)

    with_rating = sum(1 for v in data.values() if v.get("recommendationMean") is not None)
    print(f"\nFetched: {len(data)} tickers  ({with_rating} with analyst ratings)")

    _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved → {_OUTPUT_FILE}")
    print("Done. Refresh weekly — analyst consensus changes slowly.")


if __name__ == "__main__":
    main()
