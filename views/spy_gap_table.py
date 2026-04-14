import pandas as pd
import streamlit as st

from data import fetch_spx_intraday
from indicators import compute_daily_gaps, compute_rsi
from views.ai_forecast import render_ai_forecast


def render_spy_gap_table_page() -> None:
    st.title("📋 SPY Gap Fill Tracker")
    st.caption("Daily gap fill tracker for SPY — last 30 trading days")

    with st.spinner("Loading SPY data…"):
        daily_df = fetch_spx_intraday(period="1y", interval="1d")

    if daily_df.empty:
        st.error("Could not load SPY data. Try again shortly.")
        return

    gaps_df = compute_daily_gaps(daily_df)
    gaps_df = gaps_df.copy()

    # Next-day price direction
    gaps_df["Next Close"] = gaps_df["Close"].shift(-1)
    gaps_df["Next Day"] = gaps_df.apply(
        lambda r: "▲" if (pd.notna(r["Next Close"]) and r["Next Close"] > r["Close"])
                  else ("▼" if (pd.notna(r["Next Close"]) and r["Next Close"] < r["Close"])
                  else "—"),
        axis=1,
    )

    # RSI — deduplicate index before aligning to prevent row expansion
    rsi_dedup = compute_rsi(daily_df)[~daily_df.index.duplicated(keep="last")]
    gaps_df["RSI"] = rsi_dedup.reindex(gaps_df.index)

    # ── Reserve slot for AI Forecast — renders after gap table loads ──────────
    ai_slot = st.empty()

    st.divider()

    # ── Gap Table (renders immediately) ───────────────────────────────────────
    has_vol = "Volume" in gaps_df.columns
    base_cols = ["Open", "Prev Close", "Gap", "Gap %", "Gap Filled", "Gap Confirmed", "RSI", "Next Day"]
    if has_vol:
        base_cols.insert(2, "Volume")
    gaps_data = gaps_df.tail(30)[base_cols].reset_index()
    if has_vol:
        gaps_data.columns = ["Date", "Open", "Prev Close", "Volume", "Gap $", "Gap %", "Filled", "Gap Confirmed", "RSI", "Next Day"]
    else:
        gaps_data.columns = ["Date", "Open", "Prev Close", "Gap $", "Gap %", "Filled", "Gap Confirmed", "RSI", "Next Day"]

    gaps_data["Date"] = gaps_data["Date"].dt.strftime("%m-%d")
    gaps_data = gaps_data.sort_values("Date", ascending=False).reset_index(drop=True)

    gaps_data["Status"] = gaps_data.apply(
        lambda r: "—" if r["Gap $"] == 0
        else ("✅ Filled" if r["Filled"]
        else ("⏳ Pending" if not r.get("Gap Confirmed", True)
        else "❌ Open")),
        axis=1,
    )

    gaps_data["RSI Zone"] = gaps_data["RSI"].apply(
        lambda v: "—" if pd.isna(v) or v == 0
        else ("Overbought" if v >= 70 else ("Oversold" if v <= 30 else "Neutral"))
    )

    display_cols = (
        ["Date", "Open", "Prev Close"]
        + (["Volume"] if has_vol else [])
        + ["Gap $", "Gap %", "Status", "RSI", "RSI Zone", "Next Day"]
    )
    display = gaps_data[display_cols]

    def _color_next_day(val):
        if val == "▲":
            return "color: #22C55E; font-weight: 700"
        if val == "▼":
            return "color: #EF4444; font-weight: 700"
        return ""

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

    fmt = {"Open": "${:.2f}", "Prev Close": "${:.2f}", "Gap $": "${:.2f}", "Gap %": "{:+.2f}%", "RSI": "{:.1f}"}
    if has_vol:
        fmt["Volume"] = lambda x: f"{x/1_000_000:.1f}M" if x and x > 0 else "—"

    st.dataframe(
        display.style
            .apply(_highlight, axis=1)
            .map(_color_next_day, subset=["Next Day"])
            .map(_color_rsi_zone, subset=["RSI Zone"])
            .map(_color_rsi, subset=["RSI"])
            .format(fmt, na_rep="—"),
        width="stretch", hide_index=True, height=900,
    )

    # ── Fill AI Forecast slot now that gap table is visible ───────────────────
    with ai_slot.container():
        render_ai_forecast(gaps_df)


render_spy_gap_table_page()
