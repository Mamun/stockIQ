"""
Build fundamentals cache (Munger-style quality metrics).

Fetches returnOnEquity, profitMargins, revenueGrowth, debtToEquity, earningsGrowth
for every ticker in the SPX universe via yfinance.

Fundamentals update quarterly (earnings cycle) — run this after each earnings season.

Usage (from project root):
    python scripts/build_fundamentals_cache.py

Writes to: cache/screener/fundamentals.json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yfinance as yf

from stockiq.backend.config import SPX_TICKERS  # noqa: E402

_OUTPUT_FILE = Path(__file__).parent.parent / "cache" / "screener" / "fundamentals.json"
_BATCH_SIZE  = 10
_BATCH_PAUSE = 3.0

_FIELDS = [
    "returnOnEquity",
    "profitMargins",
    "revenueGrowth",
    "debtToEquity",
    "earningsGrowth",
]


def fetch_fundamentals(tickers: list[str]) -> dict[str, dict]:
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
    print(f"Building fundamentals cache for {len(tickers)} tickers → {_OUTPUT_FILE}\n")

    data = fetch_fundamentals(tickers)

    with_roe = sum(1 for v in data.values() if v.get("returnOnEquity") is not None)
    print(f"\nFetched: {len(data)} tickers  ({with_roe} with ROE data)")

    _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved → {_OUTPUT_FILE}")
    print("Done. Refresh quarterly after each earnings season.")


if __name__ == "__main__":
    main()
