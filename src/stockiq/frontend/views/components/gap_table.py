"""
Reusable gap-fill tracker table.

Consolidated from three near-identical implementations that were spread across
analyzer.py, spy_dashboard.py, and spy_gap_table.py.
"""

import pandas as pd
import streamlit as st


def render_gap_table(
    gaps_df: pd.DataFrame,
    *,
    title: str = "Daily Gaps (Last 30 Days)",
    show_rsi: bool = False,
    show_next_day: bool = False,
    price_prefix: str = "$",
    share_url: str | None = None,
    rows: int = 30,
    height: int = 600,
) -> None:
    """Render a styled gap-fill tracker table.

    Args:
        gaps_df:       DataFrame returned by compute_daily_gaps() (optionally
                       enriched with RSI, Next Day columns).
        title:         Section heading text.
        show_rsi:      Show RSI + RSI Zone columns (gaps_df must have 'RSI').
        show_next_day: Show Next Day direction column (gaps_df must have 'Next Day').
        price_prefix:  '$' for stocks/ETFs, '' for indices like VIX.
        share_url:     If set, renders a share popover next to the title.
        rows:          How many recent rows to show.
        height:        Dataframe display height in pixels.
    """
    # ── Header row ────────────────────────────────────────────────────────────
    _pending_note = (
        '<span style="font-size:11px;color:#64748B;font-weight:400;margin-left:10px">'
        '⏳ Pending = gap not yet filled, confirms within 3 trading days'
        '</span>'
    )
    if share_url:
        head_col, btn_col = st.columns([8, 1])
        head_col.markdown(f"#### {title} {_pending_note}", unsafe_allow_html=True)
        with btn_col:
            with st.popover("🔗 Share", use_container_width=True):
                st.code(share_url, language=None)
                st.caption("Copy the link above to share this page.")
    else:
        st.markdown(f"#### {title} {_pending_note}", unsafe_allow_html=True)

    # ── Build display DataFrame ───────────────────────────────────────────────
    has_vol = "Volume" in gaps_df.columns
    base_cols = ["Open", "Close", "High", "Low", "Gap", "Gap %", "Gap Filled", "Gap Confirmed"]
    if has_vol:
        base_cols.insert(2, "Volume")
    if show_rsi and "RSI" in gaps_df.columns:
        base_cols.append("RSI")
    if show_next_day and "Next Day" in gaps_df.columns:
        base_cols.append("Next Day")

    gaps_data = gaps_df.tail(rows)[base_cols].reset_index()

    # Rename columns to display-friendly names
    col_names = ["Date", "Open", "Close"]
    if has_vol:
        col_names.append("Volume")
    col_names += ["High", "Low", "Gap $", "Gap %", "Filled", "Gap Confirmed"]
    if show_rsi and "RSI" in gaps_df.columns:
        col_names.append("RSI")
    if show_next_day and "Next Day" in gaps_df.columns:
        col_names.append("Next Day")
    gaps_data.columns = col_names

    gaps_data["Date"] = gaps_data["Date"].dt.strftime("%m-%d")
    gaps_data = gaps_data.sort_values("Date", ascending=False).reset_index(drop=True)

    gaps_data["Status"] = gaps_data.apply(
        lambda r: "—" if r["Gap $"] == 0
        else ("✅ Filled" if r["Filled"]
        else ("⏳ Pending" if not r.get("Gap Confirmed", True)
        else "❌ Open")),
        axis=1,
    )

    has_rsi_col = "RSI" in gaps_data.columns
    if has_rsi_col:
        gaps_data["RSI Zone"] = gaps_data["RSI"].apply(
            lambda v: "—" if pd.isna(v) or v == 0
            else ("Overbought" if v >= 70 else ("Oversold" if v <= 30 else "Neutral"))
        )

    # ── Select display columns ────────────────────────────────────────────────
    display_cols = ["Date", "Open", "Close", "High", "Low"]
    if has_vol:
        display_cols.append("Volume")
    display_cols += ["Gap $", "Gap %", "Status"]
    if has_rsi_col:
        display_cols += ["RSI", "RSI Zone"]
    if show_next_day and "Next Day" in gaps_data.columns:
        display_cols.append("Next Day")

    display = gaps_data[display_cols]

    # ── Styling functions ─────────────────────────────────────────────────────
    def _highlight(row):
        gap    = gaps_data.loc[row.name, "Gap $"]
        filled = gaps_data.loc[row.name, "Filled"]
        if gap == 0 or bool(filled):
            return [""] * len(row)
        style = (
            "background-color: rgba(34,197,94,0.20); color:#22C55E; font-weight:600"
            if gap > 0
            else "background-color: rgba(239,68,68,0.25); color:#EF4444; font-weight:600"
        )
        return [style] * len(row)

    def _color_rsi_zone(val):
        if val == "Overbought":
            return "color:#EF4444; font-weight:700"
        if val == "Oversold":
            return "color:#22C55E; font-weight:700"
        if val == "Neutral":
            return "color:#F59E0B"
        return ""

    def _color_rsi(val):
        if pd.isna(val) or val == 0:
            return ""
        if val >= 70:
            return "color:#EF4444; font-weight:700"
        if val <= 30:
            return "color:#22C55E; font-weight:700"
        return "color:#F59E0B"

    def _color_next_day(val):
        if val == "▲":
            return "color: #22C55E; font-weight: 700"
        if val == "▼":
            return "color: #EF4444; font-weight: 700"
        return ""

    # ── Format spec ───────────────────────────────────────────────────────────
    p = price_prefix
    fmt = {
        "Open":  f"{p}{{:.2f}}",
        "Close": f"{p}{{:.2f}}",
        "High":  f"{p}{{:.2f}}",
        "Low":   f"{p}{{:.2f}}",
        "Gap $": f"{p}{{:.2f}}",
        "Gap %": "{:+.2f}%",
    }
    if has_rsi_col:
        fmt["RSI"] = "{:.1f}"
    if has_vol:
        fmt["Volume"] = lambda x: f"{x/1_000_000:.1f}M" if x and x > 0 else "—"

    # ── Build styled dataframe ────────────────────────────────────────────────
    styled = display.style.apply(_highlight, axis=1).format(fmt, na_rep="—")
    if has_rsi_col:
        styled = styled.map(_color_rsi_zone, subset=["RSI Zone"]).map(_color_rsi, subset=["RSI"])
    if show_next_day and "Next Day" in display_cols:
        styled = styled.map(_color_next_day, subset=["Next Day"])

    st.dataframe(styled, width="stretch", hide_index=True, height=(len(display) + 1) * 35 + 4)
