"""Price-momentum screeners: bounce radar, NASDAQ RSI, premarket movers."""

from ._shared import (
    ttl_cache, CACHE_TTL, SPX_TICKERS, NASDAQ_100_TICKERS,
    np, pd, yf, datetime, timedelta, compute_rsi,
    get_metadata, _batch_download, _rsi_last, _NASDAQ_COMPANY_NAMES,
)


@ttl_cache(CACHE_TTL["fetch_bounce_radar_scan"])
def fetch_bounce_radar_scan(threshold_pct: float = 5.0, top_n: int = 30) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for stocks within ±threshold_pct of their 200-day MA.
    Bounce score rewards: proximity to MA200 + oversold RSI + below-MA200 support.
    Returns top_n rows sorted by bounce score descending.

    Uses a single batch OHLC download (no per-ticker calls) + GCS metadata for names.
    """
    results  = []
    gcs_meta = get_metadata()

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=320)

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
            if df.empty or len(df) < 201:
                continue

            price = float(df["Close"].iloc[-1])
            ma200 = float(df["Close"].rolling(200).mean().iloc[-1])
            ma50  = float(df["Close"].rolling(50).mean().iloc[-1])

            if np.isnan(ma200):
                continue

            dist_pct = (price - ma200) / ma200 * 100
            if abs(dist_pct) > threshold_pct:
                continue

            rsi   = _rsi_last(df)
            trend = "📈 Uptrend" if ma50 > ma200 else "📉 Downtrend"

            proximity_bonus = (threshold_pct - abs(dist_pct)) * 2
            oversold_bonus  = max(0, 50 - rsi)
            support_bonus   = 8 if dist_pct < 0 else 0
            bounce_score    = proximity_bonus + oversold_bonus + support_bonus

            if rsi <= 30:
                rsi_label = "🟢 Oversold"
            elif rsi >= 70:
                rsi_label = "🔴 Overbought"
            else:
                rsi_label = "⚪ Neutral"

            meta         = gcs_meta.get(ticker)
            company_name = meta["name"] if meta else ticker

            results.append({
                "Ticker":       ticker,
                "Company":      company_name,
                "Price":        round(price, 2),
                "MA 200":       round(ma200, 2),
                "Distance %":   round(dist_pct, 2),
                "RSI":          round(rsi, 1),
                "RSI Zone":     rsi_label,
                "Trend":        trend,
                "Bounce Score": round(bounce_score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Bounce Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


@ttl_cache(CACHE_TTL["fetch_nasdaq_rsi_scan"])
def fetch_nasdaq_rsi_scan() -> pd.DataFrame:
    """
    Scan all NASDAQ-100 stocks in a single batch download.
    Returns every stock with RSI, moving averages, trend, day change,
    volume ratio, and overbought/oversold status.
    """
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=300)
    tickers    = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]

    raw = _batch_download(
        tickers,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if raw.empty:
        return pd.DataFrame()

    try:
        is_multi  = isinstance(raw.columns, pd.MultiIndex)
        close_df  = raw["Close"]  if is_multi else raw
        volume_df = raw["Volume"] if is_multi else None
    except Exception:
        return pd.DataFrame()

    results = []
    for ticker in NASDAQ_100_TICKERS:
        try:
            if not isinstance(ticker, str) or ticker not in close_df.columns:
                continue
            closes = close_df[ticker].dropna()
            if len(closes) < 15:
                continue

            price = float(closes.iloc[-1])
            rsi   = float(compute_rsi(closes.to_frame("Close")).iloc[-1])

            ma50  = float(closes.iloc[-50:].mean())  if len(closes) >= 50  else None
            ma200 = float(closes.iloc[-200:].mean()) if len(closes) >= 200 else None

            pct_ma50  = round((price - ma50)  / ma50  * 100, 1) if ma50  else None
            pct_ma200 = round((price - ma200) / ma200 * 100, 1) if ma200 else None

            day_chg = round((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2) \
                      if len(closes) >= 2 else None

            if ma50 and ma200:
                trend = "📈 Uptrend" if ma50 > ma200 else "📉 Downtrend"
            else:
                trend = "—"

            vol_ratio = None
            if volume_df is not None and ticker in volume_df.columns:
                vols = volume_df[ticker].dropna()
                if len(vols) >= 21:
                    avg_vol   = float(vols.iloc[-21:-1].mean())
                    today_vol = float(vols.iloc[-1])
                    vol_ratio = round(today_vol / avg_vol, 2) if avg_vol > 0 else None

            if rsi >= 70:
                status = "🔴 Overbought"
            elif rsi <= 30:
                status = "🟢 Oversold"
            else:
                status = "⚪ Neutral"

            results.append({
                "Ticker":     ticker,
                "Price":      round(price, 2),
                "Day Chg %":  day_chg,
                "RSI":        round(rsi, 1),
                "% vs MA50":  pct_ma50,
                "% vs MA200": pct_ma200,
                "Trend":      trend,
                "Vol Ratio":  vol_ratio,
                "Status":     status,
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("RSI", ascending=False)
        .reset_index(drop=True)
    )


@ttl_cache(CACHE_TTL["fetch_premarket_scan"])
def fetch_premarket_scan() -> pd.DataFrame:
    """Scans NASDAQ-100 for today's pre-market movers."""
    tickers = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]

    try:
        daily = yf.download(tickers, period="12d", auto_adjust=True, progress=False)
    except Exception:
        return pd.DataFrame()

    if daily.empty:
        return pd.DataFrame()

    is_d         = isinstance(daily.columns, pd.MultiIndex)
    daily_close  = daily["Close"]  if is_d else daily
    daily_volume = daily["Volume"] if is_d else None

    intra_close  = pd.DataFrame()
    intra_volume = pd.DataFrame()
    try:
        intra = yf.download(
            tickers, period="2d", interval="5m",
            prepost=True, auto_adjust=True, progress=False,
        )
        if not intra.empty:
            is_i         = isinstance(intra.columns, pd.MultiIndex)
            intra_close  = intra["Close"]  if is_i else intra
            intra_volume = intra["Volume"] if is_i else pd.DataFrame()
    except Exception:
        pass

    pm_close_df  = pd.DataFrame()
    pm_volume_df = pd.DataFrame()

    if not intra_close.empty:
        now_et    = pd.Timestamp.now(tz="America/New_York")
        today_str = now_et.strftime("%Y-%m-%d")
        idx       = intra_close.index
        idx_et    = (
            idx.tz_convert("America/New_York") if idx.tzinfo is not None
            else idx.tz_localize("UTC").tz_convert("America/New_York")
        )
        pm_mask = (
            (idx_et.strftime("%Y-%m-%d") == today_str) &
            (idx_et.hour >= 4) &
            ((idx_et.hour < 9) | ((idx_et.hour == 9) & (idx_et.minute < 30)))
        )
        pm_close_df = intra_close[pm_mask]
        if not intra_volume.empty:
            pm_volume_df = intra_volume[pm_mask]

    results = []
    for ticker in tickers:
        try:
            if ticker not in daily_close.columns:
                continue
            d_closes = daily_close[ticker].dropna()
            if len(d_closes) < 2:
                continue

            prev_close = float(d_closes.iloc[-1])
            ref        = float(d_closes.iloc[max(0, len(d_closes) - 8)])
            chg_7d     = round((prev_close - ref) / ref * 100, 2) if ref > 0 else None

            avg_dvol = None
            if daily_volume is not None and ticker in daily_volume.columns:
                dvols = daily_volume[ticker].dropna()
                if len(dvols) >= 5:
                    avg_dvol = float(dvols.iloc[-10:].mean())

            pm_price   = None
            pm_chg     = None
            pm_vol_pct = None

            if not pm_close_df.empty and ticker in pm_close_df.columns:
                pm_bars = pm_close_df[ticker].dropna()
                if not pm_bars.empty:
                    pm_price = round(float(pm_bars.iloc[-1]), 2)
                    pm_chg   = round((pm_price - prev_close) / prev_close * 100, 2)
                    if not pm_volume_df.empty and ticker in pm_volume_df.columns:
                        pm_vol = float(pm_volume_df[ticker].fillna(0).sum())
                        if avg_dvol and avg_dvol > 0:
                            pm_vol_pct = round(pm_vol / avg_dvol * 100, 1)

            results.append({
                "Ticker":     ticker,
                "PM Price":   pm_price,
                "PM Chg %":   pm_chg,
                "PM Vol %":   pm_vol_pct,
                "Prev Close": round(prev_close, 2),
                "7D Chg %":   chg_7d,
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df["_has_pm"]  = df["PM Chg %"].notna().astype(int)
    df["_abs_chg"] = pd.to_numeric(df["PM Chg %"], errors="coerce").abs().fillna(-1)
    df = (
        df.sort_values(["_has_pm", "_abs_chg"], ascending=[False, False])
          .drop(columns=["_has_pm", "_abs_chg"])
          .reset_index(drop=True)
    )
    df.insert(1, "Company", df["Ticker"].map(_NASDAQ_COMPANY_NAMES).fillna("—"))
    return df


@ttl_cache(CACHE_TTL["fetch_premarket_history"])
def fetch_premarket_history() -> pd.DataFrame:
    """Returns the last 7 trading days of daily close prices for all NASDAQ-100 stocks."""
    tickers = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]
    try:
        raw = yf.download(tickers, period="12d", auto_adjust=True, progress=False)
    except Exception:
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()

    is_multi = isinstance(raw.columns, pd.MultiIndex)
    close_df = raw["Close"] if is_multi else raw
    close_df = close_df.dropna(how="all").tail(7)
    close_df.index = pd.to_datetime(close_df.index).strftime("%b %d")

    result = close_df.T.round(2)
    result.index.name = "Ticker"
    return result
