import logging

import pandas as pd
import streamlit as st
import yfinance as yf

from indexiq.cache_ttl import CACHE_TTL

logging.getLogger("yfinance").setLevel(logging.CRITICAL)


@st.cache_data(ttl=CACHE_TTL["fetch_spx_quote"])
def fetch_spx_quote() -> dict:
    """Near-real-time SPY quote via yfinance fast_info. Cached 60 s. Returns {} on error."""
    try:
        fi    = yf.Ticker("SPY").fast_info
        price = float(fi.last_price)
        prev  = float(fi.previous_close)

        # fast_info.volume is absent in some yfinance versions — fall back to 1d download
        vol = int(getattr(fi, "volume", 0) or 0)
        if not vol:
            try:
                day_df = yf.download("SPY", period="1d", interval="1d", progress=False, auto_adjust=True)
                if isinstance(day_df.columns, pd.MultiIndex):
                    day_df.columns = day_df.columns.get_level_values(0)
                vol = int(day_df["Volume"].iloc[-1]) if "Volume" in day_df.columns and not day_df.empty else 0
            except Exception:
                vol = 0

        return {
            "price":      price,
            "prev_close": prev,
            "change":     price - prev,
            "change_pct": (price - prev) / prev * 100,
            "day_open":   float(getattr(fi, "open",               0) or 0),
            "day_high":   float(getattr(fi, "day_high",            0) or 0),
            "day_low":    float(getattr(fi, "day_low",             0) or 0),
            "volume":     vol,
            "w52_high":   float(getattr(fi, "fifty_two_week_high", 0) or 0),
            "w52_low":    float(getattr(fi, "fifty_two_week_low",  0) or 0),
        }
    except Exception:
        return {}


@st.cache_data(ttl=CACHE_TTL["fetch_spx_intraday"])
def fetch_spx_intraday(period: str = "1d", interval: str = "5m") -> pd.DataFrame:
    """
    SPY price history for any period / interval combination.
    Examples:
      period="1d",  interval="5m"   → today's intraday bars
      period="5d",  interval="30m"  → 5-day half-hourly bars
      period="1y",  interval="1d"   → daily bars for MA/RSI analysis
    Cached 120 s.
    """
    try:
        df = yf.download(
            "SPY",
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL["fetch_vix_ohlc"])
def fetch_vix_ohlc(period: str = "1y") -> pd.DataFrame:
    """Daily VIX OHLC history (Open, High, Low, Close) for gap analysis. Cached 1 hour."""
    try:
        df = yf.download(
            "^VIX",
            period=period,
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        cols = ["Open", "High", "Low", "Close"] + (["Volume"] if "Volume" in df.columns else [])
        return df[cols].dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL["fetch_vix_history"])
def fetch_vix_history(period: str = "1y") -> pd.DataFrame:
    """
    Daily VIX close alongside SPY close for dual-axis comparison.
    Returns DataFrame with columns: Date (index), SPY, VIX.
    Cached 1 hour.
    """
    try:
        raw = yf.download(
            ["SPY", "^VIX"],
            period=period,
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"].copy()
        else:
            close = raw[["Close"]].copy()
        close.columns = [c.replace("^VIX", "VIX") for c in close.columns]
        return close.dropna()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL["fetch_index_snapshot"])
def fetch_index_snapshot() -> pd.DataFrame:
    """Day-change snapshot for major indices used in the SPX dashboard. Cached 120 s."""
    symbols = {
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq",
        "^DJI":  "Dow Jones",
        "^RUT":  "Russell 2000",
        "SPY":   "SPY",
        "QQQ":   "QQQ",
        "^VIX":  "VIX",
    }
    rows = []
    for sym, name in symbols.items():
        try:
            fi    = yf.Ticker(sym).fast_info
            price = float(fi.last_price)
            prev  = float(fi.previous_close)
            chg   = price - prev
            rows.append({
                "Index":    name,
                "Symbol":   sym,
                "Price":    price,
                "Change":   chg,
                "Change %": chg / prev * 100,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)
