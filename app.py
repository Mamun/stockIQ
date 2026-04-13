import streamlit as st

from seo import inject_seo
from views.about import render_about_tab
from views.bounce_radar import render_bounce_radar_tab
from views.screener import render_screener_tab
from views.search import render_search_tab
from views.munger_strategy import render_munger_tab
from views.spx_dashboard import render_spx_dashboard_tab, render_spx_sidebar_ticker
from views.squeeze_scanner import render_squeeze_scanner_tab
from views.strong_buy import render_strong_buy_tab
from views.strong_sell import render_strong_sell_tab

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Market Analyzer — Free S&P 500 Technical Analysis & Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Free stock technical analysis: moving averages, RSI, Fibonacci retracement, "
                 "short squeeze scanner, bounce radar, and Munger quality watchlist."
    },
)

# ── SEO metadata ──────────────────────────────────────────────────────────────
inject_seo()

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
    render_spx_sidebar_ticker()
    st.markdown("---")
    active_tab = st.radio(
        "Navigation",
        ["📈 SPX Live", "🔍 Search by Company", "📊 Weekly/Monthly Screener", "📡 Bounce Radar", "🔥 Squeeze Scanner", "💎 Strong Buy", "🔻 Strong Sell", "🎩 Munger Watchlist", "ℹ️ About"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("Data sourced from Yahoo Finance · Real-time")

# ── Route to view ─────────────────────────────────────────────────────────────
if active_tab == "📈 SPX Live":
    render_spx_dashboard_tab()
elif active_tab == "🔍 Search by Company":
    render_search_tab()
elif active_tab == "📊 Weekly/Monthly Screener":
    render_screener_tab()
elif active_tab == "📡 Bounce Radar":
    render_bounce_radar_tab()
elif active_tab == "🔥 Squeeze Scanner":
    render_squeeze_scanner_tab()
elif active_tab == "💎 Strong Buy":
    render_strong_buy_tab()
elif active_tab == "🔻 Strong Sell":
    render_strong_sell_tab()
elif active_tab == "🎩 Munger Watchlist":
    render_munger_tab()
elif active_tab == "ℹ️ About":
    render_about_tab()
