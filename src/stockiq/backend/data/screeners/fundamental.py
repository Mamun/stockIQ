"""Munger-style fundamental quality screener for SPX_TICKERS."""

from ._shared import (
    ttl_cache, CACHE_TTL, SPX_TICKERS,
    np, pd, yf, datetime, timedelta,
    get_metadata, get_fundamentals, _batch_download, _rsi_last,
)


def _quality_score(info: dict) -> tuple[float, list[str]]:
    """Score a stock's fundamental quality (Munger-style). Returns (score 0–85, breakdown)."""
    score     = 0.0
    breakdown: list[str] = []

    roe = info.get("returnOnEquity")
    if roe is not None:
        roe_pct = roe * 100
        pts = 25.0 if roe_pct >= 20 else 18.0 if roe_pct >= 15 else 10.0 if roe_pct >= 10 else 5.0 if roe_pct > 0 else 0.0
        score += pts
        breakdown.append(f"ROE {roe_pct:.1f}% → {pts:.0f}/25")

    pm = info.get("profitMargins")
    if pm is not None:
        pm_pct = pm * 100
        pts = 20.0 if pm_pct >= 20 else 14.0 if pm_pct >= 10 else 8.0 if pm_pct >= 5 else 3.0 if pm_pct > 0 else 0.0
        score += pts
        breakdown.append(f"Profit Margin {pm_pct:.1f}% → {pts:.0f}/20")

    rg = info.get("revenueGrowth")
    if rg is not None:
        rg_pct = rg * 100
        pts = 15.0 if rg_pct >= 15 else 10.0 if rg_pct >= 8 else 6.0 if rg_pct >= 3 else 2.0 if rg_pct >= 0 else 0.0
        score += pts
        breakdown.append(f"Revenue Growth {rg_pct:.1f}% → {pts:.0f}/15")

    de = info.get("debtToEquity")
    if de is not None:
        de_ratio = de / 100.0
        pts = 15.0 if de_ratio < 0.3 else 10.0 if de_ratio < 0.7 else 5.0 if de_ratio < 1.5 else 0.0
        score += pts
        breakdown.append(f"D/E {de_ratio:.2f}× → {pts:.0f}/15")

    eg = info.get("earningsGrowth")
    if eg is not None:
        eg_pct = eg * 100
        pts = 10.0 if eg_pct >= 15 else 7.0 if eg_pct >= 8 else 3.0 if eg_pct >= 0 else 0.0
        score += pts
        breakdown.append(f"EPS Growth {eg_pct:.1f}% → {pts:.0f}/10")

    return score, breakdown


def _proximity_score(dist_pct: float) -> int:
    """Points for proximity to 200-week MA. Closer = higher score (max 15)."""
    abs_d = abs(dist_pct)
    if abs_d <= 2:   return 15
    if abs_d <= 5:   return 12
    if abs_d <= 10:  return 8
    if abs_d <= 15:  return 4
    if abs_d <= 20:  return 2
    return 0


@ttl_cache(CACHE_TTL["fetch_munger_strategy_scan"])
def fetch_munger_strategy_scan(
    threshold_pct: float = 15.0,
    min_quality: float = 30.0,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for Charlie Munger-style setups.
    Munger Score = Quality Score (0–85) + Proximity Score (0–15). Max = 100.

    Single batch OHLC download (1600 days all tickers) + GCS fundamentals cache.
    Falls back to yfinance .info only for tickers missing from GCS.
    """
    results   = []
    gcs_meta  = get_metadata()
    gcs_funds = get_fundamentals()

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=1600)

    raw = _batch_download(
        SPX_TICKERS,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
    )
    if raw.empty:
        return pd.DataFrame()

    def _get_ticker_df(ticker: str) -> pd.DataFrame:
        try:
            df = raw[ticker].copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df.dropna(subset=["Close"])
        except Exception:
            return pd.DataFrame()

    for ticker in SPX_TICKERS:
        try:
            df = _get_ticker_df(ticker)
            if df.empty or len(df) < 200:
                continue

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

            fund = gcs_funds.get(ticker)
            if fund:
                q_score, breakdown = _quality_score(fund)
            else:
                info               = yf.Ticker(ticker).info
                q_score, breakdown = _quality_score(info)

            if q_score < min_quality:
                continue

            prox_score   = _proximity_score(dist_pct)
            munger_score = q_score + prox_score
            rsi          = _rsi_last(df)

            meta = gcs_meta.get(ticker)
            results.append({
                "Ticker":        ticker,
                "Company":       meta["name"]   if meta else ticker,
                "Sector":        meta["sector"] if meta else "—",
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

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Munger Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
