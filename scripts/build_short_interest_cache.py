"""
Build short interest cache.

Fetches shortPercentOfFloat, shortRatio, sharesShort, sharesShortPriorMonth
for every ticker in the SPX universe via yfinance.

Short interest data updates monthly (SEC reporting) — run this monthly.

Usage (from project root):
    python scripts/build_short_interest_cache.py

Writes to: cache/screener/short_interest.json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yfinance as yf

from stockiq.backend.config import SPX_TICKERS  # noqa: E402

_OUTPUT_FILE = Path(__file__).parent.parent / "cache" / "screener" / "short_interest.json"
_BATCH_SIZE  = 10
_BATCH_PAUSE = 3.0


def fetch_short_interest(tickers: list[str]) -> dict[str, dict]:
    data: dict[str, dict] = {}
    total = len(tickers)

    for i in range(0, total, _BATCH_SIZE):
        batch = tickers[i : i + _BATCH_SIZE]
        print(f"  Fetching batch {i // _BATCH_SIZE + 1} / {-(-total // _BATCH_SIZE)}"
              f"  ({batch[0]} … {batch[-1]})")

        for ticker in batch:
            try:
                info = yf.Ticker(ticker).info
                data[ticker] = {
                    "shortPercentOfFloat":   float(info.get("shortPercentOfFloat")   or 0.0),
                    "shortRatio":            float(info.get("shortRatio")             or 0.0),
                    "sharesShort":           int(  info.get("sharesShort")            or 0),
                    "sharesShortPriorMonth": int(  info.get("sharesShortPriorMonth")  or 0),
                }
            except Exception as exc:
                print(f"    WARNING: {ticker} failed — {exc}")
                data[ticker] = {
                    "shortPercentOfFloat": 0.0,
                    "shortRatio": 0.0,
                    "sharesShort": 0,
                    "sharesShortPriorMonth": 0,
                }

        if i + _BATCH_SIZE < total:
            time.sleep(_BATCH_PAUSE)

    return data


def main() -> None:
    tickers = SPX_TICKERS
    print(f"Building short interest cache for {len(tickers)} tickers → {_OUTPUT_FILE}\n")

    data = fetch_short_interest(tickers)

    with_data = sum(1 for v in data.values() if v["shortPercentOfFloat"] > 0)
    print(f"\nFetched: {len(data)} tickers  ({with_data} with short interest data)")

    _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved → {_OUTPUT_FILE}")
    print("Done. Refresh monthly to keep short interest data current.")


if __name__ == "__main__":
    main()
