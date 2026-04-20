import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def search_companies(query: str) -> list[dict]:
    """Return matching companies from Yahoo Finance search."""
    try:
        quotes = yf.Search(query, max_results=10, news_count=0).quotes
        return [
            {
                "symbol":   r.get("symbol", ""),
                "name":     r.get("shortname") or r.get("longname") or r.get("symbol", ""),
                "exchange": r.get("exchange", ""),
                "type":     r.get("quoteType", ""),
            }
            for r in quotes
            if r.get("symbol") and r.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND", "INDEX")
        ]
    except Exception:
        return []


def fetch_ohlcv(ticker: str, period_days: int) -> pd.DataFrame:
    """
    Download OHLCV history for a single ticker.
    Fetches extra history (period_days + 1450) so long-period MAs have enough warmup data.
    Returns a clean DataFrame or raises on failure.
    """
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=period_days + 1450)
    df = yf.download(
        ticker,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


def get_company_name(ticker: str) -> str:
    """Fetch the long company name from yfinance; falls back to ticker on error."""
    try:
        return yf.Ticker(ticker).info.get("longName", ticker)
    except Exception:
        return ticker
