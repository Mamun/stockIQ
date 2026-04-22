import os
import sys
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Stock Screener & AI Analyzer — StockIQ",
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
        <div class="overload-title">StockIQ is temporarily unavailable</div>
        <div class="overload-sub">
            We're experiencing higher than usual traffic and the app is currently overloaded.
            Our free tier has limited resources — we're working to bring it back online shortly.
        </div>
        <div class="sponsor-card">
            <h3>❤️ Help us stay online for everyone</h3>
            <p>
                StockIQ is free and open source. Your sponsorship directly funds server capacity,
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
    # Inject Streamlit secrets into os.environ (Streamlit Cloud only — no-op locally)
    try:
        for _key, _val in st.secrets.items():
            if isinstance(_val, str):
                os.environ[_key] = _val  # always override .env so Cloud secrets win

        # Service account JSON stored as a TOML table in Streamlit secrets.
        # Streamlit Cloud has no persistent filesystem, so we write the key to a
        # temp file and point GOOGLE_APPLICATION_CREDENTIALS at it.
        if "gcs_service_account" in st.secrets:
            import json, tempfile
            _sa = dict(st.secrets["gcs_service_account"])
            _sa_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            )
            json.dump(_sa, _sa_file)
            _sa_file.flush()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _sa_file.name
    except Exception:
        pass  # No secrets configured locally — credentials come from .env

    # Ensure src/ is on the path so `stockiq` resolves on Streamlit Cloud
    _src = os.path.join(os.path.dirname(__file__), "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    from stockiq.frontend.views.seo import inject_seo

except Exception:
    _show_overloaded_page()

# ── SEO metadata ──────────────────────────────────────────────────────────────
inject_seo()

# ── Navigation ────────────────────────────────────────────────────────────────
pages = {
    "Market": [
        st.Page("src/stockiq/frontend/views/spy_dashboard.py",    title="SPY Dashboard",       icon="📈", url_path="spy",             default=True),
        st.Page("src/stockiq/frontend/views/volatility.py",       title="Volatility / VIX",    icon="📉", url_path="volatility"),
        st.Page("src/stockiq/frontend/views/ai_forecast_page.py", title="SPY AI Outlook",      icon="🤖", url_path="spy-ai-forecast"),
        st.Page("src/stockiq/frontend/views/spy_gap_table.py",    title="SPY Gap Table",        icon="📋", url_path="spy-gaps"),
    ],
    "S&P 500 Tools": [
        st.Page("src/stockiq/frontend/views/analyzer.py",         title="Stock Analyzer",      icon="🔬", url_path="analyzer"),
        st.Page("src/stockiq/frontend/views/candle_momentum_screener.py",         title="Candle Screener",     icon="📊", url_path="screener"),
    ],
    "Scanners": [
        st.Page("src/stockiq/frontend/views/premarket_scanner.py",       title="Pre-Market Scanner",    icon="🌅", url_path="premarket"),
        st.Page("src/stockiq/frontend/views/nasdaq_rsi_scanner.py",      title="NASDAQ RSI Scanner",    icon="📊", url_path="nasdaq-oversold"),
        st.Page("src/stockiq/frontend/views/bounce_radar_scanner.py",    title="MA200 Bounce Radar",    icon="📡", url_path="bounce-radar"),
        st.Page("src/stockiq/frontend/views/squeeze_scanner.py",         title="Short Squeeze Scanner", icon="🔥", url_path="squeeze"),
        st.Page("src/stockiq/frontend/views/strong_buy_scanner.py",      title="Analyst Buy Picks",     icon="💎", url_path="strong-buy"),
        st.Page("src/stockiq/frontend/views/strong_sell_scanner.py",     title="Analyst Sell Picks",    icon="🔻", url_path="strong-sell"),
        st.Page("src/stockiq/frontend/views/munger_strategy_scanner.py", title="Munger Value Picks",    icon="🎩", url_path="munger"),
        st.Page("src/stockiq/frontend/views/etf_scanner.py",             title="ETF Scanner",           icon="🌐", url_path="etf-scanner"),
    ],
    "Info": [
        st.Page("src/stockiq/frontend/views/about.py",            title="About StockIQ",       icon="ℹ️",  url_path="about"),
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
        StockIQ
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
    # ── Buy Me a Coffee ───────────────────────────────────────────────────────
    st.markdown("""
<a href="https://buymeacoffee.com/mamuninfo" target="_blank" rel="noopener noreferrer"
   style="display:block; text-decoration:none;">
  <div style="
    background: #FFDD00;
    color: #000000;
    font-weight: 700;
    font-size: 0.875rem;
    text-align: center;
    padding: 10px 16px;
    border-radius: 8px;
    margin-bottom: 4px;
  ">
    ☕ Buy Me a Coffee
  </div>
</a>
""", unsafe_allow_html=True)
    st.caption("Enjoying StockIQ? A coffee keeps it free ❤️")

    st.markdown("---")

    # ── Affiliate links ───────────────────────────────────────────────────────
    st.markdown("**🤝 Recommended Broker**")
    st.markdown("""
<div style="margin-top:6px;">
  <a href="https://act.webull.com/kol-us/share.html?hl=en&inviteCode=stockiq" target="_blank" rel="noopener noreferrer"
     style="
       display:block; text-decoration:none;
       background:#1E293B; border:1px solid #334155;
       border-radius:7px; padding:9px 12px;
     ">
    <div style="font-size:0.82rem; font-weight:700; color:#F8FAFC;">Webull</div>
    <div style="font-size:0.75rem; color:#94A3B8; margin-top:2px;">Commission-free · Get free stocks</div>
  </a>
</div>
<div style="font-size:0.7rem; color:#475569; margin-top:8px;">
  Affiliate link — we may earn a commission at no cost to you.
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.caption("Data sourced from Yahoo Finance · Real-time")

pg.run()
