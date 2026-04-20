"""Short-squeeze screener for SPX_TICKERS."""

from ._shared import (
    ttl_cache, CACHE_TTL, SPX_TICKERS,
    np, pd, yf, datetime, timedelta,
    get_metadata, get_short_interest, _batch_download, _rsi_last,
)


@ttl_cache(CACHE_TTL["fetch_squeeze_scan"])
def fetch_squeeze_scan(
    rsi_min: float = 55.0,
    min_short_float: float = 0.5,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for potential short-squeeze setups:
      • RSI ≥ rsi_min              — stock extended (shorts under pressure)
      • Short % of Float ≥ min_short_float — meaningful short interest

    Uses a single batch OHLC download for RSI + GCS short interest cache.
    Falls back to yfinance .info only for tickers missing from GCS cache.
    """
    results   = []
    gcs_meta  = get_metadata()
    gcs_short = get_short_interest()

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=90)

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
            if df.empty or len(df) < 14:
                continue

            rsi = _rsi_last(df)
            if np.isnan(rsi) or rsi < rsi_min:
                continue

            si = gcs_short.get(ticker)
            if si:
                raw_spf       = si["shortPercentOfFloat"]
                short_pct_flt = raw_spf * 100.0 if raw_spf <= 1.0 else raw_spf
                short_ratio   = float(si["shortRatio"])
                shares_short  = int(si["sharesShort"])
                shares_prior  = int(si["sharesShortPriorMonth"])
            else:
                info          = yf.Ticker(ticker).info
                raw_spf       = info.get("shortPercentOfFloat") or 0.0
                short_pct_flt = raw_spf * 100.0
                short_ratio   = float(info.get("shortRatio")            or 0.0)
                shares_short  = int(  info.get("sharesShort")           or 0)
                shares_prior  = int(  info.get("sharesShortPriorMonth") or 0)

            if short_pct_flt < min_short_float:
                continue

            price        = float(df["Close"].iloc[-1])
            meta         = gcs_meta.get(ticker)
            company_name = meta["name"] if meta else ticker

            short_change_pct = (
                (shares_short - shares_prior) / shares_prior * 100
                if shares_prior > 0 else 0.0
            )

            rsi_score = max(0.0, (rsi - 50.0)) * 0.4

            if short_pct_flt >= 5:
                float_score = 40.0
            elif short_pct_flt >= 3:
                float_score = 25.0
            elif short_pct_flt >= 1.5:
                float_score = 15.0
            else:
                float_score = short_pct_flt * 8.0

            if short_ratio >= 10:
                ratio_score = 20.0
            elif short_ratio >= 5:
                ratio_score = 12.0
            elif short_ratio >= 2:
                ratio_score = 6.0
            else:
                ratio_score = short_ratio * 2.0

            build_score   = 5.0 if short_change_pct > 0 else 0.0
            squeeze_score = rsi_score + float_score + ratio_score + build_score

            if rsi >= 80:
                rsi_zone = "🔴 Extreme OB"
            elif rsi >= 70:
                rsi_zone = "🟠 Overbought"
            else:
                rsi_zone = "🟡 Elevated"

            results.append({
                "Ticker":          ticker,
                "Company":         company_name,
                "Price":           round(price, 2),
                "RSI":             round(rsi, 1),
                "RSI Zone":        rsi_zone,
                "Short % Float":   round(short_pct_flt, 1),
                "Days to Cover":   round(short_ratio, 1),
                "Short Chg % MoM": round(short_change_pct, 1),
                "Squeeze Score":   round(squeeze_score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Squeeze Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
