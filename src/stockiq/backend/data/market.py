import logging

import pandas as pd
import yfinance as yf

from stockiq.backend.cache import ttl_cache
from stockiq.backend.config import CACHE_TTL

logging.getLogger("yfinance").setLevel(logging.CRITICAL)


@ttl_cache(CACHE_TTL["fetch_spx_quote"])
def fetch_spx_quote() -> dict:
    """Near-real-time SPY quote via yfinance fast_info. Cached 60 s. Returns {} on error."""
    try:
        fi    = yf.Ticker("SPY").fast_info
        price = float(fi.last_price)
        prev  = float(fi.previous_close)

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


@ttl_cache(CACHE_TTL["fetch_spx_intraday"])
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


@ttl_cache(CACHE_TTL["fetch_vix_ohlc"])
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


@ttl_cache(CACHE_TTL["fetch_vix_history"])
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


@ttl_cache(CACHE_TTL["fetch_spy_options_data"])
def fetch_spy_options_data(expiration: str = "") -> dict | None:
    """
    Fetch SPY options chain (calls + puts) for one expiration.
    If expiration is "" or not found, uses the nearest available date.

    Returns:
        {
          "calls":       DataFrame  (strike, openInterest, volume, impliedVolatility, …)
          "puts":        DataFrame
          "expiration":  str        (ISO date used)
          "expirations": list[str]  (all available ISO dates)
        }
    or None on error.
    """
    try:
        ticker   = yf.Ticker("SPY")
        all_exps = list(ticker.options)
        if not all_exps:
            return None
        exp = expiration if expiration in all_exps else all_exps[0]
        chain = ticker.option_chain(exp)
        return {
            "calls":       chain.calls,
            "puts":        chain.puts,
            "expiration":  exp,
            "expirations": all_exps,
        }
    except Exception:
        return None


@ttl_cache(CACHE_TTL["fetch_put_call_ratio"])
def fetch_put_call_ratio(scope: str = "daily") -> dict | None:
    """
    Compute SPY put/call ratio from option activity.

    scope:
      "daily"   — today's volume across the 4 nearest expirations
      "7d"      — open interest across expirations within 7 days
      "14d"     — open interest across expirations within 14 days
      "21d"     — open interest across expirations within 21 days
      "monthly" — open interest across expirations within 30 days
    """
    from datetime import datetime, timedelta

    _SCOPE_META = {
        "daily":  {"label": "Daily",   "note": "Today's volume · 4 nearest expirations · resets daily"},
        "7d":     {"label": "7 Days",  "note": "Open interest · expirations within 7 days"},
        "14d":    {"label": "14 Days", "note": "Open interest · expirations within 14 days"},
        "21d":    {"label": "21 Days", "note": "Open interest · expirations within 21 days"},
        "monthly":{"label": "Monthly", "note": "Open interest · expirations ≤ 30 days out"},
    }

    try:
        ticker = yf.Ticker("SPY")
        all_exps = ticker.options
        if not all_exps:
            return None

        today = datetime.today().date()

        if scope == "daily":
            expirations = all_exps[:4]
            prefer_volume = True
        elif scope in ("7d", "14d", "21d", "monthly"):
            days = {"7d": 7, "14d": 14, "21d": 21, "monthly": 30}[scope]
            cutoff = today + timedelta(days=days)
            expirations = [e for e in all_exps
                           if datetime.strptime(e, "%Y-%m-%d").date() <= cutoff]
            prefer_volume = False
        else:
            return None

        if not expirations:
            return None

        total_puts = total_calls = 0
        for exp in expirations:
            chain = ticker.option_chain(exp)
            if prefer_volume:
                put_v  = chain.puts["volume"].fillna(0).sum()
                call_v = chain.calls["volume"].fillna(0).sum()
                if put_v > 0 or call_v > 0:
                    total_puts  += int(put_v)
                    total_calls += int(call_v)
                    continue
            total_puts  += int(chain.puts["openInterest"].fillna(0).sum())
            total_calls += int(chain.calls["openInterest"].fillna(0).sum())

        if not total_calls:
            return None

        ratio = round(total_puts / total_calls, 3)
        if ratio > 1.2:
            signal, color = "Extreme Fear — contrarian bullish", "#22C55E"
        elif ratio > 1.0:
            signal, color = "Fearful — mild bullish lean",        "#86EFAC"
        elif ratio > 0.8:
            signal, color = "Neutral",                             "#94A3B8"
        elif ratio > 0.6:
            signal, color = "Complacent — mild bearish lean",     "#F59E0B"
        else:
            signal, color = "Extreme Greed — contrarian bearish", "#EF4444"

        meta = _SCOPE_META[scope]
        return {
            "ratio":        ratio,
            "signal":       signal,
            "color":        color,
            "puts":         total_puts,
            "calls":        total_calls,
            "scope_label":  meta["label"],
            "scope_note":   meta["note"],
            "exp_count":    len(expirations),
            "exp_nearest":  expirations[0],
            "exp_farthest": expirations[-1],
        }
    except Exception:
        return None


@ttl_cache(CACHE_TTL["fetch_index_snapshot"])
def fetch_index_snapshot() -> pd.DataFrame:
    """
    Day-change snapshot for major indices used in the SPX dashboard. Cached 120 s.

    Strategy:
      1. Try fast_info for each ticker — gives live intraday prices when US market is open.
      2. fast_info returns None outside market hours (weekends, pre-market in Europe).
         For any ticker that returns None/0, fall back to a single batch OHLCV download
         so the landing page always shows the last known session close — never empty.
    """
    _SYMBOLS = {
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq",
        "^DJI":  "Dow Jones",
        "^RUT":  "Russell 2000",
        "SPY":   "SPY",
        "QQQ":   "QQQ",
        "^VIX":  "VIX",
    }

    prices: dict[str, tuple[float, float]] = {}  # sym → (price, prev_close)

    # Pass 1 — fast_info (live; may return None when market is closed)
    needs_fallback = []
    for sym in _SYMBOLS:
        try:
            fi    = yf.Ticker(sym).fast_info
            price = float(fi.last_price or 0)
            prev  = float(fi.previous_close or 0)
            if price > 0 and prev > 0:
                prices[sym] = (price, prev)
            else:
                needs_fallback.append(sym)
        except Exception:
            needs_fallback.append(sym)

    # Pass 2 — single batch download for any ticker fast_info couldn't serve
    # (covers weekends, pre-market hours, and any transient API errors)
    if needs_fallback:
        try:
            hist = yf.download(
                needs_fallback,
                period="5d",
                interval="1d",
                progress=False,
                auto_adjust=True,
            )
            if isinstance(hist.columns, pd.MultiIndex):
                closes = hist["Close"]
            else:
                # single ticker comes back as flat columns
                closes = hist[["Close"]].rename(columns={"Close": needs_fallback[0]})

            closes = closes.dropna(how="all")
            for sym in needs_fallback:
                try:
                    col = closes[sym].dropna()
                    if len(col) >= 2:
                        prices[sym] = (float(col.iloc[-1]), float(col.iloc[-2]))
                except Exception:
                    continue
        except Exception:
            pass

    # Build result in original order
    rows = []
    for sym, name in _SYMBOLS.items():
        if sym not in prices:
            continue
        price, prev = prices[sym]
        chg = price - prev
        rows.append({
            "Index":    name,
            "Symbol":   sym,
            "Price":    round(price, 2),
            "Change":   round(chg, 2),
            "Change %": round(chg / prev * 100, 2),
        })
    return pd.DataFrame(rows)
