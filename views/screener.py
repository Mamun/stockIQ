import streamlit as st

from config import SCREENER_TICKER_COUNT
from data import fetch_spx_recommendations


def render_screener_tab() -> None:
    st.title("📊 Weekly/Monthly Screener")
    st.markdown("🟢 **Green** = Close > Open | 🔴 **Red** = Close < Open")
    st.markdown("**Signal**: BUY if all 4 weeks are green AND at least 3 months green, otherwise SELL")
    st.caption(f"Analyzing top {SCREENER_TICKER_COUNT} S&P 500 stocks · configurable via `SCREENER_TICKER_COUNT` env var")
    st.markdown("---")

    if not st.button("🔄 Generate Recommendations", use_container_width=True, type="primary"):
        return

    with st.spinner(f"📊 Analyzing top {SCREENER_TICKER_COUNT} SPX stocks…"):
        recs_df = fetch_spx_recommendations()

    if recs_df.empty:
        st.warning("Could not fetch recommendation data. Please try again.")
        return

    st.success(f"✅ Analyzed {len(recs_df)} stocks")

    display_cols = [
        "Ticker", "Company", "Last Price",
        "🔷 Weeks", "Green Weeks",
        "🔶 Months", "Green Months",
        "Signal",
    ]
    buy_df  = recs_df[recs_df["Signal"] == "🟢 BUY"]
    sell_df = recs_df[recs_df["Signal"] == "🔴 SELL"]

    if not buy_df.empty:
        st.markdown("### 🟢 BUY Recommendations")
        st.dataframe(buy_df[display_cols], use_container_width=True, hide_index=True)

    if not sell_df.empty:
        st.markdown("### 🔴 SELL / HOLD")
        st.dataframe(sell_df[display_cols], use_container_width=True, hide_index=True)
