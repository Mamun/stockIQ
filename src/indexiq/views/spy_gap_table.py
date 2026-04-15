import pandas as pd
import streamlit as st

from indexiq.data import fetch_spx_intraday, fetch_spx_quote
from indexiq.models.indicators import compute_daily_gaps, compute_rsi, patch_today_gap
from indexiq.views.components.gap_table import render_gap_table


def render_spy_gap_table_page() -> None:
    st.title("📋 SPY Gap Fill Tracker")
    st.caption("Daily gap fill tracker for SPY — last 30 trading days")

    with st.spinner("Loading SPY data…"):
        daily_df = fetch_spx_intraday(period="1y", interval="1d")

    if daily_df.empty:
        st.error("Could not load SPY data. Try again shortly.")
        return

    quote   = fetch_spx_quote()
    gaps_df = patch_today_gap(compute_daily_gaps(daily_df), quote)
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

    st.divider()

    render_gap_table(
        gaps_df,
        show_rsi=True,
        show_next_day=True,
        height=900,
    )


render_spy_gap_table_page()
