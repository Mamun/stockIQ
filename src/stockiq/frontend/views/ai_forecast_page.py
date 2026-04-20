import streamlit as st

from stockiq.backend.services.spy_service import get_spy_gap_table_data
from stockiq.frontend.views.ai_forecast import render_ai_forecast


def render_ai_forecast_page() -> None:
    st.title("🤖 SPY AI Outlook")
    st.caption("AI-generated SPY price outlook · Updates hourly · Powered by your choice of AI provider")

    with st.expander("How is this forecast generated?", expanded=False):
        st.markdown("""
**Data inputs (updated hourly)**
- Last 15 trading days of SPY opening gaps, gap fill status, and RSI
- Live SPY price, prev close, day high/low

**AI reasoning (Claude Opus)**
- Identifies unfilled gaps above/below current price — these act as price magnets
- Reads RSI zone (overbought ≥ 70 / oversold ≤ 30) to gauge reversal probability
- Analyses recent next-day momentum patterns (▲/▼ streaks)
- Calibrates confidence and range width based on signal strength

**Output**
- 10 trading days of directional bias, estimated close, intraday range, and a one-line reason
- Refreshes automatically every hour during market hours
""")

    with st.spinner("Loading SPY data…"):
        gap_data = get_spy_gap_table_data()

    if gap_data["gaps_df"].empty:
        st.error("Could not load SPY data. Try again shortly.")
        return

    render_ai_forecast(gap_data["gaps_df"], gap_data["quote"], show_share_btn=False)


render_ai_forecast_page()
