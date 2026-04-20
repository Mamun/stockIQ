"""Weekly/monthly candle momentum screener for SPX_TICKERS."""

from ._shared import (
    ttl_cache, CACHE_TTL, SPX_TICKERS,
    np, pd, yf, datetime, timedelta,
    get_metadata, _batch_download, _rsi_last,
)


@ttl_cache(CACHE_TTL["fetch_candle_momentum_scan"])
def fetch_candle_momentum_scan() -> pd.DataFrame:
    """
    Weekly/monthly candle screener for SPX_TICKERS.

    Per ticker:
      • 4-week & 4-month green candle counts → 5-tier signal (Strong Buy → Sell)
      • 1W / 1M / 3M price returns + performance vs SPY (1M relative strength)
      • Volume trend (5-day avg vs 20-day avg)
      • RSI-14
      • Sector

    Performance: all tickers downloaded in one batch call; company name + sector
    served from GCS metadata cache (immutable) — no per-ticker .info calls needed.
    """
    recommendations = []
    gcs_meta = get_metadata()

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=270)
    start_str  = start_date.strftime("%Y-%m-%d")
    end_str    = end_date.strftime("%Y-%m-%d")

    all_tickers = ["SPY"] + SPX_TICKERS
    raw = _batch_download(
        all_tickers,
        start=start_str,
        end=end_str,
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

    spx_ret_1m = 0.0
    spx_df = _get_ticker_df("SPY")
    if len(spx_df) >= 22:
        spx_ret_1m = (
            (float(spx_df["Close"].iloc[-1]) - float(spx_df["Close"].iloc[-22]))
            / float(spx_df["Close"].iloc[-22]) * 100
        )

    for ticker in SPX_TICKERS:
        try:
            df = _get_ticker_df(ticker)
            if df.empty or len(df) < 20:
                continue

            meta = gcs_meta.get(ticker)
            if meta:
                company_name = meta["name"]
                sector       = meta["sector"]
            else:
                info         = yf.Ticker(ticker).info
                company_name = info.get("longName", ticker)
                sector       = info.get("sector", "—")

            last_price = float(df["Close"].iloc[-1])

            def _ret(n: int) -> float | None:
                if len(df) > n:
                    prev = float(df["Close"].iloc[-(n + 1)])
                    return (last_price - prev) / prev * 100
                return None

            ret_1w = _ret(5)
            ret_1m = _ret(21)
            ret_3m = _ret(63)
            vs_spx = round(ret_1m - spx_ret_1m, 1) if ret_1m is not None else None

            avg_vol_5  = float(df["Volume"].tail(5).mean())
            avg_vol_20 = float(df["Volume"].tail(20).mean())
            if avg_vol_20 > 0:
                ratio     = avg_vol_5 / avg_vol_20
                vol_trend = "🔼" if ratio > 1.1 else "🔽" if ratio < 0.9 else "➡️"
            else:
                vol_trend = "—"

            rsi = _rsi_last(df)

            weekly_df    = df[["Open", "Close"]].resample("W").agg({"Open": "first", "Close": "last"})
            w4           = weekly_df.tail(4)
            weekly_green = sum(1 for _, r in w4.iterrows() if r["Close"] > r["Open"])
            weekly_dots  = ["🟢" if r["Close"] > r["Open"] else "🔴" for _, r in w4.iterrows()]

            monthly_df    = df[["Open", "Close"]].resample("ME").agg({"Open": "first", "Close": "last"})
            m4            = monthly_df.tail(4)
            monthly_green = sum(1 for _, r in m4.iterrows() if r["Close"] > r["Open"])
            monthly_dots  = ["🟢" if r["Close"] > r["Open"] else "🔴" for _, r in m4.iterrows()]

            if weekly_green == 4 and monthly_green == 4:
                signal, sig_order = "🟢 Strong Buy", 1
            elif weekly_green == 4 and monthly_green >= 3:
                signal, sig_order = "🟢 Buy", 2
            elif weekly_green >= 3 and monthly_green >= 3:
                signal, sig_order = "🟡 Accumulate", 3
            elif weekly_green >= 2:
                signal, sig_order = "🟠 Caution", 4
            else:
                signal, sig_order = "🔴 Sell", 5

            recommendations.append({
                "Ticker":    ticker,
                "Company":   company_name,
                "Sector":    sector,
                "Price":     round(last_price, 2),
                "1W %":      round(ret_1w, 1) if ret_1w is not None else None,
                "1M %":      round(ret_1m, 1) if ret_1m is not None else None,
                "3M %":      round(ret_3m, 1) if ret_3m is not None else None,
                "vs SPX":    vs_spx,
                "Vol":       vol_trend,
                "RSI":       round(rsi, 1),
                "🔷 Weeks":  " ".join(weekly_dots),
                "W Score":   f"{weekly_green}/4",
                "🔶 Months": " ".join(monthly_dots),
                "M Score":   f"{monthly_green}/4",
                "Signal":    signal,
                "_order":    sig_order,
                "Strength":  weekly_green + monthly_green,
            })
        except Exception:
            continue

    if not recommendations:
        return pd.DataFrame()

    return (
        pd.DataFrame(recommendations)
        .sort_values(["_order", "Strength"], ascending=[True, False])
        .reset_index(drop=True)
    )
