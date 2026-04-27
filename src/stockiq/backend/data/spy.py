"""SPY-specific data fetchers — price, intraday bars, options chain, put/call ratio."""

import logging
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

from stockiq.backend.cache import ttl_cache
from stockiq.backend.config import CACHE_TTL

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

_CBOE_SPY_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/SPY.json"
_CBOE_HEADERS = {"User-Agent": "Mozilla/5.0"}

_PCR_SCOPE_META = {
    "daily":   {"label": "Daily",   "note": "Today's volume · 4 nearest expirations · resets daily"},
    "7d":      {"label": "7 Days",  "note": "Open interest · expirations within 7 days"},
    "14d":     {"label": "14 Days", "note": "Open interest · expirations within 14 days"},
    "21d":     {"label": "21 Days", "note": "Open interest · expirations within 21 days"},
    "monthly": {"label": "Monthly", "note": "Open interest · expirations ≤ 30 days out"},
}


def _pcr_signal(ratio: float) -> tuple[str, str]:
    if ratio > 1.2:
        return "Extreme Fear — contrarian bullish", "#22C55E"
    if ratio > 1.0:
        return "Fearful — mild bullish lean",        "#86EFAC"
    if ratio > 0.8:
        return "Neutral",                             "#94A3B8"
    if ratio > 0.6:
        return "Complacent — mild bearish lean",     "#F59E0B"
    return "Extreme Greed — contrarian bearish",     "#EF4444"


# ── Quote & price history ──────────────────────────────────────────────────────

@ttl_cache(CACHE_TTL["fetch_spx_quote"])
def fetch_spx_quote() -> dict:
    """SPY quote via yfinance .info — includes regularMarketTime for freshness comparison. Cached 60 s."""
    try:
        info  = yf.Ticker("SPY").info
        price = float(info.get("regularMarketPrice") or info.get("currentPrice") or 0)
        prev  = float(info.get("regularMarketPreviousClose") or info.get("previousClose") or 0)
        if not price:
            return {}
        return {
            "price":      price,
            "prev_close": prev,
            "change":     round(price - prev, 2),
            "change_pct": round((price - prev) / prev * 100, 4) if prev else 0,
            "day_open":   float(info.get("open")         or 0),
            "day_high":   float(info.get("dayHigh")       or 0),
            "day_low":    float(info.get("dayLow")        or 0),
            "volume":     int(  info.get("volume")        or 0),
            "w52_high":   float(info.get("fiftyTwoWeekHigh") or 0),
            "w52_low":    float(info.get("fiftyTwoWeekLow")  or 0),
            "_ts":        int(  info.get("regularMarketTime") or 0),
        }
    except Exception:
        return {}


@ttl_cache(CACHE_TTL["fetch_spx_quote_cboe"])
def fetch_spx_quote_cboe() -> dict:
    """SPY quote from CBOE CDN (15-min delayed). Same return shape as fetch_spx_quote. Returns {} on error."""
    try:
        resp = requests.get(_CBOE_SPY_URL, timeout=10, headers=_CBOE_HEADERS)
        resp.raise_for_status()
        d     = resp.json().get("data", {})
        price = float(d.get("current_price") or 0)
        prev  = float(d.get("prev_day_close") or 0)
        if not price:
            return {}
        ts_str = d.get("last_trade_time") or ""
        try:
            ts = int(datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S").timestamp())
        except Exception:
            ts = 0
        return {
            "price":      price,
            "prev_close": prev,
            "change":     round(float(d.get("price_change") or 0), 2),
            "change_pct": round(float(d.get("price_change_percent") or 0), 4),
            "day_open":   float(d.get("open")   or 0),
            "day_high":   float(d.get("high")   or 0),
            "day_low":    float(d.get("low")    or 0),
            "volume":     int(d.get("volume")   or 0),
            "w52_high":   None,
            "w52_low":    None,
            "_ts":        ts,
        }
    except Exception:
        return {}


@ttl_cache(CACHE_TTL["fetch_spx_intraday"])
def fetch_spx_intraday(period: str = "1d", interval: str = "5m") -> pd.DataFrame:
    """
    SPY price history for any period / interval combination.
      period="1d",  interval="5m"   → today's intraday bars (incl. pre/post market)
      period="5d",  interval="30m"  → 5-day half-hourly bars (incl. pre/post market)
      period="1y",  interval="1d"   → daily bars for MA/RSI analysis
    Cached 120 s. prepost=True for sub-day intervals extends coverage to
    4am–8pm ET so the chart populates outside regular market hours.
    """
    try:
        intraday = not interval.endswith("d")
        df = yf.download(
            "SPY", period=period, interval=interval,
            progress=False, auto_adjust=False,
            prepost=intraday,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


# ── Options chain (Yahoo Finance, primary) ─────────────────────────────────────

@ttl_cache(CACHE_TTL["fetch_spy_options_data"])
def fetch_spy_options_data(expiration: str = "") -> dict | None:
    """
    SPY options chain (calls + puts) for one expiration via Yahoo Finance.
    Falls back to nearest expiration when requested date is unavailable.

    Returns {calls, puts, expiration, expirations} or None on error.
    """
    try:
        ticker   = yf.Ticker("SPY")
        all_exps = list(ticker.options)
        if not all_exps:
            return None
        exp   = expiration if expiration in all_exps else all_exps[0]
        chain = ticker.option_chain(exp)
        return {"calls": chain.calls, "puts": chain.puts, "expiration": exp, "expirations": all_exps}
    except Exception:
        return None


@ttl_cache(CACHE_TTL["fetch_put_call_ratio"])
def fetch_put_call_ratio(scope: str = "daily") -> dict | None:
    """
    SPY put/call ratio from Yahoo Finance options activity.
    scope: 'daily' | '7d' | '14d' | '21d' | 'monthly'
    """
    try:
        ticker   = yf.Ticker("SPY")
        all_exps = ticker.options
        if not all_exps:
            return None

        today = datetime.today().date()
        if scope == "daily":
            expirations   = all_exps[:4]
            prefer_volume = True
        elif scope in ("7d", "14d", "21d", "monthly"):
            days          = {"7d": 7, "14d": 14, "21d": 21, "monthly": 30}[scope]
            cutoff        = today + timedelta(days=days)
            expirations   = [e for e in all_exps if datetime.strptime(e, "%Y-%m-%d").date() <= cutoff]
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

        ratio          = round(total_puts / total_calls, 3)
        signal, color  = _pcr_signal(ratio)
        meta           = _PCR_SCOPE_META[scope]
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


# ── Options chain (CBOE CDN, fallback) ────────────────────────────────────────

def _parse_cboe_options() -> list[dict] | None:
    """Fetch and parse all SPY options from CBOE CDN into a list of row dicts."""
    try:
        resp     = requests.get(_CBOE_SPY_URL, timeout=10, headers=_CBOE_HEADERS)
        resp.raise_for_status()
        raw_opts = resp.json().get("data", {}).get("options", [])
        if not raw_opts:
            return None

        rows = []
        for opt in raw_opts:
            sym = opt.get("option", "").strip()
            if sym.startswith("SPY "):
                code = sym[4:]
            elif sym.startswith("SPY"):
                code = sym[3:]
            else:
                continue
            if len(code) < 15:
                continue
            opt_type = code[6].upper()
            if opt_type not in ("C", "P"):
                continue
            rows.append({
                "expiration":        f"20{code[0:2]}-{code[2:4]}-{code[4:6]}",
                "type":              opt_type,
                "strike":            int(code[7:15]) / 1000.0,
                "openInterest":      int(opt.get("open_interest", 0) or 0),
                "volume":            int(opt.get("volume", 0) or 0),
                "impliedVolatility": float(opt.get("iv", 0) or 0),
            })
        return rows or None
    except Exception:
        return None


@ttl_cache(CACHE_TTL["fetch_spy_options_data_cboe"])
def fetch_spy_options_data_cboe(expiration: str = "") -> dict | None:
    """CBOE CDN fallback for SPY options chain. Same return shape as fetch_spy_options_data."""
    rows = _parse_cboe_options()
    if not rows:
        return None

    df       = pd.DataFrame(rows)
    all_exps = sorted(df["expiration"].unique().tolist())
    exp      = expiration if expiration in all_exps else all_exps[0]
    exp_df   = df[df["expiration"] == exp]

    cols  = ["strike", "openInterest", "volume", "impliedVolatility"]
    calls = exp_df[exp_df["type"] == "C"][cols].reset_index(drop=True)
    puts  = exp_df[exp_df["type"] == "P"][cols].reset_index(drop=True)
    return {"calls": calls, "puts": puts, "expiration": exp, "expirations": all_exps}


@ttl_cache(CACHE_TTL["fetch_put_call_ratio_cboe"])
def fetch_put_call_ratio_cboe(scope: str = "daily") -> dict | None:
    """CBOE CDN fallback for SPY put/call ratio. Same return shape as fetch_put_call_ratio."""
    rows = _parse_cboe_options()
    if not rows:
        return None

    df       = pd.DataFrame(rows)
    all_exps = sorted(df["expiration"].unique().tolist())
    today    = datetime.today().date()

    if scope == "daily":
        expirations = all_exps[:4]
        metric      = "volume"
    elif scope in ("7d", "14d", "21d", "monthly"):
        days        = {"7d": 7, "14d": 14, "21d": 21, "monthly": 30}[scope]
        cutoff      = today + timedelta(days=days)
        expirations = [e for e in all_exps if datetime.strptime(e, "%Y-%m-%d").date() <= cutoff]
        metric      = "openInterest"
    else:
        return None

    if not expirations:
        return None

    filt        = df[df["expiration"].isin(expirations)]
    total_puts  = int(filt[filt["type"] == "P"][metric].sum())
    total_calls = int(filt[filt["type"] == "C"][metric].sum())

    if not total_calls:
        return None

    ratio         = round(total_puts / total_calls, 3)
    signal, color = _pcr_signal(ratio)
    meta          = _PCR_SCOPE_META[scope]
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
