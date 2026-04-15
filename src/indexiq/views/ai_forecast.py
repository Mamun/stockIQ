"""Shared AI 5-day SPY forecast view — used by spy_dashboard and spy_gap_table."""

import os
from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

from indexiq.data.market import fetch_spx_quote
from indexiq.models.ai_forecast import (
    build_forecast_context,
    fetch_ai_prediction,
    is_market_open,
    next_market_open_str,
)


def _share_url(path: str) -> str:
    """Build an absolute share URL using the current page's origin."""
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(st.context.url)
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    except Exception:
        return path


def render_ai_forecast(gaps_df: pd.DataFrame, show_share_btn: bool = True) -> None:
    """Render the AI 5-day SPY forecast table. Pass the computed gaps DataFrame."""
    quote         = fetch_spx_quote()
    current_price = quote.get("price", 0)
    api_key       = os.environ.get("ANTHROPIC_API_KEY", "")

    head_col, btn_col = st.columns([8, 1])
    head_col.markdown("### 🤖 AI SPY Forecast")
    if show_share_btn:
        with btn_col:
            with st.popover("🔗 Share", use_container_width=True):
                st.code(_share_url("/spy-ai-forecast"), language=None)
                st.caption("Copy the link above to share this forecast.")

    if not api_key:
        st.warning(
            "Set the `ANTHROPIC_API_KEY` environment variable to enable the AI forecast.",
            icon="🔑",
        )
        return

    market_open = is_market_open()
    et          = timezone(timedelta(hours=-4))
    now_et      = datetime.now(et)

    if not market_open and now_et.weekday() >= 5:
        st.info(f"Market closed (weekend). Next update at {next_market_open_str()}.", icon="🗓️")

    context_json = build_forecast_context(gaps_df, quote)
    cache_key    = now_et.strftime("%Y-%m-%d-%H")   # changes once per hour

    with st.spinner("Generating AI forecast…"):
        try:
            predictions = fetch_ai_prediction(cache_key, context_json)
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
        raw_date  = p.get("date", "")
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
            "Low":        float(p.get("range_low",  est)),
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
