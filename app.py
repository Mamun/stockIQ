import os
import sys
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
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

def _show_overloaded_page():
    st.markdown("""
    <style>
    .overload-wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 80px 24px 40px;
        text-align: center;
        font-family: sans-serif;
    }
    .overload-icon { font-size: 4rem; margin-bottom: 12px; }
    .overload-title {
        font-size: 2rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 8px;
    }
    .overload-sub {
        font-size: 1.1rem;
        color: #94A3B8;
        max-width: 520px;
        line-height: 1.6;
        margin-bottom: 36px;
    }
    .sponsor-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 32px 40px;
        max-width: 520px;
        width: 100%;
    }
    .sponsor-card h3 {
        color: #F1C40F;
        font-size: 1.3rem;
        margin-bottom: 10px;
    }
    .sponsor-card p {
        color: #CBD5E1;
        font-size: 0.95rem;
        line-height: 1.6;
        margin-bottom: 24px;
    }
    .sponsor-btn {
        display: inline-block;
        background: #F1C40F;
        color: #0F172A !important;
        font-weight: 700;
        font-size: 1rem;
        padding: 12px 32px;
        border-radius: 8px;
        text-decoration: none !important;
    }
    .sponsor-btn:hover { background: #F9D923; }
    </style>

    <div class="overload-wrap">
        <div class="overload-icon">📈</div>
        <div class="overload-title">IndexIQ is temporarily unavailable</div>
        <div class="overload-sub">
            We're experiencing higher than usual traffic and the app is currently overloaded.
            Our free tier has limited resources — we're working to bring it back online shortly.
        </div>
        <div class="sponsor-card">
            <h3>❤️ Help us stay online for everyone</h3>
            <p>
                IndexIQ is free and open source. Your sponsorship directly funds server capacity,
                faster data feeds, and new features — so more traders can access professional-grade
                technical analysis without paying a subscription.
            </p>
            <a class="sponsor-btn"
               href="https://github.com/sponsors/Mamun"
               target="_blank" rel="noopener noreferrer">
               Become a Sponsor
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

try:
    # Inject Streamlit secrets into os.environ so all modules can use os.environ.get()
    for _key, _val in st.secrets.items():
        if isinstance(_val, str):
            os.environ.setdefault(_key, _val)

    # Ensure src/ is on the path so `indexiq` resolves on Streamlit Cloud
    _src = os.path.join(os.path.dirname(__file__), "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    from indexiq.views.seo import inject_seo

except Exception:
    _show_overloaded_page()

# ── SEO metadata ──────────────────────────────────────────────────────────────
inject_seo()

# ── Navigation ────────────────────────────────────────────────────────────────
pages = {
    "Market": [
        st.Page("src/indexiq/views/spy_dashboard.py",    title="SPY Dashboard",           icon="📈", url_path="spy",             default=True),
        st.Page("src/indexiq/views/ai_forecast_page.py", title="AI 10-Day Forecast",       icon="🤖", url_path="spy-ai-forecast"),
        st.Page("src/indexiq/views/spy_gap_table.py",    title="SPY Gap Table",           icon="📋", url_path="spy-gaps"),
    ],
    "S&P 500 Tools": [
        st.Page("src/indexiq/views/analyzer.py",         title="Stock Analyzer",          icon="🔬", url_path="analyzer"),
        st.Page("src/indexiq/views/screener.py",         title="Candle Screener",         icon="📊", url_path="screener"),
    ],
    "Scanners": [
        st.Page("src/indexiq/views/scanner_premarket.py",       title="Pre-Market Scanner",     icon="🌅", url_path="premarket"),
        st.Page("src/indexiq/views/scanner_nasdaq_rsi.py",      title="NASDAQ RSI Scanner",     icon="📊", url_path="nasdaq-oversold"),
        st.Page("src/indexiq/views/scanner_bounce_radar.py",    title="MA200 Bounce Radar",     icon="📡", url_path="bounce-radar"),
        st.Page("src/indexiq/views/scanner_squeeze.py",         title="Short Squeeze Scanner",  icon="🔥", url_path="squeeze"),
        st.Page("src/indexiq/views/scanner_strong_buy.py",      title="Analyst Buy Picks",      icon="💎", url_path="strong-buy"),
        st.Page("src/indexiq/views/scanner_strong_sell.py",     title="Analyst Sell Picks",     icon="🔻", url_path="strong-sell"),
        st.Page("src/indexiq/views/scanner_munger_strategy.py", title="Munger Value Picks",     icon="🎩", url_path="munger"),
    ],
    "Info": [
        st.Page("src/indexiq/views/about.py",            title="About IndexIQ",           icon="ℹ️",  url_path="about"),
    ],
}

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
[data-testid="stSidebarNavLink"] a[href$="/spy-gaps"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.caption("Data sourced from Yahoo Finance · Real-time")

pg.run()
