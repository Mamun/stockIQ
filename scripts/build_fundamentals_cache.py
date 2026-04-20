"""
Build and upload fundamentals cache to GCS (Munger-style quality metrics).

Fetches returnOnEquity, profitMargins, revenueGrowth, debtToEquity, earningsGrowth
for every ticker in the SPX universe via yfinance, then uploads as JSON to GCS.

Fundamentals update quarterly (earnings cycle), so run this after each earnings season.

Usage (from project root):
    python scripts/build_fundamentals_cache.py

Required env var:
    GCS_BUCKET=your-bucket-name

Uploads to: gs://<GCS_BUCKET>/screener/fundamentals.json
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

from stockiq.backend.config import SPX_TICKERS  # noqa: E402

_GCS_OBJECT  = "screener/fundamentals.json"
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


def upload_to_gcs(bucket_name: str, data: dict) -> None:
    from google.cloud import storage

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    client  = storage.Client()
    blob    = client.bucket(bucket_name).blob(_GCS_OBJECT)
    blob.upload_from_string(payload, content_type="application/json")
    print(f"\nUploaded {len(data)} tickers → gs://{bucket_name}/{_GCS_OBJECT}")


def main() -> None:
    bucket_name = os.environ.get("GCS_BUCKET", "").strip()
    if not bucket_name:
        print("ERROR: GCS_BUCKET env var is not set.")
        sys.exit(1)

    tickers = SPX_TICKERS
    print(f"Building fundamentals cache for {len(tickers)} tickers → gs://{bucket_name}/{_GCS_OBJECT}\n")

    data = fetch_fundamentals(tickers)

    with_roe = sum(1 for v in data.values() if v.get("returnOnEquity") is not None)
    print(f"\nFetched: {len(data)} tickers  ({with_roe} with ROE data)")

    upload_to_gcs(bucket_name, data)
    print("Done. Refresh quarterly after each earnings season.")


if __name__ == "__main__":
    main()
