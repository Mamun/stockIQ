"""
Build and upload ticker metadata cache to GCS.

Fetches company name + sector for every ticker in the SPX universe via yfinance,
then uploads the result as JSON to GCS so the Streamlit app can skip .info calls.

Usage (from project root):
    python scripts/build_metadata_cache.py

Required env var:
    GCS_BUCKET=your-bucket-name

Optional:
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    (not needed when using `gcloud auth application-default login`)

The script uploads to:  gs://<GCS_BUCKET>/screener/ticker_metadata.json
"""

import json
import os
import sys
import time
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

from stockiq.backend.config import SPX_TICKERS  # noqa: E402 — after sys.path patch

_GCS_OBJECT = "screener/ticker_metadata.json"
_BATCH_SIZE = 20       # tickers per yfinance batch
_BATCH_PAUSE = 2.0     # seconds between batches (rate-limit courtesy)


def fetch_metadata(tickers: list[str]) -> dict[str, dict]:
    metadata: dict[str, dict] = {}
    total = len(tickers)

    for i in range(0, total, _BATCH_SIZE):
        batch = tickers[i : i + _BATCH_SIZE]
        print(f"  Fetching batch {i // _BATCH_SIZE + 1} / {-(-total // _BATCH_SIZE)}  ({batch[0]} … {batch[-1]})")

        for ticker in batch:
            try:
                info = yf.Ticker(ticker).info
                name = info.get("longName") or info.get("shortName") or ticker
                sector = info.get("sector") or "—"
                metadata[ticker] = {"name": name, "sector": sector}
            except Exception as exc:
                print(f"    WARNING: {ticker} failed — {exc}")
                metadata[ticker] = {"name": ticker, "sector": "—"}

        if i + _BATCH_SIZE < total:
            time.sleep(_BATCH_PAUSE)

    return metadata


def upload_to_gcs(bucket_name: str, data: dict) -> None:
    from google.cloud import storage

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(_GCS_OBJECT)
    blob.upload_from_string(payload, content_type="application/json")
    print(f"\nUploaded {len(data)} tickers → gs://{bucket_name}/{_GCS_OBJECT}")


def main() -> None:
    bucket_name = os.environ.get("GCS_BUCKET", "").strip()
    if not bucket_name:
        print("ERROR: GCS_BUCKET env var is not set.")
        print("  Add it to your .env file:  GCS_BUCKET=your-bucket-name")
        sys.exit(1)

    tickers = SPX_TICKERS
    print(f"Building metadata cache for {len(tickers)} tickers → gs://{bucket_name}/{_GCS_OBJECT}\n")

    metadata = fetch_metadata(tickers)

    found = sum(1 for v in metadata.values() if v["sector"] != "—")
    print(f"\nFetched: {len(metadata)} tickers  ({found} with sector info)")

    upload_to_gcs(bucket_name, metadata)
    print("Done. Run `streamlit run app.py` — the app will load from GCS on startup.")


if __name__ == "__main__":
    main()
