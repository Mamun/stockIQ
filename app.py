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
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 80px 24px 40px;
        text-align: center; font-family: sans-serif;
    }
    .overload-icon { font-size: 4rem; margin-bottom: 12px; }
    .overload-title { font-size: 2rem; font-weight: 700; color: #F8FAFC; margin-bottom: 8px; }
    .overload-sub {
        font-size: 1.1rem; color: #94A3B8; max-width: 520px;
        line-height: 1.6; margin-bottom: 36px;
    }
    .sponsor-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155; border-radius: 16px;
        padding: 32px 40px; max-width: 520px; width: 100%;
    }
    .sponsor-card h3 { color: #F1C40F; font-size: 1.3rem; margin-bottom: 10px; }
    .sponsor-card p { color: #CBD5E1; font-size: 0.95rem; line-height: 1.6; margin-bottom: 24px; }
    .sponsor-btn {
        display: inline-block; background: #F1C40F; color: #0F172A !important;
        font-weight: 700; font-size: 1rem; padding: 12px 32px;
        border-radius: 8px; text-decoration: none !important;
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
                os.environ[_key] = _val

        if "gcs_service_account" in st.secrets:
            import json, tempfile
            _sa = dict(st.secrets["gcs_service_account"])
            _sa_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            json.dump(_sa, _sa_file)
            _sa_file.flush()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _sa_file.name
    except Exception:
        pass

    _src = os.path.join(os.path.dirname(__file__), "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    from stockiq.frontend.layout.banner import render_top_banner
    from stockiq.frontend.layout.nav import get_pages
    from stockiq.frontend.layout.sidebar import render_sidebar
    from stockiq.frontend.views.seo import inject_seo

except Exception:
    _show_overloaded_page()

# ── SEO metadata ──────────────────────────────────────────────────────────────
inject_seo()

# ── Navigation + shell ────────────────────────────────────────────────────────
pg = st.navigation(get_pages())
render_top_banner()
render_sidebar()
pg.run()
