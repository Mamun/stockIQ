import streamlit as st

from stockiq.backend.services.spy_service import get_spy_gap_table_data
from stockiq.frontend.views.components.gap_table import render_gap_table


def render_spy_gap_table_page() -> None:
    st.title("📋 SPY Gap Fill Tracker")
    st.caption("Daily gap fill tracker for SPY — last 30 trading days")

    with st.spinner("Loading SPY data…"):
        gap_data = get_spy_gap_table_data()

    gaps_df = gap_data.get("gaps_df")
    if gaps_df is None or gaps_df.empty:
        st.error("Could not load SPY data. Try again shortly.")
        return

    st.divider()

    render_gap_table(
        gaps_df,
        show_rsi=True,
        show_next_day=True,
        height=900,
    )


render_spy_gap_table_page()
