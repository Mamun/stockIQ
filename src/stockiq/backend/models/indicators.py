import pandas as pd
import numpy as np

from stockiq.backend.config import MA_PERIODS, FIB_LEVELS


def compute_mas(df: pd.DataFrame) -> pd.DataFrame:
    for p in MA_PERIODS:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    return df


def compute_weekly_ma200(daily_df: pd.DataFrame) -> pd.Series:
    """
    Resample daily Close to weekly (Friday close), compute 200-week rolling mean,
    then forward-fill back onto the daily index.
    Returns a daily-indexed Series named 'MA200W'.
    """
    weekly_close = daily_df["Close"].resample("W").last()
    weekly_ma200 = weekly_close.rolling(200).mean()
    daily_ma200w = weekly_ma200.reindex(daily_df.index, method="ffill")
    daily_ma200w.name = "MA200W"
    return daily_ma200w


def compute_fibonacci(df: pd.DataFrame) -> dict[str, float]:
    """Fibonacci retracement on the 200-session range visible in the data."""
    window = df.tail(200)
    high = window["Close"].max()
    low  = window["Close"].min()
    diff = high - low
    return {f"{int(lvl * 100)}%": high - diff * lvl for lvl in FIB_LEVELS}


def compute_daily_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily gaps (current open vs previous close) and whether filled within 3 days."""
    if df.empty or not {"Open", "Close", "High", "Low"}.issubset(df.columns):
        return pd.DataFrame()
    cols = ["Open", "Close", "High", "Low"] + (["Volume"] if "Volume" in df.columns else [])
    df_gap = df[cols].copy()
    df_gap["Prev Close"] = df_gap["Close"].shift(1)
    df_gap["Gap"] = df_gap["Open"] - df_gap["Prev Close"]
    df_gap["Gap %"] = (df_gap["Gap"] / df_gap["Prev Close"] * 100).round(2)

    gap_filled_list = []
    for i in range(len(df_gap)):
        gap = df_gap.iloc[i]["Gap"]
        prev_close = df_gap.iloc[i]["Prev Close"]

        if pd.isna(gap) or pd.isna(prev_close) or gap == 0:
            gap_filled_list.append(False)
            continue

        is_filled = False
        gap_direction = 1 if gap > 0 else -1

        for j in range(i, min(i + 4, len(df_gap))):
            high = df_gap.iloc[j]["High"]
            low  = df_gap.iloc[j]["Low"]
            if gap_direction > 0:
                if low <= prev_close:
                    is_filled = True
                    break
            else:
                if high >= prev_close:
                    is_filled = True
                    break

        gap_filled_list.append(is_filled)

    n = len(df_gap)
    df_gap["Gap Filled"]    = gap_filled_list
    # Confirmed when: filled intraday or on a subsequent bar, OR 2+ future bars checked (i <= n-3).
    df_gap["Gap Confirmed"] = [
        gap_filled_list[i] or (i <= n - 3)
        for i in range(n)
    ]
    df_gap["Open"]       = df_gap["Open"].round(2)
    df_gap["Close"]      = df_gap["Close"].round(2)
    df_gap["Prev Close"] = df_gap["Prev Close"].round(2)
    df_gap["Gap"]        = df_gap["Gap"].round(2)
    return df_gap.dropna(subset=["Prev Close"])


def patch_today_gap(gaps_df: pd.DataFrame, quote: dict) -> pd.DataFrame:
    """Patch today's gap row with live intraday fill status.

    Historical OHLC data has no future bars for the current session, so gap fill
    is always shown as Pending/Unknown. This uses fast_info day_high/day_low to
    determine in real-time whether today's gap has been touched.

    Note: Open and Prev Close are intentionally left as-is from the historical
    OHLC data so all rows use a single consistent data source for gap amounts.
    fast_info.previous_close can diverge from the historical regular-session close
    (e.g. due to extended-hours trades), which would make today's gap inconsistent
    with every other row in the table.
    """
    if gaps_df.empty:
        return gaps_df

    day_high = quote.get("day_high") or 0
    day_low  = quote.get("day_low")  or 0
    if not day_high or not day_low:
        return gaps_df

    gaps_df  = gaps_df.copy()
    last_idx = gaps_df.index[-1]
    gap        = float(gaps_df.at[last_idx, "Gap"])
    prev_close = float(gaps_df.at[last_idx, "Prev Close"])

    if pd.isna(gap) or gap == 0 or pd.isna(prev_close):
        return gaps_df

    is_filled = (day_low <= prev_close) if gap > 0 else (day_high >= prev_close)
    gaps_df.at[last_idx, "Gap Filled"]    = is_filled
    gaps_df.at[last_idx, "Gap Confirmed"] = True
    return gaps_df


def compute_buying_pressure(df: pd.DataFrame, timeframe: str = "monthly") -> dict:
    """
    Buying Pressure (BX) signal — detects selling exhaustion and onset of real buying.

    Three conditions (2/3 = signal, 3/3 = strong signal):
      1. RSI turning up from oversold  (RSI < 45 and rising vs previous bar)
      2. Volume surge                  (current bar > 1.5× trailing 20-bar average)
      3. Bullish close                 (candle closes in upper 60% of High–Low range)

    timeframe: 'monthly' | 'weekly' | 'daily'
    """
    freq_map = {"monthly": "MS", "weekly": "W-FRI"}
    freq = freq_map.get(timeframe)

    if freq:
        agg_spec = {k: v for k, v in {
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum",
        }.items() if k in df.columns}
        bars = df.resample(freq).agg(agg_spec).dropna(subset=["Close"])

        # Drop the current incomplete bar — signal must be based on a finished period
        today = pd.Timestamp.today().normalize()
        last_period = bars.index[-1].to_period(
            "M" if timeframe == "monthly" else "W"
        )
        current_period = today.to_period(
            "M" if timeframe == "monthly" else "W"
        )
        if last_period >= current_period:
            bars = bars.iloc[:-1]
    else:
        bars = df.copy()

    if len(bars) < 22:
        return {"signal": False, "strength": 0,
                "conditions_met": [], "conditions_missing": [],
                "timeframe": timeframe, "rsi": None}

    bars = bars.copy()
    bars["RSI"] = compute_rsi(bars)
    if "Volume" in bars.columns:
        bars["_vol_ma20"] = bars["Volume"].rolling(20).mean()

    latest = bars.iloc[-1]
    prev   = bars.iloc[-2]

    met     = []
    missing = []

    # 1. RSI turning up from oversold
    rsi_now  = latest.get("RSI", np.nan)
    rsi_prev = prev.get("RSI",   np.nan)
    if not (np.isnan(rsi_now) or np.isnan(rsi_prev)):
        if rsi_now < 45 and rsi_now > rsi_prev:
            met.append(f"RSI turning up from oversold ({rsi_now:.1f} ↑ from {rsi_prev:.1f})")
        elif rsi_now >= 45:
            missing.append(f"RSI not oversold ({rsi_now:.1f} — needs < 45)")
        else:
            missing.append(f"RSI still falling ({rsi_now:.1f} ↓ from {rsi_prev:.1f})")

    # 2. Volume surge
    if "Volume" in bars.columns:
        vol_now = latest.get("Volume",    np.nan)
        vol_avg = latest.get("_vol_ma20", np.nan)
        if not (np.isnan(vol_now) or np.isnan(vol_avg)) and vol_avg > 0:
            ratio = vol_now / vol_avg
            if ratio >= 1.5:
                met.append(f"Volume surge ({ratio:.1f}× average)")
            else:
                missing.append(f"Volume below threshold ({ratio:.1f}× avg — needs 1.5×)")

    # 3. Bullish close (close in upper 60% of candle range)
    h, lo, c = float(latest["High"]), float(latest["Low"]), float(latest["Close"])
    rng = h - lo
    if rng > 0:
        pos = (c - lo) / rng
        if pos >= 0.60:
            met.append(f"Bullish close — {pos * 100:.0f}% up the candle range")
        else:
            missing.append(f"Weak close — {pos * 100:.0f}% up range (needs ≥ 60%)")

    strength  = len(met)
    bar_label = bars.index[-1].strftime("%b %Y" if timeframe == "monthly" else "%d %b %Y")
    return {
        "signal":             strength >= 2,
        "strength":           strength,
        "conditions_met":     met,
        "conditions_missing": missing,
        "timeframe":          timeframe,
        "rsi":                rsi_now if not np.isnan(rsi_now) else None,
        "bar_label":          bar_label,
    }


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder's RSI.  Returns a Series named 'RSI' aligned to df.index.
    >70 = overbought, <30 = oversold.
    """
    delta    = df["Close"].diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi      = 100 - (100 / (1 + rs))
    rsi.name = "RSI"
    return rsi


def detect_reversal_patterns(df: pd.DataFrame) -> pd.DataFrame:
    o, h, lo, c = df["Open"], df["High"], df["Low"], df["Close"]
    max_oc = pd.concat([o, c], axis=1).max(axis=1)
    min_oc = pd.concat([o, c], axis=1).min(axis=1)
    body       = max_oc - min_oc
    upper_wick = h - max_oc
    lower_wick = min_oc - lo
    full_range = h - lo
    bullish_c  = c > o
    bearish_c  = c < o

    # Hammer: small body near top, lower wick ≥ 2× body, tiny upper wick
    df["pat_hammer"] = (
        (body > 0) &
        (lower_wick >= 2 * body) &
        (upper_wick <= 0.25 * body)
    )

    # Shooting Star: small body near bottom, upper wick ≥ 2× body, tiny lower wick
    df["pat_shoot_star"] = (
        (body > 0) &
        (upper_wick >= 2 * body) &
        (lower_wick <= 0.25 * body)
    )

    prev_max = max_oc.shift(1)
    prev_min = min_oc.shift(1)

    # Bullish Engulfing
    df["pat_bull_engulf"] = (
        bullish_c &
        bearish_c.shift(1) &
        (o < prev_min) &
        (c > prev_max)
    )

    # Bearish Engulfing
    df["pat_bear_engulf"] = (
        bearish_c &
        bullish_c.shift(1) &
        (o > prev_max) &
        (c < prev_min)
    )

    # Morning Star (3-candle bullish)
    d1_mid = (o.shift(2) + c.shift(2)) / 2
    df["pat_morning_star"] = (
        bearish_c.shift(2) &
        (body.shift(1) <= 0.35 * body.shift(2)) &
        bullish_c &
        (c > d1_mid)
    )

    # Evening Star (3-candle bearish)
    d1_mid_e = (o.shift(2) + c.shift(2)) / 2
    df["pat_evening_star"] = (
        bullish_c.shift(2) &
        (body.shift(1) <= 0.35 * body.shift(2)) &
        bearish_c &
        (c < d1_mid_e)
    )

    # Doji: body ≤ 5% of full range
    df["pat_doji"] = (
        (full_range > 0) &
        (body <= 0.05 * full_range)
    )

    return df
