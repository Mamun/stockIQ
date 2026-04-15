"""
AI forecast model — pure data logic + Anthropic API call.

Extracted from views/ai_forecast.py so the API call and context-building
live in the model layer, independent of any Streamlit rendering code.
"""

import json
import os
from datetime import datetime, timezone, timedelta

import anthropic
import pandas as pd
import streamlit as st

from indexiq.cache_ttl import CACHE_TTL


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


def build_forecast_context(gaps_df: pd.DataFrame, quote: dict) -> str:
    """Build the JSON context string passed to the AI forecast prompt.

    Excludes the last (incomplete) bar from gap history and enriches with
    the live quote fields (prev_close, day_high, day_low, etc.).
    """
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
    context = {
        "today":              now_et.strftime("%Y-%m-%d"),
        "as_of":              now_et.strftime("%Y-%m-%d %H:%M ET"),
        "spy_live_price":     round(quote.get("price", 0), 2),
        "spy_prev_close":     prev_c,
        "spy_day_open":       day_o,
        "spy_today_gap_usd":  today_gap,
        "spy_today_gap_pct":  today_gap_pct,
        "spy_day_high":       round(quote.get("day_high", 0), 2),
        "spy_day_low":        round(quote.get("day_low",  0), 2),
        "gap_history":        rows,
    }
    return json.dumps(context)


@st.cache_data(ttl=CACHE_TTL["fetch_ai_prediction"], show_spinner=False)
def fetch_ai_prediction(cache_key: str, _context_json: str) -> list[dict]:
    """Fetch a 5-day SPY forecast from Claude.

    cache_key = "YYYY-MM-DD-HH" — stable for one hour so page refreshes hit
    the cache. _context_json is excluded from the cache key (leading _) but
    still passed to the API when the cache is cold.
    """
    context_json = _context_json
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return []

    client = anthropic.Anthropic(api_key=api_key)

    system = (
        "You are a quantitative equity analyst specialising in SPY (S&P 500 ETF) short-term price dynamics. "
        "You reason from opening gap data, RSI, and recent momentum to produce a directional 5-trading-day forecast. "
        "Your output must be a valid JSON array — nothing else."
    )

    prompt = f"""
Given the following SPY market data (last 15 trading days of gap history plus today's live quote):

{context_json}

Produce a 5-trading-day price forecast. Day 1 must be today's date ("today" field in the data).
Use the current live SPY price as the anchor.

Rules:
- Day 1 = today. Day 2 = next trading day after today, and so on.
- Skip weekends and US market holidays when assigning dates.
- Unfilled gaps act as price magnets — factor them into your targets.
- RSI ≥ 70 = overbought, ≤ 30 = oversold.
- Range width should widen with lower confidence.
- Return ONLY a JSON array of exactly 10 objects with these keys:
  "date"       : "YYYY-MM-DD" format (ISO date, e.g. "2026-04-14")
  "direction"  : "Bullish" | "Bearish" | "Neutral"
  "est_close"  : number (estimated EOD close price, 2 decimal places)
  "range_low"  : number (intraday low estimate, 2 decimal places)
  "range_high" : number (intraday high estimate, 2 decimal places)
  "confidence" : "High" | "Medium" | "Low"
  "reason"     : string (one concise sentence, max 12 words)
"""

    raw = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    text = next((b.text for b in raw.content if b.type == "text"), "")
    if not text:
        return []
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
