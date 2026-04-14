"""Shared AI 5-day SPY forecast — used by spy_dashboard and spy_gap_table."""

import json
import os
from datetime import datetime, timezone, timedelta

import anthropic
import pandas as pd
import streamlit as st

from data.market import fetch_spx_quote


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_market_open() -> bool:
    et  = timezone(timedelta(hours=-4))
    now = datetime.now(et)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


def _next_market_open_str() -> str:
    et  = timezone(timedelta(hours=-4))
    now = datetime.now(et)
    days_ahead = 1
    while True:
        candidate = now + timedelta(days=days_ahead)
        if candidate.weekday() < 5:
            break
        days_ahead += 1
    return candidate.strftime("%a %b %-d, 9:30 AM ET")


def _build_context(gaps_df: pd.DataFrame, quote: dict) -> str:
    rows = []
    for dt, row in gaps_df.tail(15).iterrows():
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
    context = {
        "today":          now_et.strftime("%Y-%m-%d"),
        "as_of":          now_et.strftime("%Y-%m-%d %H:%M ET"),
        "spy_live_price": round(quote.get("price", 0), 2),
        "spy_prev_close": round(quote.get("prev_close", 0), 2),
        "spy_day_high":   round(quote.get("day_high", 0), 2),
        "spy_day_low":    round(quote.get("day_low", 0), 2),
        "gap_history":    rows,
    }
    return json.dumps(context)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_ai_prediction(context_json: str) -> list[dict]:
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


# ── Public renderer ───────────────────────────────────────────────────────────

def render_ai_forecast(gaps_df: pd.DataFrame, show_share_btn: bool = True) -> None:
    """Render the AI 5-day SPY forecast table. Pass the computed gaps DataFrame."""
    quote         = fetch_spx_quote()
    current_price = quote.get("price", 0)
    api_key       = os.environ.get("ANTHROPIC_API_KEY", "")

    head_col, btn_col = st.columns([8, 1])
    head_col.markdown("### 🤖 AI SPY Forecast")
    if show_share_btn:
        with btn_col:
            st.html("""
            <button onclick="
              var url = (window.parent.location.origin || window.location.ancestorOrigins?.[0] || window.location.origin) + '/spy-ai-forecast';
              navigator.clipboard.writeText(url)
                .then(function() {
                  var b = document.getElementById('fb');
                  b.innerHTML = '✅ Copied!';
                  b.style.color = '#22C55E';
                  b.style.borderColor = '#22C55E';
                  setTimeout(function() {
                    b.innerHTML = '🔗 Share';
                    b.style.color = '#94A3B8';
                    b.style.borderColor = '#334155';
                  }, 2000);
                })
                .catch(function() {
                  var b = document.getElementById('fb');
                  b.innerHTML = window.location.origin + '/spy-ai-forecast';
                });
            " id="fb" style="
              background:#0F172A;color:#94A3B8;border:1px solid #334155;
              border-radius:6px;padding:5px 10px;cursor:pointer;
              font-size:13px;white-space:nowrap;width:100%;
            ">🔗 Share</button>
            """)

    if not api_key:
        st.warning(
            "Set the `ANTHROPIC_API_KEY` environment variable to enable the AI forecast.",
            icon="🔑",
        )
        return

    market_open = _is_market_open()
    et          = timezone(timedelta(hours=-4))
    now_et      = datetime.now(et)

    if not market_open and now_et.weekday() >= 5:
        st.info(f"Market closed (weekend). Next update at {_next_market_open_str()}.", icon="🗓️")

    context_json = _build_context(gaps_df, quote)

    with st.spinner("Generating AI forecast…"):
        try:
            predictions = _fetch_ai_prediction(context_json)
        except Exception as e:
            st.error(f"AI forecast unavailable: {e}")
            return

    if not predictions:
        st.error("AI forecast returned no data.")
        return

    rows = []
    for p in predictions:
        direction = p.get("direction", "Neutral")
        dir_icon  = "▲" if direction == "Bullish" else ("▼" if direction == "Bearish" else "—")
        conf      = p.get("confidence", "Low")
        conf_icon = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(conf, "🔴")
        est       = float(p.get("est_close", current_price))
        chg       = est - current_price
        chg_p     = (chg / current_price * 100) if current_price else 0
        raw_date = p.get("date", "")
        try:
            fmt_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%m-%d")
        except ValueError:
            fmt_date = raw_date
        rows.append({
            "Date":       fmt_date,
            "Direction":  dir_icon,
            "Est. Close": est,
            "Change":     chg,
            "Change %":   chg_p,
            "Low":        float(p.get("range_low", est)),
            "High":       float(p.get("range_high", est)),
            "Confidence": f"{conf_icon} {conf}",
            "Signal":     p.get("reason", ""),
        })

    pred_df = pd.DataFrame(rows)

    def _color_direction(val):
        if val == "▲":
            return "color:#22C55E; font-weight:700"
        if val == "▼":
            return "color:#EF4444; font-weight:700"
        return "color:#94A3B8"

    def _color_change(val):
        if val > 0:
            return "color:#22C55E; font-weight:600"
        if val < 0:
            return "color:#EF4444; font-weight:600"
        return ""

    fmt = {
        "Est. Close": "${:.2f}",
        "Change":     lambda v: f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}",
        "Change %":   lambda v: f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%",
        "Low":        "${:.2f}",
        "High":       "${:.2f}",
    }

    st.dataframe(
        pred_df.style
            .map(_color_direction, subset=["Direction"])
            .map(_color_change,    subset=["Change", "Change %"])
            .format(fmt),
        hide_index=True,
        width="stretch",
    )

    updated_at  = now_et.strftime("%I:%M %p ET")
    next_update = (now_et + timedelta(hours=1)).strftime("%I:%M %p ET")
    if market_open:
        st.caption(f"Last updated: {updated_at} · Next refresh: {next_update} · Anchor: ${current_price:.2f}")
    else:
        st.caption(f"Last updated: {updated_at} · Market closed — refreshes at next open")

