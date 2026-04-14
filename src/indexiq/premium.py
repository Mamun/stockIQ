"""
Premium tier utilities.

Flow:
  1. User buys on Stripe via STRIPE_PAYMENT_LINK.
  2. You add their access code to st.secrets["PREMIUM_CODES"] (comma-separated).
  3. User enters the code in the sidebar widget → session unlocked.

No backend / webhook required for the MVP.  When you're ready to automate,
replace _get_premium_codes() with a Stripe subscription lookup.
"""

import os

import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

STRIPE_PAYMENT_LINK: str = os.environ.get(
    "STRIPE_PAYMENT_LINK",
    "https://buy.stripe.com/YOUR_PAYMENT_LINK",   # replace in Streamlit secrets
)

MONTHLY_PRICE = "$9"

FREE_TICKER_COUNT  = 50
PREMIUM_TICKER_COUNT = 100   # full _SPX_UNIVERSE


# ── State helpers ─────────────────────────────────────────────────────────────

def is_premium() -> bool:
    """True when the current session has an active premium access code."""
    return bool(st.session_state.get("is_premium", False))


def _load_codes() -> set[str]:
    try:
        raw = st.secrets.get("PREMIUM_CODES", "") or os.environ.get("PREMIUM_CODES", "")
    except Exception:
        raw = os.environ.get("PREMIUM_CODES", "")
    return {c.strip().lower() for c in raw.split(",") if c.strip()}


def _activate(code: str) -> bool:
    if code.strip().lower() in _load_codes():
        st.session_state.is_premium = True
        return True
    return False


# ── Sidebar widget ────────────────────────────────────────────────────────────

def render_premium_sidebar() -> None:
    """Call once from app.py sidebar — shows status or unlock form."""
    if is_premium():
        st.sidebar.markdown("---")
        st.sidebar.success("✨ Premium active")
        if st.sidebar.button("Deactivate", key="_premium_deactivate"):
            st.session_state.is_premium = False
            st.rerun()
        return

    st.sidebar.markdown("---")
    with st.sidebar.expander("✨ Unlock Premium", expanded=False):
        st.markdown(
            f"**{MONTHLY_PRICE}/mo** · Expand screeners to 100 tickers · "
            "Priority support",
            unsafe_allow_html=False,
        )
        st.link_button("Get access →", STRIPE_PAYMENT_LINK, use_container_width=True)
        st.markdown("Already have a code?")
        code = st.text_input("Access code", type="password", key="_premium_code_input",
                             label_visibility="collapsed", placeholder="Enter access code")
        if st.button("Activate", key="_premium_activate", use_container_width=True):
            if _activate(code):
                st.success("Premium unlocked!")
                st.rerun()
            else:
                st.error("Invalid code — check your confirmation email.")


# ── Inline upgrade prompt ─────────────────────────────────────────────────────

def render_upgrade_prompt(feature: str, detail: str = "") -> None:
    """Drop-in CTA shown inside a page when a premium feature is gated."""
    st.markdown("---")
    col_text, col_btn = st.columns([3, 1])
    with col_text:
        st.markdown(
            f"✨ **{feature}** is a Premium feature.  \n"
            + (detail or f"Upgrade to {MONTHLY_PRICE}/mo to unlock it.")
        )
    with col_btn:
        st.link_button("Upgrade →", STRIPE_PAYMENT_LINK, use_container_width=True)
    st.markdown("---")
