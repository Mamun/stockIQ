"""
Build ticker metadata cache (company name + sector).

Fetches longName and sector for every ticker in the SPX universe via yfinance.

Usage (from project root):
    python scripts/build_metadata_cache.py

Writes to: cache/screener/ticker_metadata.json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yfinance as yf

from stockiq.backend.config import SPX_TICKERS  # noqa: E402

_OUTPUT_FILE = Path(__file__).parent.parent / "cache" / "screener" / "ticker_metadata.json"
_BATCH_SIZE  = 20
_BATCH_PAUSE = 2.0


def fetch_metadata(tickers: list[str]) -> dict[str, dict]:
    metadata: dict[str, dict] = {}
    total = len(tickers)

    for i in range(0, total, _BATCH_SIZE):
        batch = tickers[i : i + _BATCH_SIZE]
        print(f"  Fetching batch {i // _BATCH_SIZE + 1} / {-(-total // _BATCH_SIZE)}  ({batch[0]} … {batch[-1]})")

        for ticker in batch:
            try:
                info   = yf.Ticker(ticker).info
                name   = info.get("longName") or info.get("shortName") or ticker
                sector = info.get("sector") or "—"
                metadata[ticker] = {"name": name, "sector": sector}
            except Exception as exc:
                print(f"    WARNING: {ticker} failed — {exc}")
                metadata[ticker] = {"name": ticker, "sector": "—"}

        if i + _BATCH_SIZE < total:
            time.sleep(_BATCH_PAUSE)

    return metadata


def main() -> None:
    tickers = SPX_TICKERS
    print(f"Building metadata cache for {len(tickers)} tickers → {_OUTPUT_FILE}\n")

    metadata = fetch_metadata(tickers)

    found = sum(1 for v in metadata.values() if v["sector"] != "—")
    print(f"\nFetched: {len(metadata)} tickers  ({found} with sector info)")

    _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_FILE.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved → {_OUTPUT_FILE}")
    print("Done. Run `streamlit run app.py` — the app will load from the local cache on startup.")


if __name__ == "__main__":
    main()
