"""ETF momentum/RSI/MA scanner."""

from ._shared import (
    ttl_cache, CACHE_TTL, ETF_UNIVERSE,
    np, pd, yf, datetime, timedelta,
    _rsi_last,
)


@ttl_cache(CACHE_TTL["fetch_etf_scan"])
def fetch_etf_scan(categories: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Scan ETF_UNIVERSE for momentum, RSI, MA crossover, and volume signals."""
    etfs = ETF_UNIVERSE
    if categories:
        etfs = [e for e in etfs if e["category"] in categories]

    tickers = [e["ticker"] for e in etfs]
    meta    = {e["ticker"]: e for e in etfs}

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=320)

    raw = yf.download(
        tickers,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
    )

    spy_ret_1m = 0.0
    try:
        if "SPY" in tickers:
            spy_close = raw["SPY"]["Close"].dropna()
        else:
            spy_raw   = yf.download("SPY", start=start_date.strftime("%Y-%m-%d"),
                                    end=end_date.strftime("%Y-%m-%d"),
                                    progress=False, auto_adjust=True)
            spy_close = spy_raw["Close"].dropna()
        if len(spy_close) >= 22:
            spy_ret_1m = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-22])) / float(spy_close.iloc[-22]) * 100
    except Exception:
        pass

    results = []
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = raw.copy()
            else:
                df = raw[ticker].copy()

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 22:
                continue

            price = float(df["Close"].iloc[-1])

            def _ret(n: int) -> float | None:
                if len(df) > n:
                    prev = float(df["Close"].iloc[-(n + 1)])
                    return (price - prev) / prev * 100
                return None

            ret_1d = _ret(1)
            ret_1w = _ret(5)
            ret_1m = _ret(21)
            ret_3m = _ret(63)
            vs_spy = round(ret_1m - spy_ret_1m, 1) if ret_1m is not None else None

            rsi = _rsi_last(df)

            ma20  = float(df["Close"].rolling(20).mean().iloc[-1])  if len(df) >= 20  else None
            ma50  = float(df["Close"].rolling(50).mean().iloc[-1])  if len(df) >= 50  else None
            ma200 = float(df["Close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

            if ma20 is not None and ma50 is not None and not np.isnan(ma20) and not np.isnan(ma50):
                ma_cross = "🟢 Bullish" if ma20 > ma50 else "🔴 Bearish"
            else:
                ma_cross = "—"

            ma200_dist = round((price - ma200) / ma200 * 100, 1) if ma200 and not np.isnan(ma200) else None

            avg_vol_5  = float(df["Volume"].tail(5).mean())
            avg_vol_20 = float(df["Volume"].tail(20).mean())
            vol_ratio  = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0
            vol_surge  = "🔼" if vol_ratio > 1.2 else "🔽" if vol_ratio < 0.8 else "➡️"

            if rsi <= 30:
                rsi_zone = "🟢 Oversold"
            elif rsi >= 70:
                rsi_zone = "🔴 Overbought"
            elif rsi <= 45:
                rsi_zone = "🟡 Weak"
            elif rsi >= 55:
                rsi_zone = "🔵 Strong"
            else:
                rsi_zone = "⚪ Neutral"

            score = 50.0
            if ret_1m is not None:
                score += min(ret_1m * 1.5, 15)
            if vs_spy is not None:
                score += min(vs_spy * 1.0, 10)
            if rsi <= 40:
                score += 10
            elif rsi >= 70:
                score -= 10
            if ma_cross == "🟢 Bullish":
                score += 10
            elif ma_cross == "🔴 Bearish":
                score -= 10
            if vol_ratio > 1.2:
                score += 5

            results.append({
                "Ticker":      ticker,
                "Name":        meta[ticker]["name"],
                "Category":    meta[ticker]["category"],
                "Price":       round(price, 2),
                "1D %":        round(ret_1d, 2) if ret_1d is not None else None,
                "1W %":        round(ret_1w, 1) if ret_1w is not None else None,
                "1M %":        round(ret_1m, 1) if ret_1m is not None else None,
                "3M %":        round(ret_3m, 1) if ret_3m is not None else None,
                "vs SPY":      vs_spy,
                "RSI":         round(rsi, 1),
                "RSI Zone":    rsi_zone,
                "MA Signal":   ma_cross,
                "MA200 Dist%": ma200_dist,
                "Vol":         vol_surge,
                "ETF Score":   round(score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("ETF Score", ascending=False)
        .reset_index(drop=True)
    )
