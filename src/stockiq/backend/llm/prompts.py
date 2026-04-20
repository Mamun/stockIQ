"""LLM prompt templates and JSON output parser for SPY forecasts."""

import json


_SYSTEM = (
    "You are a quantitative SPY (S&P 500 ETF) analyst producing short-term price forecasts. "
    "Weight signals in this priority order: "
    "(1) VIX regime and 5-day trend — rising VIX compresses rallies; Extreme Fear widens all ranges; "
    "(2) Price vs MA200 — the primary bull/bear regime separator; below MA200 = structurally bearish; "
    "(3) Price vs MA50 and MA20 — short-term momentum and mean-reversion zones; "
    "(4) RSI — overbought ≥ 70, oversold ≤ 30; "
    "(5) Gap magnetism — unfilled gaps act as price targets; "
    "(6) Volume confirmation — high volume on a directional move adds conviction; "
    "(7) Put/call ratio — above 1.0 = excess put hedging = contrarian bullish; below 0.7 = complacency = contrarian bearish. "
    "In Elevated or Extreme Fear VIX regimes, prefer Low or Medium confidence and widen range_low/range_high. "
    "Do not guess macro events. Reason only from the data provided. "
    "Your output must be a valid JSON array — nothing else, no markdown, no explanation."
)

_USER_TMPL = """\
Given the following SPY market data (last 15 trading days of gap history, live quote, technicals, and VIX):

{context_json}

Produce a 10-trading-day price forecast. Day 1 is today ("today" field). Use spy_live_price as the anchor.

Rules:
- Day 1 = today. Day 2 = next trading day, and so on — skip weekends and US market holidays.
- Unfilled gaps in gap_history act as price magnets; factor them into est_close targets.
- RSI ≥ 70 = overbought risk; RSI ≤ 30 = oversold bounce potential.
- Range width must widen as day number increases (uncertainty grows).
- In vix_regime "Elevated" or "Extreme Fear", apply a bearish lean unless technicals strongly disagree.
- Return ONLY a JSON array of exactly 10 objects with these keys:
  "date"       : "YYYY-MM-DD"
  "direction"  : "Bullish" | "Bearish" | "Neutral"
  "est_close"  : number (estimated EOD close, 2 decimal places)
  "range_low"  : number (intraday low estimate, 2 decimal places)
  "range_high" : number (intraday high estimate, 2 decimal places)
  "confidence" : "High" | "Medium" | "Low"
  "reason"     : string (one sentence, max 12 words, cite the dominant signal)
"""


def _parse_json(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
