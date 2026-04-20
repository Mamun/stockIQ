"""Shared utilities used across all screener modules."""

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from stockiq.backend.cache import ttl_cache
from stockiq.backend.config import CACHE_TTL, NASDAQ_100_TICKERS, SPX_TICKERS
from stockiq.backend.models.indicators import compute_rsi
from stockiq.backend.data.gcs_ticker_names import get_metadata
from stockiq.backend.data.gcs_short_interest import get_short_interest
from stockiq.backend.data.gcs_ticker_fundamentals import get_fundamentals
from stockiq.backend.data.gcs_analyst_consensus import get_analyst_consensus

logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)


def _batch_download(tickers: list[str], **kwargs) -> pd.DataFrame:
    """
    Wrapper around yf.download with partial-fail logging.
    Returns empty DataFrame on total failure; logs missing tickers on partial failure.
    """
    try:
        raw = yf.download(tickers, **kwargs)
        if raw.empty:
            logger.warning("yf.download returned empty for %d tickers", len(tickers))
        else:
            if isinstance(raw.columns, pd.MultiIndex) and "Close" in raw.columns.get_level_values(0):
                available = set(raw["Close"].columns[raw["Close"].notna().any()])
                missing   = set(tickers) - available
                if missing:
                    logger.warning("yf.download missing data for: %s", sorted(missing))
        return raw
    except Exception as exc:
        logger.warning("yf.download failed (%s) for %d tickers", exc, len(tickers))
        return pd.DataFrame()


def _rsi_last(df: pd.DataFrame) -> float:
    """Return the latest RSI-14 value for a DataFrame with a Close column."""
    return float(compute_rsi(df).iloc[-1])


_NASDAQ_COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon",
    "META": "Meta Platforms", "GOOGL": "Alphabet A", "GOOG": "Alphabet C",
    "TSLA": "Tesla", "AVGO": "Broadcom", "COST": "Costco", "NFLX": "Netflix",
    "AMD": "Advanced Micro Devices", "ADBE": "Adobe", "QCOM": "Qualcomm",
    "TXN": "Texas Instruments", "CSCO": "Cisco", "INTU": "Intuit",
    "AMGN": "Amgen", "ISRG": "Intuitive Surgical", "CMCSA": "Comcast",
    "REGN": "Regeneron", "VRTX": "Vertex Pharma", "MDLZ": "Mondelez",
    "GILD": "Gilead Sciences", "MU": "Micron Technology", "LRCX": "Lam Research",
    "KLAC": "KLA Corp", "AMAT": "Applied Materials", "PANW": "Palo Alto Networks",
    "SNPS": "Synopsys", "CDNS": "Cadence Design", "ADI": "Analog Devices",
    "MRVL": "Marvell Technology", "ASML": "ASML Holding", "MELI": "MercadoLibre",
    "ADP": "Automatic Data Processing", "PYPL": "PayPal", "WDAY": "Workday",
    "DDOG": "Datadog", "CRWD": "CrowdStrike", "ZS": "Zscaler", "FTNT": "Fortinet",
    "MNST": "Monster Beverage", "ROST": "Ross Stores", "AEP": "American Electric Power",
    "IDXX": "IDEXX Laboratories", "PCAR": "PACCAR", "EXC": "Exelon",
    "GEHC": "GE HealthCare", "ODFL": "Old Dominion Freight", "FAST": "Fastenal",
    "VRSK": "Verisk Analytics", "CTSH": "Cognizant", "DLTR": "Dollar Tree",
    "EA": "Electronic Arts", "ALGN": "Align Technology", "ANSS": "ANSYS",
    "TEAM": "Atlassian", "NXPI": "NXP Semiconductors", "PAYX": "Paychex",
    "CHTR": "Charter Communications", "CPRT": "Copart", "CTAS": "Cintas",
    "LULU": "Lululemon", "BKNG": "Booking Holdings", "KHC": "Kraft Heinz",
    "CEG": "Constellation Energy", "DXCM": "Dexcom", "MRNA": "Moderna",
    "TTD": "The Trade Desk", "NDAQ": "Nasdaq Inc", "INTC": "Intel",
    "SBUX": "Starbucks", "MAR": "Marriott", "ORLY": "O'Reilly Auto",
    "KDP": "Keurig Dr Pepper", "FANG": "Diamondback Energy", "ON": "ON Semiconductor",
    "BIIB": "Biogen", "OKTA": "Okta", "WBD": "Warner Bros Discovery",
    "ABNB": "Airbnb", "ENPH": "Enphase Energy", "FSLR": "First Solar",
    "TTWO": "Take-Two Interactive", "EBAY": "eBay", "ILMN": "Illumina",
    "ZM": "Zoom Video", "FISV": "Fiserv", "SMCI": "Super Micro Computer",
    "HON": "Honeywell", "PDD": "PDD Holdings", "JD": "JD.com",
    "SIRI": "Sirius XM", "MTCH": "Match Group", "GFS": "GlobalFoundries",
    "RIVN": "Rivian", "LCID": "Lucid Group", "MSTR": "MicroStrategy", "ARM": "Arm Holdings",
}

ETF_UNIVERSE: list[dict] = [
    {"ticker": "SPY",  "name": "S&P 500",              "category": "Retail Favorites"},
    {"ticker": "QQQ",  "name": "NASDAQ-100",            "category": "Retail Favorites"},
    {"ticker": "TQQQ", "name": "3× NASDAQ (Bull)",      "category": "Retail Favorites"},
    {"ticker": "SQQQ", "name": "3× NASDAQ (Bear)",      "category": "Retail Favorites"},
    {"ticker": "SPXL", "name": "3× S&P 500 (Bull)",     "category": "Retail Favorites"},
    {"ticker": "SOXL", "name": "3× Semiconductors",     "category": "Retail Favorites"},
    {"ticker": "ARKK", "name": "ARK Innovation",        "category": "Retail Favorites"},
    {"ticker": "ARKG", "name": "ARK Genomics",          "category": "Retail Favorites"},
    {"ticker": "VXX",  "name": "VIX Short-Term Futures","category": "Retail Favorites"},
    {"ticker": "UVXY", "name": "1.5× VIX Futures",      "category": "Retail Favorites"},
    {"ticker": "JETS", "name": "Airlines",              "category": "Retail Favorites"},
    {"ticker": "MSOS", "name": "Cannabis",              "category": "Retail Favorites"},
    {"ticker": "IWM",  "name": "Russell 2000",          "category": "Retail Favorites"},
    {"ticker": "SPY",  "name": "S&P 500",            "category": "Broad Market"},
    {"ticker": "QQQ",  "name": "NASDAQ-100",          "category": "Broad Market"},
    {"ticker": "IWM",  "name": "Russell 2000",        "category": "Broad Market"},
    {"ticker": "DIA",  "name": "Dow Jones",           "category": "Broad Market"},
    {"ticker": "VTI",  "name": "Total US Market",     "category": "Broad Market"},
    {"ticker": "VOO",  "name": "Vanguard S&P 500",    "category": "Broad Market"},
    {"ticker": "XLK",  "name": "Technology",          "category": "Sector"},
    {"ticker": "XLF",  "name": "Financials",          "category": "Sector"},
    {"ticker": "XLE",  "name": "Energy",              "category": "Sector"},
    {"ticker": "XLV",  "name": "Health Care",         "category": "Sector"},
    {"ticker": "XLC",  "name": "Communication Svcs",  "category": "Sector"},
    {"ticker": "XLY",  "name": "Consumer Discret.",   "category": "Sector"},
    {"ticker": "XLP",  "name": "Consumer Staples",    "category": "Sector"},
    {"ticker": "XLB",  "name": "Materials",           "category": "Sector"},
    {"ticker": "XLI",  "name": "Industrials",         "category": "Sector"},
    {"ticker": "XLU",  "name": "Utilities",           "category": "Sector"},
    {"ticker": "XLRE", "name": "Real Estate",         "category": "Sector"},
    {"ticker": "TLT",  "name": "20+ Yr Treasury",     "category": "Fixed Income"},
    {"ticker": "IEF",  "name": "7-10 Yr Treasury",    "category": "Fixed Income"},
    {"ticker": "SHY",  "name": "1-3 Yr Treasury",     "category": "Fixed Income"},
    {"ticker": "HYG",  "name": "High Yield Corp",     "category": "Fixed Income"},
    {"ticker": "LQD",  "name": "Investment Grade Corp","category": "Fixed Income"},
    {"ticker": "GLD",  "name": "Gold",                "category": "Commodity"},
    {"ticker": "SLV",  "name": "Silver",              "category": "Commodity"},
    {"ticker": "USO",  "name": "Oil",                 "category": "Commodity"},
    {"ticker": "UNG",  "name": "Natural Gas",         "category": "Commodity"},
    {"ticker": "DBA",  "name": "Agriculture",         "category": "Commodity"},
    {"ticker": "EFA",  "name": "Developed Markets",   "category": "International"},
    {"ticker": "EEM",  "name": "Emerging Markets",    "category": "International"},
    {"ticker": "FXI",  "name": "China Large-Cap",     "category": "International"},
    {"ticker": "EWJ",  "name": "Japan",               "category": "International"},
    {"ticker": "IEFA", "name": "Core MSCI EAFE",      "category": "International"},
    {"ticker": "SOXX", "name": "iShares Semiconductors",     "category": "Semiconductor"},
    {"ticker": "SMH",  "name": "VanEck Semiconductors",      "category": "Semiconductor"},
    {"ticker": "SOXQ", "name": "Invesco PHLX Semis",         "category": "Semiconductor"},
    {"ticker": "PSI",  "name": "Invesco Dynamic Semis",      "category": "Semiconductor"},
    {"ticker": "FTXL", "name": "First Trust Nasdaq Semis",   "category": "Semiconductor"},
    {"ticker": "IGV",  "name": "iShares Expanded Tech-SW",   "category": "Software"},
    {"ticker": "WCLD", "name": "WisdomTree Cloud Computing", "category": "Software"},
    {"ticker": "BUG",  "name": "Global X Cybersecurity",     "category": "Software"},
    {"ticker": "CIBR", "name": "First Trust Cybersecurity",  "category": "Software"},
    {"ticker": "CLOU", "name": "Global X Cloud Computing",   "category": "Software"},
]

__all__ = [
    "ttl_cache", "CACHE_TTL", "SPX_TICKERS", "NASDAQ_100_TICKERS",
    "compute_rsi", "np", "pd", "yf", "datetime", "timedelta",
    "get_metadata", "get_short_interest", "get_fundamentals", "get_analyst_consensus",
    "_batch_download", "_rsi_last", "_NASDAQ_COMPANY_NAMES", "ETF_UNIVERSE",
]
