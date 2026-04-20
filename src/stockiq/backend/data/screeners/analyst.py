"""Analyst consensus buy/sell screeners for SPX_TICKERS."""

from ._shared import (
    ttl_cache, CACHE_TTL, SPX_TICKERS,
    np, pd, yf, datetime, timedelta,
    get_metadata, get_analyst_consensus,
    compute_rsi, _batch_download,
)


@ttl_cache(CACHE_TTL["fetch_strong_buy_scan"])
def fetch_strong_buy_scan(
    min_upside: float = 5.0,
    min_analysts: int = 5,
    max_rating: float = 2.5,
    top_n: int = 20,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for analyst strong-buy / buy consensus setups.

    Single batch OHLC download for price + RSI.
    GCS analyst consensus cache eliminates all per-ticker .info calls.
    Falls back to yfinance .info only for tickers missing from GCS.
    """
    results     = []
    gcs_meta    = get_metadata()
    gcs_analyst = get_analyst_consensus()

    end_dt   = datetime.today()
    start_dt = end_dt - timedelta(days=60)

    raw = _batch_download(
        SPX_TICKERS,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
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
            analyst = gcs_analyst.get(ticker)
            if analyst:
                rec_mean     = analyst.get("recommendationMean")
                num_analysts = int(analyst.get("numberOfAnalystOpinions") or 0)
                target_mean  = float(analyst.get("targetMeanPrice") or 0)
                target_high  = float(analyst.get("targetHighPrice")  or 0)
                target_low   = float(analyst.get("targetLowPrice")   or 0)
            else:
                info         = yf.Ticker(ticker).info
                rec_mean     = info.get("recommendationMean")
                num_analysts = int(info.get("numberOfAnalystOpinions") or 0)
                target_mean  = float(info.get("targetMeanPrice") or 0)
                target_high  = float(info.get("targetHighPrice")  or 0)
                target_low   = float(info.get("targetLowPrice")   or 0)

            if rec_mean is None or float(rec_mean) > max_rating:
                continue
            if num_analysts < min_analysts:
                continue
            if target_mean <= 0:
                continue

            df = _get_ticker_df(ticker)
            if df.empty:
                continue

            price = float(df["Close"].iloc[-1])
            if price <= 0:
                continue

            upside_pct = (target_mean - price) / price * 100
            if upside_pct < min_upside:
                continue

            rsi = float(compute_rsi(df).iloc[-1]) if len(df) >= 14 else np.nan

            rating_score  = max(0.0, (2.5 - float(rec_mean)) * 26.7)
            upside_score  = min(upside_pct, 50.0) * 0.5
            analyst_score = min(num_analysts, 20) * 1.5
            rsi_bonus     = 5.0 if (not np.isnan(rsi) and rsi < 60) else 0.0
            sb_score      = rating_score + upside_score + analyst_score + rsi_bonus

            if float(rec_mean) <= 1.5:
                consensus = "⭐ Strong Buy"
            elif float(rec_mean) <= 2.0:
                consensus = "🟢 Buy"
            else:
                consensus = "🟡 Moderate Buy"

            meta = gcs_meta.get(ticker)
            results.append({
                "Ticker":      ticker,
                "Company":     meta["name"]   if meta else ticker,
                "Sector":      meta["sector"] if meta else "—",
                "Price":       round(price, 2),
                "Target":      round(target_mean, 2),
                "Target High": round(target_high, 2),
                "Target Low":  round(target_low, 2),
                "Upside %":    round(upside_pct, 1),
                "Rating":      round(float(rec_mean), 2),
                "Consensus":   consensus,
                "Analysts":    num_analysts,
                "RSI":         round(rsi, 1) if not np.isnan(rsi) else None,
                "SB Score":    round(sb_score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("SB Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


@ttl_cache(CACHE_TTL["fetch_strong_sell_scan"])
def fetch_strong_sell_scan(
    min_downside: float = 0.0,
    min_analysts: int = 1,
    min_rating: float = 2.5,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for analyst sell / strong-sell consensus setups.

    Single batch OHLC download for price + RSI.
    GCS analyst consensus cache eliminates all per-ticker .info calls.
    Falls back to yfinance .info only for tickers missing from GCS.
    """
    results     = []
    gcs_meta    = get_metadata()
    gcs_analyst = get_analyst_consensus()

    end_dt   = datetime.today()
    start_dt = end_dt - timedelta(days=60)

    raw = _batch_download(
        SPX_TICKERS,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
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
            analyst = gcs_analyst.get(ticker)
            if analyst:
                rec_mean     = analyst.get("recommendationMean")
                num_analysts = int(analyst.get("numberOfAnalystOpinions") or 0)
                target_mean  = float(analyst.get("targetMeanPrice") or 0)
                target_high  = float(analyst.get("targetHighPrice")  or 0)
                target_low   = float(analyst.get("targetLowPrice")   or 0)
            else:
                info         = yf.Ticker(ticker).info
                rec_mean     = info.get("recommendationMean")
                num_analysts = int(info.get("numberOfAnalystOpinions") or 0)
                target_mean  = float(info.get("targetMeanPrice") or 0)
                target_high  = float(info.get("targetHighPrice")  or 0)
                target_low   = float(info.get("targetLowPrice")   or 0)

            if rec_mean is None or float(rec_mean) < min_rating:
                continue
            if num_analysts < min_analysts:
                continue
            if target_mean <= 0:
                continue

            df = _get_ticker_df(ticker)
            if df.empty:
                continue

            price = float(df["Close"].iloc[-1])
            if price <= 0:
                continue

            downside_pct = (target_mean - price) / price * 100
            if downside_pct > -min_downside:
                continue

            rsi = float(compute_rsi(df).iloc[-1]) if len(df) >= 14 else np.nan

            rating_score   = max(0.0, (float(rec_mean) - 3.5) * 26.7)
            downside_score = min(abs(downside_pct), 50.0) * 0.5
            analyst_score  = min(num_analysts, 20) * 1.5
            rsi_bonus      = 5.0 if (not np.isnan(rsi) and rsi > 60) else 0.0
            ss_score       = rating_score + downside_score + analyst_score + rsi_bonus

            if float(rec_mean) >= 4.5:
                consensus = "🔴 Strong Sell"
            elif float(rec_mean) >= 4.0:
                consensus = "🟠 Sell"
            elif float(rec_mean) >= 3.5:
                consensus = "🟡 Moderate Sell"
            elif float(rec_mean) >= 3.0:
                consensus = "⚪ Hold"
            else:
                consensus = "🔵 Cautious Hold"

            meta = gcs_meta.get(ticker)
            results.append({
                "Ticker":      ticker,
                "Company":     meta["name"]   if meta else ticker,
                "Sector":      meta["sector"] if meta else "—",
                "Price":       round(price, 2),
                "Target":      round(target_mean, 2),
                "Target High": round(target_high, 2),
                "Target Low":  round(target_low, 2),
                "Downside %":  round(downside_pct, 1),
                "Rating":      round(float(rec_mean), 2),
                "Consensus":   consensus,
                "Analysts":    num_analysts,
                "RSI":         round(rsi, 1) if not np.isnan(rsi) else None,
                "SS Score":    round(ss_score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("SS Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
