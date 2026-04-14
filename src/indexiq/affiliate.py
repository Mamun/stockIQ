"""
Affiliate link definitions and rendering helpers.

Replace the `ref_url` values with your personal referral URLs from each broker.
All links open in a new tab.
"""

from __future__ import annotations

import streamlit as st

# ── Broker definitions ────────────────────────────────────────────────────────
# Replace ref_url with your actual affiliate / referral link.

BROKERS: list[dict] = [
    {
        "name":    "Webull",
        "logo":    "🟣",
        "tagline": "Commission-free trading · Up to 12 free stocks on sign-up",
        "cta":     "Open Webull account →",
        "ref_url": "https://a.webull.com/i/YOUR_REFERRAL_CODE",
        "commission": "Commission-free",
    },
    {
        "name":    "Interactive Brokers",
        "logo":    "🔵",
        "tagline": "Global markets · Low margin rates · Advanced tools",
        "cta":     "Open IBKR account →",
        "ref_url": "https://ibkr.com/referral/YOUR_REFERRAL_CODE",
        "commission": "Up to $1,000 cash bonus",
    },
    {
        "name":    "TradingView",
        "logo":    "📈",
        "tagline": "Advanced charting & screening · Used by 50M+ traders",
        "cta":     "Try TradingView Pro →",
        "ref_url": "https://www.tradingview.com/?aff_id=YOUR_AFF_ID",
        "commission": "30% recurring commission",
    },
]


# ── Renderers ─────────────────────────────────────────────────────────────────

def render_broker_cards() -> None:
    """Full broker cards — use on the About page."""
    st.markdown("### Recommended Brokers")
    st.caption(
        "IndexIQ partners with these brokers. If you sign up using our links, "
        "we may earn a commission at no extra cost to you."
    )
    cols = st.columns(len(BROKERS))
    for col, broker in zip(cols, BROKERS):
        with col:
            st.markdown(
                f"""
<div style="
    background:#1E293B; border:1px solid #334155; border-radius:10px;
    padding:16px; text-align:center; height:100%;
">
    <div style="font-size:2rem;">{broker['logo']}</div>
    <div style="font-weight:700; color:#F8FAFC; margin:8px 0 4px;">{broker['name']}</div>
    <div style="font-size:0.8rem; color:#94A3B8; margin-bottom:12px;">{broker['tagline']}</div>
    <div style="font-size:0.75rem; color:#22C55E; margin-bottom:12px; font-weight:600;">
        {broker['commission']}
    </div>
</div>
""",
                unsafe_allow_html=True,
            )
            st.link_button(
                broker["cta"],
                broker["ref_url"],
                use_container_width=True,
            )


def render_trade_buttons(ticker: str) -> None:
    """Compact "Trade on…" buttons — use inside the Stock Analyzer."""
    st.markdown("#### Trade this stock")
    st.caption("Open a position directly in your broker — affiliate links help keep IndexIQ free.")
    cols = st.columns(len(BROKERS))
    for col, broker in zip(cols, BROKERS):
        # Webull and IBKR support deep-linking to a ticker search
        url = broker["ref_url"]
        if broker["name"] == "Webull":
            url = f"https://a.webull.com/i/YOUR_REFERRAL_CODE&tickerId={ticker}"
        elif broker["name"] == "TradingView":
            url = f"https://www.tradingview.com/chart/?symbol={ticker}&aff_id=YOUR_AFF_ID"
        with col:
            st.link_button(
                f"{broker['logo']} {broker['name']}",
                url,
                use_container_width=True,
            )


def render_sidebar_banner() -> None:
    """Single compact affiliate line in sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.caption("📣 Commission-free trading on [Webull](https://a.webull.com/i/YOUR_REFERRAL_CODE)")
