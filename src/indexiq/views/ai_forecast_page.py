import streamlit as st

from indexiq.data import fetch_spx_intraday
from indexiq.models.indicators import compute_daily_gaps, compute_rsi
from indexiq.views.ai_forecast import render_ai_forecast


def render_ai_forecast_page() -> None:
    st.title("🤖 SPY AI Forecast")
    st.caption("AI-generated SPY price forecast · Updates hourly · Powered by Claude")

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
        daily_df = fetch_spx_intraday(period="1y", interval="1d")

    if daily_df.empty:
        st.error("Could not load SPY data. Try again shortly.")
        return

    gaps_df   = compute_daily_gaps(daily_df).copy()
    rsi_dedup = compute_rsi(daily_df)[~daily_df.index.duplicated(keep="last")]
    gaps_df["RSI"] = rsi_dedup.reindex(gaps_df.index)

    render_ai_forecast(gaps_df, show_share_btn=False)


render_ai_forecast_page()
