import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# Inject Streamlit secrets into os.environ so all modules can use os.environ.get()
for _key, _val in st.secrets.items():
    if isinstance(_val, str):
        os.environ.setdefault(_key, _val)

from seo import inject_seo

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IndexIQ — Free S&P 500 Technical Analysis & Screener",
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

# ── Navigation ────────────────────────────────────────────────────────────────
pages = [
    st.Page("views/spy_dashboard.py",   title="SPY Live",               icon="📈", url_path="spy",          default=True),
    st.Page("views/spy_gap_table.py",    title="SPY Gap Table",          icon="📋", url_path="spy-gaps"),
    st.Page("views/ai_forecast_page.py", title="SPY AI Forecast",        icon="🤖", url_path="spy-ai-forecast"),
    st.Page("views/analyzer.py",        title="Stock Analyzer",         icon="🔬", url_path="analyzer"),
    st.Page("views/screener.py",        title="Weekly/Monthly Screener",icon="📊", url_path="screener"),
    st.Page("views/bounce_radar.py",    title="Bounce Radar",           icon="📡", url_path="bounce-radar"),
    st.Page("views/squeeze_scanner.py", title="Squeeze Scanner",        icon="🔥", url_path="squeeze"),
    st.Page("views/strong_buy.py",      title="Strong Buy",             icon="💎", url_path="strong-buy"),
    st.Page("views/strong_sell.py",     title="Strong Sell",            icon="🔻", url_path="strong-sell"),
    st.Page("views/munger_strategy.py", title="Munger Watchlist",       icon="🎩", url_path="munger"),
    st.Page("views/about.py",           title="About",                  icon="ℹ️",  url_path="about"),
]

pg = st.navigation(pages)

# ── Top banner ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    z-index: 9999;
    background: #0F172A;
    padding: 10px 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    font-family: sans-serif;
">
    <span style="font-size: 1.2rem; font-weight: 700; color: #F8FAFC; letter-spacing: 0.5px;">
        IndexIQ
    </span>
</div>
<div style="margin-top: 48px;"></div>
""", unsafe_allow_html=True)

# Hide utility pages (shareable embeds) from the sidebar nav
st.markdown("""
<style>
[data-testid="stSidebarNav"] a[href$="/spy-gaps"],
[data-testid="stSidebarNavLink"] a[href$="/spy-gaps"],
[data-testid="stSidebarNav"] a[href$="/spy-ai-forecast"],
[data-testid="stSidebarNavLink"] a[href$="/spy-ai-forecast"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.caption("Data sourced from Yahoo Finance · Real-time")

pg.run()
