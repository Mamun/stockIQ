from datetime import datetime, timedelta
import logging

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from config import SPX_TICKERS

# Suppress yfinance "possibly delisted" and "no timezone" warnings
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
    success_count = 0
    error_count = 0

    for idx, ticker in enumerate(SPX_TICKERS):
        progress.info(f"Scanning {ticker}… ({idx + 1}/{len(SPX_TICKERS)}) - Success: {success_count}, Errors: {error_count}")
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
                error_count += 1
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 201:
                error_count += 1
                continue

            price  = float(df["Close"].iloc[-1])
            ma200  = float(df["Close"].rolling(200).mean().iloc[-1])
            ma50   = float(df["Close"].rolling(50).mean().iloc[-1])

            if np.isnan(ma200):
                error_count += 1
                continue

            dist_pct = (price - ma200) / ma200 * 100
            if abs(dist_pct) > threshold_pct:
                error_count += 1
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
            success_count += 1
        except Exception as e:
            error_count += 1
            # Log the error for debugging
            st.write(f"Error processing {ticker}: {str(e)}")
            continue

    progress.empty()
    st.write(f"Debug: Processed {len(SPX_TICKERS)} tickers, {success_count} successful, {error_count} errors")
    if not results:
        st.error("No bounce candidates found. This might be due to network issues or data availability.")
        return pd.DataFrame()

    df_result = (
        pd.DataFrame(results)
        .sort_values("Bounce Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    st.write(f"Debug: Returning DataFrame with {len(df_result)} rows")
    return df_result


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


# ── Munger Strategy helpers ────────────────────────────────────────────────────

def _quality_score(info: dict) -> tuple[float, list[str]]:
    """
    Score a stock's fundamental quality (Munger-style).
    Returns (score 0–85, breakdown list).

    Component          Max
    ─────────────────  ───
    ROE                 25
    Profit Margin       20
    Revenue Growth      15
    Debt/Equity         15
    EPS Growth          10
    ─────────────────  ───
    Total               85
    """
    score = 0.0
    breakdown: list[str] = []

    # 1. Return on Equity (returnOnEquity — decimal)
    roe = info.get("returnOnEquity")
    if roe is not None:
        roe_pct = roe * 100
        if roe_pct >= 20:
            pts = 25.0
        elif roe_pct >= 15:
            pts = 18.0
        elif roe_pct >= 10:
            pts = 10.0
        elif roe_pct > 0:
            pts = 5.0
        else:
            pts = 0.0
        score += pts
        breakdown.append(f"ROE {roe_pct:.1f}% → {pts:.0f}/25")

    # 2. Profit Margin (profitMargins — decimal)
    pm = info.get("profitMargins")
    if pm is not None:
        pm_pct = pm * 100
        if pm_pct >= 20:
            pts = 20.0
        elif pm_pct >= 10:
            pts = 14.0
        elif pm_pct >= 5:
            pts = 8.0
        elif pm_pct > 0:
            pts = 3.0
        else:
            pts = 0.0
        score += pts
        breakdown.append(f"Profit Margin {pm_pct:.1f}% → {pts:.0f}/20")

    # 3. Revenue Growth (revenueGrowth — decimal YoY)
    rg = info.get("revenueGrowth")
    if rg is not None:
        rg_pct = rg * 100
        if rg_pct >= 15:
            pts = 15.0
        elif rg_pct >= 8:
            pts = 10.0
        elif rg_pct >= 3:
            pts = 6.0
        elif rg_pct >= 0:
            pts = 2.0
        else:
            pts = 0.0
        score += pts
        breakdown.append(f"Revenue Growth {rg_pct:.1f}% → {pts:.0f}/15")

    # 4. Debt/Equity (debtToEquity — already as percentage, e.g. 45 means 0.45×)
    de = info.get("debtToEquity")
    if de is not None:
        de_ratio = de / 100.0
        if de_ratio < 0.3:
            pts = 15.0
        elif de_ratio < 0.7:
            pts = 10.0
        elif de_ratio < 1.5:
            pts = 5.0
        else:
            pts = 0.0
        score += pts
        breakdown.append(f"D/E {de_ratio:.2f}× → {pts:.0f}/15")

    # 5. EPS Growth (earningsGrowth — decimal YoY)
    eg = info.get("earningsGrowth")
    if eg is not None:
        eg_pct = eg * 100
        if eg_pct >= 15:
            pts = 10.0
        elif eg_pct >= 8:
            pts = 7.0
        elif eg_pct >= 0:
            pts = 3.0
        else:
            pts = 0.0
        score += pts
        breakdown.append(f"EPS Growth {eg_pct:.1f}% → {pts:.0f}/10")

    return score, breakdown


def _proximity_score(dist_pct: float) -> int:
    """Points for how close price is to the 200-week MA. Closer = higher score."""
    abs_d = abs(dist_pct)
    if abs_d <= 2:
        return 15
    elif abs_d <= 5:
        return 12
    elif abs_d <= 10:
        return 8
    elif abs_d <= 15:
        return 4
    elif abs_d <= 20:
        return 2
    return 0


@st.cache_data(ttl=3600)
def fetch_munger_candidates(
    threshold_pct: float = 15.0,
    min_quality: float = 30.0,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for Charlie Munger-style setups:
      "Buy wonderful companies at a fair price — ideally near the 200-week MA."

    Filters:
      • Price within ±threshold_pct of the 200-week moving average
      • Quality Score ≥ min_quality

    Munger Score = Quality Score (0–85) + Proximity Score (0–15)
    Max total = 100.
    """
    results  = []
    progress = st.empty()

    for idx, ticker in enumerate(SPX_TICKERS):
        progress.info(f"Scanning {ticker}… ({idx + 1}/{len(SPX_TICKERS)})")
        try:
            # Need ~4.5 years of daily data for a stable 200-week MA
            end_date   = datetime.today()
            start_date = end_date - timedelta(days=1600)
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < 200:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 200:
                continue

            # 200-week MA from weekly closes
            weekly = df["Close"].resample("W").last().dropna()
            if len(weekly) < 200:
                continue
            ma200w = float(weekly.rolling(200).mean().iloc[-1])
            if np.isnan(ma200w):
                continue

            price    = float(df["Close"].iloc[-1])
            dist_pct = (price - ma200w) / ma200w * 100

            if abs(dist_pct) > threshold_pct:
                continue

            # Fundamental quality
            info    = yf.Ticker(ticker).info
            q_score, breakdown = _quality_score(info)

            if q_score < min_quality:
                continue

            prox_score   = _proximity_score(dist_pct)
            munger_score = q_score + prox_score

            company_name = info.get("longName", ticker)
            sector       = info.get("sector", "—")

            # RSI-14 (last 60 days is enough)
            delta    = df["Close"].diff()
            avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
            avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
            rs       = avg_gain / avg_loss.replace(0, np.nan)
            rsi      = float((100 - 100 / (1 + rs)).iloc[-1])

            results.append({
                "Ticker":        ticker,
                "Company":       company_name,
                "Sector":        sector,
                "Price":         round(price, 2),
                "MA 200W":       round(ma200w, 2),
                "Distance %":    round(dist_pct, 2),
                "RSI":           round(rsi, 1),
                "Quality Score": round(q_score, 1),
                "Prox Score":    prox_score,
                "Munger Score":  round(munger_score, 1),
                "Breakdown":     " | ".join(breakdown),
            })
        except Exception:
            continue

    progress.empty()
    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Munger Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


# ── SPX live data ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch_spx_quote() -> dict:
    """
    Near-real-time S&P 500 quote via yfinance fast_info.
    Cached for 60 seconds.  Returns {} on error.
    """
    try:
        fi = yf.Ticker("^GSPC").fast_info
        price = float(fi.last_price)
        prev  = float(fi.previous_close)
        return {
            "price":      price,
            "prev_close": prev,
            "change":     price - prev,
            "change_pct": (price - prev) / prev * 100,
            "day_high":   float(getattr(fi, "day_high",            0) or 0),
            "day_low":    float(getattr(fi, "day_low",             0) or 0),
            "volume":     int(  getattr(fi, "volume",              0) or 0),
            "w52_high":   float(getattr(fi, "fifty_two_week_high", 0) or 0),
            "w52_low":    float(getattr(fi, "fifty_two_week_low",  0) or 0),
        }
    except Exception:
        return {}


@st.cache_data(ttl=120)
def fetch_spx_intraday(period: str = "1d", interval: str = "5m") -> pd.DataFrame:
    """
    SPX price history for any period / interval combination.
    Examples:
      period="1d",  interval="5m"   → today's intraday bars
      period="5d",  interval="30m"  → 5-day half-hourly bars
      period="1y",  interval="1d"   → daily bars for MA/RSI analysis
    Cached for 120 seconds.
    """
    try:
        df = yf.download(
            "^GSPC",
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120)
def fetch_index_snapshot() -> pd.DataFrame:
    """
    Day-change snapshot for the five major indices used in the SPX dashboard.
    Cached for 120 seconds.
    """
    symbols = {
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq",
        "^DJI":  "Dow Jones",
        "^RUT":  "Russell 2000",
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


# ── Strong Buy scanner ─────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_strong_buy_candidates(
    min_upside: float = 5.0,
    min_analysts: int = 5,
    max_rating: float = 2.5,
    top_n: int = 20,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for analyst strong-buy / buy consensus setups.

    yfinance recommendationMean scale:
      1.0 = Strong Buy · 2.0 = Buy · 3.0 = Hold · 4.0 = Sell · 5.0 = Strong Sell

    Strong Buy Score (max ~100)
    ─────────────────────────────
      Rating component   = (2.5 − mean) × 26.7   [max 40 at rating 1.0]
      Upside component   = min(upside %, 50) × 0.5 [max 25]
      Analyst confidence = min(analysts, 20) × 1.5  [max 30]
      RSI entry bonus    = +5 if RSI < 60           [not overbought at entry]
    """
    results  = []
    progress = st.empty()

    for idx, ticker in enumerate(SPX_TICKERS):
        progress.info(f"Scanning {ticker}… ({idx + 1}/{len(SPX_TICKERS)})")
        try:
            info = yf.Ticker(ticker).info

            rec_mean = info.get("recommendationMean")
            if rec_mean is None or float(rec_mean) > max_rating:
                continue

            num_analysts = int(info.get("numberOfAnalystOpinions") or 0)
            if num_analysts < min_analysts:
                continue

            target_mean = float(info.get("targetMeanPrice") or 0)
            target_high = float(info.get("targetHighPrice")  or 0)
            target_low  = float(info.get("targetLowPrice")   or 0)
            price       = float(
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or 0
            )

            if price <= 0 or target_mean <= 0:
                continue

            upside_pct = (target_mean - price) / price * 100
            if upside_pct < min_upside:
                continue

            # RSI-14 (60 days of daily bars is enough)
            end_dt   = datetime.today()
            start_dt = end_dt - timedelta(days=60)
            df = yf.download(
                ticker,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])

            rsi = np.nan
            if len(df) >= 14:
                delta    = df["Close"].diff()
                avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
                avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
                rs       = avg_gain / avg_loss.replace(0, np.nan)
                rsi      = float((100 - 100 / (1 + rs)).iloc[-1])

            # ── Strong Buy Score ───────────────────────────────────────────
            rating_score  = max(0.0, (2.5 - float(rec_mean)) * 26.7)   # max 40
            upside_score  = min(upside_pct, 50.0) * 0.5                # max 25
            analyst_score = min(num_analysts, 20) * 1.5                 # max 30
            rsi_bonus     = 5.0 if (not np.isnan(rsi) and rsi < 60) else 0.0
            sb_score      = rating_score + upside_score + analyst_score + rsi_bonus

            # ── Consensus label ────────────────────────────────────────────
            if float(rec_mean) <= 1.5:
                consensus = "⭐ Strong Buy"
            elif float(rec_mean) <= 2.0:
                consensus = "🟢 Buy"
            else:
                consensus = "🟡 Moderate Buy"

            results.append({
                "Ticker":       ticker,
                "Company":      info.get("longName", ticker),
                "Sector":       info.get("sector", "—"),
                "Price":        round(price, 2),
                "Target":       round(target_mean, 2),
                "Target High":  round(target_high, 2),
                "Target Low":   round(target_low, 2),
                "Upside %":     round(upside_pct, 1),
                "Rating":       round(float(rec_mean), 2),
                "Consensus":    consensus,
                "Analysts":     num_analysts,
                "RSI":          round(rsi, 1) if not np.isnan(rsi) else None,
                "SB Score":     round(sb_score, 1),
            })
        except Exception:
            continue

    progress.empty()
    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("SB Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


# ── Strong Sell scanner ────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_strong_sell_candidates(
    min_downside: float = 5.0,
    min_analysts: int = 5,
    min_rating: float = 3.5,
    top_n: int = 20,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for analyst sell / strong-sell consensus setups.

    yfinance recommendationMean scale:
      1.0 = Strong Buy · 2.0 = Buy · 3.0 = Hold · 4.0 = Sell · 5.0 = Strong Sell

    Strong Sell Score (max ~100)
    ─────────────────────────────
      Rating component   = (mean − 3.5) × 26.7    [max 40 at rating 5.0]
      Downside component = min(|downside %|, 50) × 0.5  [max 25]
      Analyst confidence = min(analysts, 20) × 1.5  [max 30]
      RSI overbought bonus = +5 if RSI > 60         [elevated = more likely to fall]
    """
    results  = []
    progress = st.empty()

    for idx, ticker in enumerate(SPX_TICKERS):
        progress.info(f"Scanning {ticker}… ({idx + 1}/{len(SPX_TICKERS)})")
        try:
            info = yf.Ticker(ticker).info

            rec_mean = info.get("recommendationMean")
            if rec_mean is None or float(rec_mean) < min_rating:
                continue

            num_analysts = int(info.get("numberOfAnalystOpinions") or 0)
            if num_analysts < min_analysts:
                continue

            target_mean = float(info.get("targetMeanPrice") or 0)
            target_high = float(info.get("targetHighPrice")  or 0)
            target_low  = float(info.get("targetLowPrice")   or 0)
            price       = float(
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or 0
            )

            if price <= 0 or target_mean <= 0:
                continue

            downside_pct = (target_mean - price) / price * 100  # negative = bearish
            if downside_pct > -min_downside:                     # must be negative enough
                continue

            # RSI-14
            end_dt   = datetime.today()
            start_dt = end_dt - timedelta(days=60)
            df = yf.download(
                ticker,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])

            rsi = np.nan
            if len(df) >= 14:
                delta    = df["Close"].diff()
                avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
                avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
                rs       = avg_gain / avg_loss.replace(0, np.nan)
                rsi      = float((100 - 100 / (1 + rs)).iloc[-1])

            # ── Strong Sell Score ──────────────────────────────────────────
            rating_score   = max(0.0, (float(rec_mean) - 3.5) * 26.7)    # max 40
            downside_score = min(abs(downside_pct), 50.0) * 0.5           # max 25
            analyst_score  = min(num_analysts, 20) * 1.5                  # max 30
            rsi_bonus      = 5.0 if (not np.isnan(rsi) and rsi > 60) else 0.0
            ss_score       = rating_score + downside_score + analyst_score + rsi_bonus

            # ── Consensus label ────────────────────────────────────────────
            if float(rec_mean) >= 4.5:
                consensus = "🔴 Strong Sell"
            elif float(rec_mean) >= 4.0:
                consensus = "🟠 Sell"
            else:
                consensus = "🟡 Moderate Sell"

            results.append({
                "Ticker":       ticker,
                "Company":      info.get("longName", ticker),
                "Sector":       info.get("sector", "—"),
                "Price":        round(price, 2),
                "Target":       round(target_mean, 2),
                "Target High":  round(target_high, 2),
                "Target Low":   round(target_low, 2),
                "Downside %":   round(downside_pct, 1),
                "Rating":       round(float(rec_mean), 2),
                "Consensus":    consensus,
                "Analysts":     num_analysts,
                "RSI":          round(rsi, 1) if not np.isnan(rsi) else None,
                "SS Score":     round(ss_score, 1),
            })
        except Exception:
            continue

    progress.empty()
    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("SS Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
