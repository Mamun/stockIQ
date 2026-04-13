import numpy as np
import pandas as pd

from config import MA_PERIODS


def signal_score(row: pd.Series, prev_row: pd.Series) -> tuple[int, list[str]]:
    """
    Returns (score, reasons).
    score:  +2 strong buy · +1 buy · 0 neutral · -1 sell · -2 strong sell
    """
    reasons: list[str] = []
    score = 0
    price = row["Close"]

    # 1. Price vs each MA
    above_count = sum(1 for p in MA_PERIODS if price > row.get(f"MA{p}", np.nan))
    below_count = len(MA_PERIODS) - above_count

    if above_count == 5:
        score += 2
        reasons.append("Price above ALL moving averages (5/20/50/100/200) — bullish alignment")
    elif above_count >= 3:
        score += 1
        reasons.append(f"Price above {above_count}/5 moving averages")
    elif below_count == 5:
        score -= 2
        reasons.append("Price below ALL moving averages (5/20/50/100/200) — bearish alignment")
    elif below_count >= 3:
        score -= 1
        reasons.append(f"Price below {below_count}/5 moving averages")

    # 2. Golden / Death Cross (MA50 vs MA200)
    ma50_now   = row.get("MA50",  np.nan)
    ma200_now  = row.get("MA200", np.nan)
    ma50_prev  = prev_row.get("MA50",  np.nan)
    ma200_prev = prev_row.get("MA200", np.nan)

    if all(not np.isnan(v) for v in [ma50_now, ma200_now, ma50_prev, ma200_prev]):
        if ma50_prev <= ma200_prev and ma50_now > ma200_now:
            score += 2
            reasons.append("Golden Cross detected (MA50 crossed above MA200) — strong bullish signal")
        elif ma50_prev >= ma200_prev and ma50_now < ma200_now:
            score -= 2
            reasons.append("Death Cross detected (MA50 crossed below MA200) — strong bearish signal")
        elif ma50_now > ma200_now:
            score += 1
            reasons.append("MA50 above MA200 — bullish trend")
        else:
            score -= 1
            reasons.append("MA50 below MA200 — bearish trend")

    # 3. Short-term momentum: MA5 vs MA20
    ma5_now  = row.get("MA5",  np.nan)
    ma20_now = row.get("MA20", np.nan)
    if not np.isnan(ma5_now) and not np.isnan(ma20_now):
        if ma5_now > ma20_now:
            score += 1
            reasons.append("MA5 above MA20 — short-term momentum positive")
        else:
            score -= 1
            reasons.append("MA5 below MA20 — short-term momentum negative")

    # 4. Long-term weekly trend: price vs MA200W
    ma200w = row.get("MA200W", np.nan)
    if not np.isnan(ma200w):
        if price > ma200w:
            score += 2
            reasons.append("Price above 200-week MA — long-term secular uptrend")
        else:
            score -= 2
            reasons.append("Price below 200-week MA — long-term secular downtrend")

    # 5. RSI overbought / oversold
    rsi = row.get("RSI", np.nan)
    if not np.isnan(rsi):
        if rsi >= 70:
            score -= 1
            reasons.append(f"RSI {rsi:.1f} — overbought (momentum may be exhausted)")
        elif rsi <= 30:
            score += 1
            reasons.append(f"RSI {rsi:.1f} — oversold (potential bounce opportunity)")
        else:
            reasons.append(f"RSI {rsi:.1f} — neutral zone (30–70)")

    return score, reasons


def overall_signal(score: int) -> tuple[str, str]:
    """Maps score → (label, css_color)."""
    if score >= 4:
        return "STRONG BUY",  "#16A34A"
    elif score >= 2:
        return "BUY",         "#22C55E"
    elif score >= 0:
        return "NEUTRAL",     "#EAB308"
    elif score >= -2:
        return "SELL",        "#F97316"
    else:
        return "STRONG SELL", "#DC2626"


def find_crosses(df: pd.DataFrame) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """
    Returns (golden_cross_dates, death_cross_dates).
    Golden cross: MA50 crosses above MA200. Death cross: MA50 crosses below MA200.
    """
    ma50  = df["MA50"].dropna()
    ma200 = df["MA200"].dropna()
    common = ma50.index.intersection(ma200.index)
    if len(common) < 2:
        return pd.DatetimeIndex([]), pd.DatetimeIndex([])

    diff       = ma50[common] - ma200[common]
    sign       = diff.apply(lambda x: 1 if x > 0 else -1)
    sign_shift = sign.shift(1)

    golden = common[(sign == 1)  & (sign_shift == -1)]
    death  = common[(sign == -1) & (sign_shift ==  1)]
    return golden, death
