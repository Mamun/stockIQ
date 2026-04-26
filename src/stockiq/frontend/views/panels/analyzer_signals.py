"""Signal analysis + Buying Pressure (BX) panels for the Stock Analyzer page."""

import pandas as pd
import streamlit as st

from stockiq.backend.services.analyzer_service import get_buying_pressure
from stockiq.frontend.theme import MUT, SEP


def render_signal_analysis(sig: dict) -> None:
    score        = sig["score"]
    signal_color = sig["color"]

    st.markdown("**Signal Analysis**")
    score_bar_pct = min(100, max(0, (score + 8) / 16 * 100))
    st.markdown(
        f'<div style="background:{SEP};border-radius:6px;height:6px;margin-bottom:10px">'
        f'<div style="width:{score_bar_pct:.0f}%;height:100%;background:{signal_color};'
        f'border-radius:6px"></div></div>',
        unsafe_allow_html=True,
    )
    for reason in sig["reasons"]:
        st.markdown(_reason_icon(reason))


def render_buying_pressure(df: pd.DataFrame) -> None:
    st.markdown("**Buying Pressure (BX)**")
    st.caption("2/3 conditions = signal · 3/3 = strong · based on completed bars only")

    _render_bx_panel(get_buying_pressure(df, "monthly"), "Monthly")
    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
    _render_bx_panel(get_buying_pressure(df, "weekly"), "Weekly")


# ── Private helpers ────────────────────────────────────────────────────────────

def _reason_icon(text: str) -> str:
    lc = text.lower()
    if any(w in lc for w in ("above", "golden cross", "positive", "uptrend", "oversold")):
        return f"🟢 {text}"
    if any(w in lc for w in ("below", "death cross", "negative", "downtrend", "overbought")):
        return f"🔴 {text}"
    return f"⚪ {text}"


def _render_bx_panel(bx: dict, label: str) -> None:
    strength = bx["strength"]
    if bx["signal"] and strength == 3:
        badge_bg, badge_txt = "#16A34A", "BX TRIGGERED ✓✓✓"
    elif bx["signal"]:
        badge_bg, badge_txt = "#22C55E", "BX TRIGGERED ✓✓"
    else:
        badge_bg, badge_txt = "#475569", "WAITING FOR BX"

    bar_label = bx.get("bar_label", "")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
        f'<span style="font-weight:600">{label}</span>'
        f'<span style="background:{badge_bg};color:#fff;padding:2px 10px;'
        f'border-radius:4px;font-size:0.78rem">{badge_txt}</span>'
        f'<span style="color:{MUT};font-size:0.72rem">{bar_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    for cond in bx["conditions_met"]:
        st.markdown(f"&nbsp;&nbsp;✅ {cond}")
    for cond in bx["conditions_missing"]:
        st.markdown(f"&nbsp;&nbsp;❌ {cond}")
