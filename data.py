from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from config import SPX_TICKERS


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
    Fetches extra history (period_days + 1450) so long-period MAs have enough data.
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


@st.cache_data(ttl=3600)
def fetch_spx_recommendations() -> pd.DataFrame:
    """
    Fetch last 6 months of data for all SPX_TOP_30 tickers.
    Resample to weekly and monthly, count green candles, produce BUY/SELL signal.
    Cached for 1 hour.
    """
    recommendations = []
    progress = st.empty()

    for idx, ticker in enumerate(SPX_TICKERS):
        progress.info(f"Fetching {ticker}… ({idx + 1}/{len(SPX_TICKERS)})")
        try:
            end_date   = datetime.today()
            start_date = end_date - timedelta(days=180)
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < 10:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 10:
                continue

            company_name = yf.Ticker(ticker).info.get("longName", ticker)

            weekly_df     = df[["Open", "Close"]].resample("W").agg({"Open": "first", "Close": "last"})
            weekly_last_4 = weekly_df.tail(4)
            weekly_green  = sum(1 for _, row in weekly_last_4.iterrows() if row["Close"] > row["Open"])
            weekly_status = ["🟢" if row["Close"] > row["Open"] else "🔴" for _, row in weekly_last_4.iterrows()]

            monthly_df     = df[["Open", "Close"]].resample("ME").agg({"Open": "first", "Close": "last"})
            monthly_last_4 = monthly_df.tail(4)
            monthly_green  = sum(1 for _, row in monthly_last_4.iterrows() if row["Close"] > row["Open"])
            monthly_status = ["🟢" if row["Close"] > row["Open"] else "🔴" for _, row in monthly_last_4.iterrows()]

            signal   = "🟢 BUY" if (weekly_green == 4 and monthly_green >= 3) else "🔴 SELL"
            strength = weekly_green + monthly_green

            recommendations.append({
                "Ticker":       ticker,
                "Company":      company_name,
                "Last Price":   f"${df['Close'].iloc[-1]:.2f}",
                "🔷 Weeks":     " ".join(weekly_status),
                "Green Weeks":  f"{weekly_green}/4",
                "🔶 Months":    " ".join(monthly_status),
                "Green Months": f"{monthly_green}/4",
                "Signal":       signal,
                "Strength":     strength,
            })
        except Exception:
            continue

    progress.empty()
    if not recommendations:
        return pd.DataFrame()
    return pd.DataFrame(recommendations).sort_values("Strength", ascending=False)


@st.cache_data(ttl=1800)  # 30-min cache — scan is expensive
def fetch_bounce_candidates(threshold_pct: float = 5.0, top_n: int = 30) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for stocks whose price is within ±threshold_pct of
    their 200-day moving average.  Ranks results by a bounce score that
    rewards stocks that are:
      • closer to the MA200
      • below the MA200 (testing support rather than resistance)
      • more oversold on RSI

    Returns the top_n rows sorted by bounce score descending.
    """
    results  = []
    progress = st.empty()

    for idx, ticker in enumerate(SPX_TICKERS):
        progress.info(f"Scanning {ticker}… ({idx + 1}/{len(SPX_TICKERS)})")
        try:
            end_date   = datetime.today()
            start_date = end_date - timedelta(days=320)  # enough for MA200 warmup
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < 201:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 201:
                continue

            price  = float(df["Close"].iloc[-1])
            ma200  = float(df["Close"].rolling(200).mean().iloc[-1])
            ma50   = float(df["Close"].rolling(50).mean().iloc[-1])

            if np.isnan(ma200):
                continue

            dist_pct = (price - ma200) / ma200 * 100
            if abs(dist_pct) > threshold_pct:
                continue

            # RSI-14 (Wilder EWM)
            delta    = df["Close"].diff()
            avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
            avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
            rs       = avg_gain / avg_loss.replace(0, np.nan)
            rsi      = float((100 - 100 / (1 + rs)).iloc[-1])

            trend = "📈 Uptrend" if ma50 > ma200 else "📉 Downtrend"

            # Bounce score: rewards oversold RSI + proximity + being below MA200
            proximity_bonus  = (threshold_pct - abs(dist_pct)) * 2   # 0-10
            oversold_bonus   = max(0, 50 - rsi)                       # 0-50
            support_bonus    = 8 if dist_pct < 0 else 0               # below MA200 = testing support
            bounce_score     = proximity_bonus + oversold_bonus + support_bonus

            # RSI condition label
            if rsi <= 30:
                rsi_label = "🟢 Oversold"
            elif rsi >= 70:
                rsi_label = "🔴 Overbought"
            else:
                rsi_label = "⚪ Neutral"

            company_name = yf.Ticker(ticker).info.get("longName", ticker)

            results.append({
                "Ticker":        ticker,
                "Company":       company_name,
                "Price":         round(price, 2),
                "MA 200":        round(ma200, 2),
                "Distance %":    round(dist_pct, 2),
                "RSI":           round(rsi, 1),
                "RSI Zone":      rsi_label,
                "Trend":         trend,
                "Bounce Score":  round(bounce_score, 1),
            })
        except Exception:
            continue

    progress.empty()
    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Bounce Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


@st.cache_data(ttl=3600)  # 1-hour cache — short interest is reported infrequently
def fetch_squeeze_candidates(
    rsi_min: float = 55.0,
    min_short_float: float = 0.5,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for potential short-squeeze setups:
      • RSI ≥ rsi_min       — stock is overbought / extended (shorts under pressure)
      • Short % of Float ≥ min_short_float — meaningful short interest exists

    Tiers are calibrated for large-cap S&P 500 stocks where 2–5% short float
    is genuinely elevated (vs. small/mid-cap where 10–30% is common).

    Squeeze Score formula
    ─────────────────────
      RSI component       = (RSI − 50) × 0.4          [rewards RSI above 50, max ~20]
      Short float tier    = ≥5% → 40 | ≥3% → 25 | ≥1.5% → 15 | else → pct×8
      Days-to-cover tier  = ≥10 → 20 | ≥5  → 12 | ≥2   →  6  | else → ratio×2
      Short-build bonus   = +5 if shares short increased vs prior month
    Higher score = stronger squeeze pressure.
    """
    results  = []
    progress = st.empty()

    for idx, ticker in enumerate(SPX_TICKERS):
        progress.info(f"Scanning {ticker}… ({idx + 1}/{len(SPX_TICKERS)})")
        try:
            # ── Price history (60 days is enough for RSI-14) ──────────────────
            end_date   = datetime.today()
            start_date = end_date - timedelta(days=90)
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < 14:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 14:
                continue

            # ── RSI-14 ────────────────────────────────────────────────────────
            delta    = df["Close"].diff()
            avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
            avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
            rs       = avg_gain / avg_loss.replace(0, np.nan)
            rsi      = float((100 - 100 / (1 + rs)).iloc[-1])

            if np.isnan(rsi) or rsi < rsi_min:
                continue

            # ── Short-interest data via yfinance info ─────────────────────────
            info = yf.Ticker(ticker).info

            # shortPercentOfFloat comes as a decimal (e.g. 0.05 = 5 %)
            raw_spf        = info.get("shortPercentOfFloat") or 0.0
            short_pct_flt  = raw_spf * 100.0

            short_ratio    = float(info.get("shortRatio")           or 0.0)
            shares_short   = int(  info.get("sharesShort")          or 0)
            shares_prior   = int(  info.get("sharesShortPriorMonth") or 0)

            if short_pct_flt < min_short_float:
                continue

            price        = float(df["Close"].iloc[-1])
            company_name = info.get("longName", ticker)

            # MoM short change
            short_change_pct = (
                (shares_short - shares_prior) / shares_prior * 100
                if shares_prior > 0 else 0.0
            )

            # ── Squeeze Score ─────────────────────────────────────────────────
            # 1. RSI component — rewards any elevation above 50
            rsi_score = max(0.0, (rsi - 50.0)) * 0.4

            # 2. Short % of float tier (calibrated for large-cap reality)
            if short_pct_flt >= 5:
                float_score = 40.0
            elif short_pct_flt >= 3:
                float_score = 25.0
            elif short_pct_flt >= 1.5:
                float_score = 15.0
            else:
                float_score = short_pct_flt * 8.0

            # 3. Days-to-cover (short ratio) tier
            if short_ratio >= 10:
                ratio_score = 20.0
            elif short_ratio >= 5:
                ratio_score = 12.0
            elif short_ratio >= 2:
                ratio_score = 6.0
            else:
                ratio_score = short_ratio * 2.0

            # 4. Shorts building bonus
            build_score = 5.0 if short_change_pct > 0 else 0.0

            squeeze_score = rsi_score + float_score + ratio_score + build_score

            # ── RSI zone label ────────────────────────────────────────────────
            if rsi >= 80:
                rsi_zone = "🔴 Extreme OB"
            elif rsi >= 70:
                rsi_zone = "🟠 Overbought"
            else:
                rsi_zone = "🟡 Elevated"

            results.append({
                "Ticker":           ticker,
                "Company":          company_name,
                "Price":            round(price, 2),
                "RSI":              round(rsi, 1),
                "RSI Zone":         rsi_zone,
                "Short % Float":    round(short_pct_flt, 1),
                "Days to Cover":    round(short_ratio, 1),
                "Short Chg % MoM":  round(short_change_pct, 1),
                "Squeeze Score":    round(squeeze_score, 1),
            })
        except Exception:
            continue

    progress.empty()
    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Squeeze Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
