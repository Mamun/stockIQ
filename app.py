import streamlit as st

from views.about import render_about_tab
from views.bounce_radar import render_bounce_radar_tab
from views.screener import render_screener_tab
from views.search import render_search_tab
from views.squeeze_scanner import render_squeeze_scanner_tab

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Market Analyzer - Technical Analysis & Trading Signals",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Stock Market Analyzer: Real-time technical analysis with moving averages, "
                 "Fibonacci retracement, and reversal pattern detection."
    },
)

# ── SEO metadata ──────────────────────────────────────────────────────────────
st.markdown("""
    <meta property="og:title" content="Stock Market Analyzer - Technical Analysis Tool" />
    <meta property="og:description" content="Free stock technical analysis with moving averages, Fibonacci levels, reversal patterns, and buy/sell signals." />
    <meta property="og:type" content="website" />
    <meta name="description" content="Real-time stock market analyzer with MA5/20/50/100/200, Fibonacci retracement, and reversal pattern detection." />
    <meta name="keywords" content="stock analysis, technical analysis, moving averages, Fibonacci retracement, trading signals, stock market" />
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "WebApplication",
        "name": "Stock Market Analyzer",
        "description": "Technical analysis tool with moving averages, Fibonacci levels, and reversal pattern detection",
        "applicationCategory": "FinanceApplication",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
    }
    </script>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "ticker_val" not in st.session_state:
    st.session_state.ticker_val = "MSFT"

# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 Stock Market Analyzer")
    st.caption("Technical Analysis Tool")
    st.markdown("---")
    active_tab = st.radio(
        "Navigation",
        ["🔍 Search by Company", "📊 Weekly/Monthly Screener", "📡 Bounce Radar", "🔥 Squeeze Scanner", "ℹ️ About"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("Data sourced from Yahoo Finance · Real-time")

# ── Route to view ─────────────────────────────────────────────────────────────
if active_tab == "🔍 Search by Company":
    render_search_tab()
elif active_tab == "📊 Weekly/Monthly Screener":
    render_screener_tab()
elif active_tab == "📡 Bounce Radar":
    render_bounce_radar_tab()
elif active_tab == "🔥 Squeeze Scanner":
    render_squeeze_scanner_tab()
elif active_tab == "ℹ️ About":
    render_about_tab()
