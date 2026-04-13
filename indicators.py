import pandas as pd
import numpy as np

from config import MA_PERIODS, FIB_LEVELS


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
    df_gap = df[["Open", "Close", "High", "Low"]].copy()
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

        for j in range(i + 1, min(i + 4, len(df_gap))):
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

    df_gap["Gap Filled"] = gap_filled_list
    df_gap["Open"]       = df_gap["Open"].round(2)
    df_gap["Close"]      = df_gap["Close"].round(2)
    df_gap["Prev Close"] = df_gap["Prev Close"].round(2)
    df_gap["Gap"]        = df_gap["Gap"].round(2)
    return df_gap.dropna(subset=["Prev Close"])


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
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    max_oc = pd.concat([o, c], axis=1).max(axis=1)
    min_oc = pd.concat([o, c], axis=1).min(axis=1)
    body       = max_oc - min_oc
    upper_wick = h - max_oc
    lower_wick = min_oc - l
    full_range = h - l
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
