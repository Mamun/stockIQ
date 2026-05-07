"""RSI-based market top detection signals for SPX/SPY."""

import numpy as np
import pandas as pd

from stockiq.backend.models.indicators import compute_rsi


def detect_bearish_rsi_divergence(df: pd.DataFrame, lookback: int = 90) -> dict:
    """
    Bearish RSI divergence: price makes a higher high but RSI makes a lower high.
    Scans the most recent `lookback` daily bars for the two latest price peaks.
    """
    if len(df) < 30:
        return {"detected": False}

    recent = df.tail(lookback).copy()
    full_rsi = compute_rsi(df)
    recent["_rsi"] = full_rsi.reindex(recent.index)

    closes = recent["Close"].values
    rsi_vals = recent["_rsi"].values
    n = len(closes)

    # Local price maxima: higher than every bar within 5 bars on each side
    peaks = [
        i for i in range(5, n - 5)
        if closes[i] == max(closes[max(0, i - 5): i + 6])
    ]

    if len(peaks) < 2:
        return {"detected": False}

    p1, p2 = peaks[-2], peaks[-1]
    price1, price2 = float(closes[p1]), float(closes[p2])
    rsi1 = float(rsi_vals[p1]) if not np.isnan(rsi_vals[p1]) else None
    rsi2 = float(rsi_vals[p2]) if not np.isnan(rsi_vals[p2]) else None

    if rsi1 is None or rsi2 is None:
        return {"detected": False}

    # Price made a meaningfully higher high (>0.1%) while RSI dropped by >1 point
    detected = price2 > price1 * 1.001 and rsi2 < rsi1 - 1.0 and rsi1 > 60

    return {
        "detected": detected,
        "price_high1": round(price1, 2),
        "price_high2": round(price2, 2),
        "rsi_at_high1": round(rsi1, 1),
        "rsi_at_high2": round(rsi2, 1),
        "date1": recent.index[p1].strftime("%b %d"),
        "date2": recent.index[p2].strftime("%b %d"),
    }


def check_rsi_timeframe_stack(daily_df: pd.DataFrame) -> dict:
    """
    Daily RSI ≥ 75 AND weekly RSI ≥ 65 → multi-timeframe overbought stack.
    When both timeframes are stretched, reversal risk is materially higher.
    """
    if len(daily_df) < 50:
        return {"daily_rsi": None, "weekly_rsi": None, "stacked": False}

    daily_rsi_series = compute_rsi(daily_df)
    daily_rsi = float(daily_rsi_series.dropna().iloc[-1])

    weekly_rsi: float | None = None
    weekly_close = daily_df["Close"].resample("W").last().dropna()
    if len(weekly_close) >= 20:
        weekly_df = pd.DataFrame({"Close": weekly_close})
        weekly_rsi_series = compute_rsi(weekly_df, period=14)
        weekly_rsi = float(weekly_rsi_series.dropna().iloc[-1])

    stacked = daily_rsi >= 75 and weekly_rsi is not None and weekly_rsi >= 65

    return {
        "daily_rsi": round(daily_rsi, 1),
        "weekly_rsi": round(weekly_rsi, 1) if weekly_rsi is not None else None,
        "daily_overbought": daily_rsi >= 75,
        "weekly_overbought": weekly_rsi is not None and weekly_rsi >= 65,
        "stacked": stacked,
    }


def detect_rsi_failure_swing(df: pd.DataFrame, lookback: int = 60) -> dict:
    """
    Bearish RSI Failure Swing (classic Wilder pattern):
      H1 = RSI peak above 70
      L1 = pullback trough below 70
      H2 = rally that fails to exceed H1  (H2 < H1)
      Break below L1 → confirmed reversal signal
    """
    full_rsi = compute_rsi(df).dropna()
    rsi = full_rsi.tail(lookback)
    if len(rsi) < 10:
        return {"detected": False}

    vals = rsi.values
    n = len(vals)

    # Local maxima/minima using a 2-bar window on each side
    maxima = [
        i for i in range(2, n - 2)
        if vals[i] >= vals[i - 1] and vals[i] >= vals[i + 1]
        and vals[i] >= vals[i - 2] and vals[i] >= vals[i + 2]
    ]
    minima = [
        i for i in range(2, n - 2)
        if vals[i] <= vals[i - 1] and vals[i] <= vals[i + 1]
        and vals[i] <= vals[i - 2] and vals[i] <= vals[i + 2]
    ]

    # H1: most recent local RSI max above 70
    h1_idx = next((i for i in reversed(maxima) if vals[i] > 70), None)
    if h1_idx is None:
        return {"detected": False, "current_rsi": round(float(vals[-1]), 1)}

    h1 = float(vals[h1_idx])

    # L1: first local min after H1 where RSI dipped below 70
    l1_idx = next((i for i in minima if i > h1_idx and vals[i] < 70), None)
    if l1_idx is None:
        return {"detected": False, "h1": round(h1, 1), "current_rsi": round(float(vals[-1]), 1)}

    l1 = float(vals[l1_idx])

    # H2: first local max after L1 that stays below H1
    h2_idx = next((i for i in maxima if i > l1_idx and vals[i] < h1), None)
    if h2_idx is None:
        return {"detected": False, "h1": round(h1, 1), "l1": round(l1, 1), "current_rsi": round(float(vals[-1]), 1)}

    h2 = float(vals[h2_idx])

    # Confirmed when RSI broke below L1 after H2
    post_h2 = vals[h2_idx + 1:] if h2_idx + 1 < n else []
    confirmed = bool(any(v < l1 for v in post_h2))
    approaching = not confirmed and float(vals[-1]) < (l1 + 4)

    return {
        "detected": confirmed,
        "approaching": approaching,
        "h1": round(h1, 1),
        "l1": round(l1, 1),
        "h2": round(h2, 1),
        "current_rsi": round(float(vals[-1]), 1),
    }


def compute_ma_stretch(df: pd.DataFrame) -> dict:
    """
    Distance of price above key MAs.
    20%+ above 200 DMA has historically preceded significant corrections.
    """
    if len(df) < 200:
        return {}

    close = float(df["Close"].iloc[-1])
    ma20  = float(df["Close"].rolling(20).mean().iloc[-1])
    ma50  = float(df["Close"].rolling(50).mean().iloc[-1])
    ma200 = float(df["Close"].rolling(200).mean().iloc[-1])

    def pct(ma: float) -> float:
        return round((close / ma - 1) * 100, 1) if ma else 0.0

    pct_200 = pct(ma200)

    if pct_200 >= 20:
        level, color = "Extreme", "#EF4444"
    elif pct_200 >= 15:
        level, color = "Very High", "#F97316"
    elif pct_200 >= 10:
        level, color = "Elevated", "#FBBF24"
    elif pct_200 >= 5:
        level, color = "Stretched", "#94A3B8"
    else:
        level, color = "Normal", "#22C55E"

    return {
        "close":         round(close, 2),
        "ma20":          round(ma20, 2),
        "ma50":          round(ma50, 2),
        "ma200":         round(ma200, 2),
        "pct_above_20":  pct(ma20),
        "pct_above_50":  pct(ma50),
        "pct_above_200": pct_200,
        "stretch_level": level,
        "stretch_color": color,
        "warning":       pct_200 >= 10,
    }


def check_breadth_divergence(daily_df: pd.DataFrame) -> dict:
    """
    Breadth divergence: SPX RSI is high while % of stocks above 50 MA is declining.
    Uses ^SPXA50R (S&P 500 % above 50-day MA) as the breadth proxy.
    """
    import yfinance as yf

    rsi_series = compute_rsi(daily_df)
    current_rsi = float(rsi_series.dropna().iloc[-1])

    try:
        breadth_df = yf.download(
            "^SPXA50R", period="60d", interval="1d",
            progress=False, auto_adjust=True,
        )
        if breadth_df.empty:
            return {"available": False, "spx_rsi": round(current_rsi, 1)}

        # Handle potential MultiIndex from newer yfinance versions
        if isinstance(breadth_df.columns, pd.MultiIndex):
            breadth_df.columns = breadth_df.columns.get_level_values(0)

        if "Close" not in breadth_df.columns:
            return {"available": False, "spx_rsi": round(current_rsi, 1)}

        breadth_close = breadth_df["Close"].dropna()
        if len(breadth_close) < 10:
            return {"available": False, "spx_rsi": round(current_rsi, 1)}

        current_breadth = float(breadth_close.iloc[-1])
        trend_10d = float(breadth_close.iloc[-1] - breadth_close.iloc[-10])
        declining = trend_10d < -5

        return {
            "available":         True,
            "detected":          current_rsi >= 65 and declining,
            "spx_rsi":           round(current_rsi, 1),
            "breadth_pct":       round(current_breadth, 1),
            "breadth_trend":     round(trend_10d, 1),
            "breadth_declining": declining,
        }
    except Exception:
        return {"available": False, "spx_rsi": round(current_rsi, 1)}
