"""
SPY forecast context builder and market calendar helpers.

Assembles the JSON market-context payload passed to the LLM.
LLM provider wrappers and prompt templates live in stockiq.backend.llm.
"""

import json
from datetime import datetime, timezone, timedelta

import pandas as pd


# ── Market calendar helpers ────────────────────────────────────────────────────

def is_market_open() -> bool:
    et  = timezone(timedelta(hours=-4))
    now = datetime.now(et)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


def next_market_open_str() -> str:
    et  = timezone(timedelta(hours=-4))
    now = datetime.now(et)
    days_ahead = 1
    while True:
        candidate = now + timedelta(days=days_ahead)
        if candidate.weekday() < 5:
            break
        days_ahead += 1
    return candidate.strftime("%a %b %-d, 9:30 AM ET")


# ── Context builder ───────────────────────────────────────────────────────────

def build_forecast_context(
    gaps_df: pd.DataFrame,
    quote: dict,
    daily_df: pd.DataFrame | None = None,
    vix_df: pd.DataFrame | None = None,
    pc_data: dict | None = None,
) -> str:
    """Build the JSON context string passed to the AI forecast prompt."""
    completed_gaps = gaps_df.iloc[:-1]
    rows = []
    for dt, row in completed_gaps.tail(15).iterrows():
        rows.append({
            "date":         dt.strftime("%Y-%m-%d"),
            "open":         round(float(row.get("Open", 0)), 2),
            "prev_close":   round(float(row.get("Prev Close", 0)), 2),
            "gap_usd":      round(float(row.get("Gap", 0)), 2),
            "gap_pct":      round(float(row.get("Gap %", 0)), 2),
            "gap_filled":   bool(row.get("Gap Filled", False)),
            "rsi":          round(float(row.get("RSI", 0) or 0), 1),
            "next_day_dir": row.get("Next Day", "—"),
        })

    et      = timezone(timedelta(hours=-4))
    now_et  = datetime.now(et)
    prev_c  = round(quote.get("prev_close", 0), 2)
    day_o   = round(quote.get("day_open",   0), 2)
    today_gap     = round(day_o - prev_c, 2) if day_o and prev_c else 0
    today_gap_pct = round(today_gap / prev_c * 100, 2) if prev_c else 0
    spy_price     = round(quote.get("price", 0), 2)

    context: dict = {
        "today":              now_et.strftime("%Y-%m-%d"),
        "as_of":              now_et.strftime("%Y-%m-%d %H:%M ET"),
        "spy_live_price":     spy_price,
        "spy_prev_close":     prev_c,
        "spy_day_open":       day_o,
        "spy_today_gap_usd":  today_gap,
        "spy_today_gap_pct":  today_gap_pct,
        "spy_day_high":       round(quote.get("day_high", 0), 2),
        "spy_day_low":        round(quote.get("day_low",  0), 2),
        "gap_history":        rows,
    }

    if daily_df is not None and not daily_df.empty and "Close" in daily_df.columns:
        close  = daily_df["Close"].dropna()
        n      = len(close)
        anchor = spy_price or (float(close.iloc[-1]) if n else 0)

        def _ma(p: int) -> float | None:
            return round(float(close.rolling(p).mean().iloc[-1]), 2) if n >= p else None

        def _pct_from(ma_val: float | None) -> float | None:
            if ma_val and anchor:
                return round((anchor - ma_val) / ma_val * 100, 2)
            return None

        ma20, ma50, ma200 = _ma(20), _ma(50), _ma(200)
        context["technicals"] = {
            "ma20":              ma20,
            "pct_from_ma20":     _pct_from(ma20),
            "ma50":              ma50,
            "pct_from_ma50":     _pct_from(ma50),
            "ma200":             ma200,
            "pct_from_ma200":    _pct_from(ma200),
            "above_ma200":       bool(anchor > ma200) if ma200 else None,
            "spy_52w_high":      round(float(close.tail(252).max()), 2),
            "spy_52w_low":       round(float(close.tail(252).min()), 2),
            "pct_from_52w_high": round((anchor / float(close.tail(252).max()) - 1) * 100, 2) if anchor else None,
            "pct_from_52w_low":  round((anchor / float(close.tail(252).min()) - 1) * 100, 2) if anchor else None,
        }

        if "Volume" in daily_df.columns:
            vol       = daily_df["Volume"].dropna()
            avg_vol   = float(vol.rolling(20).mean().iloc[-1]) if len(vol) >= 20 else None
            today_vol = float(vol.iloc[-1]) if len(vol) else None
            context["technicals"]["avg_volume_20d"]        = int(avg_vol) if avg_vol else None
            context["technicals"]["today_volume"]          = int(today_vol) if today_vol else None
            context["technicals"]["volume_vs_20d_avg_pct"] = (
                round((today_vol / avg_vol - 1) * 100, 1) if avg_vol and today_vol else None
            )

    if vix_df is not None and not vix_df.empty and "VIX" in vix_df.columns:
        vix     = vix_df["VIX"].dropna()
        vix_now = float(vix.iloc[-1])
        vix_5d  = float(vix.iloc[-6]) if len(vix) >= 6 else float(vix.iloc[0])
        vix_avg = float(vix.mean())
        if vix_now < 15:
            regime = "Calm"
        elif vix_now < 20:
            regime = "Normal"
        elif vix_now < 30:
            regime = "Elevated"
        else:
            regime = "Extreme Fear"
        context["vix"] = {
            "vix_now":       round(vix_now, 2),
            "vix_regime":    regime,
            "vix_5d_change": round(vix_now - vix_5d, 2),
            "vix_1y_avg":    round(vix_avg, 2),
            "vix_vs_1y_avg": round(vix_now - vix_avg, 2),
        }

    if pc_data:
        context["put_call_ratio"] = {
            "ratio":  pc_data["ratio"],
            "signal": pc_data["signal"],
        }

    return json.dumps(context)
