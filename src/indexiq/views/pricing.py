import streamlit as st

from indexiq.premium import MONTHLY_PRICE, STRIPE_PAYMENT_LINK, FREE_TICKER_COUNT, PREMIUM_TICKER_COUNT


def render_pricing() -> None:
    st.title("✨ IndexIQ Premium")
    st.markdown("Upgrade to Premium to unlock the full S&P 500 universe across all screeners.")

    st.markdown("---")

    col_free, col_premium = st.columns(2)

    with col_free:
        st.markdown(
            """
<div style="background:#1E293B; border:1px solid #334155; border-radius:12px; padding:24px;">
    <div style="font-size:1.2rem; font-weight:700; color:#94A3B8;">Free</div>
    <div style="font-size:2rem; font-weight:800; color:#F8FAFC; margin:8px 0;">$0</div>
    <div style="color:#64748B; margin-bottom:16px;">forever</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown(f"""
- ✅ Stock Analyzer (any ticker)
- ✅ SPY Live Dashboard
- ✅ SPY Gap Table
- ✅ SPY AI Forecast (hourly)
- ✅ Top **{FREE_TICKER_COUNT}** S&P 500 tickers in screeners
- ✅ Bounce Radar · Squeeze Scanner
- ✅ Strong Buy / Sell · Munger Watchlist
- ❌ Extended screener universe
- ❌ Priority support
""")

    with col_premium:
        st.markdown(
            f"""
<div style="background:#1E293B; border:2px solid #6366F1; border-radius:12px; padding:24px;">
    <div style="font-size:1.2rem; font-weight:700; color:#818CF8;">Premium</div>
    <div style="font-size:2rem; font-weight:800; color:#F8FAFC; margin:8px 0;">{MONTHLY_PRICE}</div>
    <div style="color:#64748B; margin-bottom:16px;">per month · cancel anytime</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown(f"""
- ✅ Everything in Free
- ✅ Full **{PREMIUM_TICKER_COUNT}** S&P 500 tickers in all screeners
- ✅ Deeper Bounce Radar & Squeeze Scanner results
- ✅ Priority email support
- ✅ Early access to new features
- ✅ Help keep IndexIQ free for everyone
""")
        st.link_button(
            f"Upgrade to Premium — {MONTHLY_PRICE}/mo →",
            STRIPE_PAYMENT_LINK,
            use_container_width=True,
            type="primary",
        )

    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("""
1. Click **Upgrade** above and complete checkout on Stripe (secure, takes 60 seconds)
2. You will receive a **confirmation email** with your personal access code
3. Enter the code in the **✨ Unlock Premium** panel in the sidebar
4. Premium is active instantly — no refresh needed
""")

    st.markdown("---")
    st.markdown("### FAQ")

    with st.expander("Is my payment secure?"):
        st.markdown(
            "Yes. Payments are processed by [Stripe](https://stripe.com), "
            "one of the most trusted payment platforms in the world. "
            "IndexIQ never sees your card details."
        )
    with st.expander("Can I cancel anytime?"):
        st.markdown(
            "Yes. Cancel from the Stripe customer portal or reply to your confirmation "
            "email and we will cancel within 24 hours."
        )
    with st.expander("Do you offer a refund?"):
        st.markdown(
            "If you are not satisfied within the first 7 days, email us and we will "
            "issue a full refund — no questions asked."
        )
    with st.expander("What happens to my data if I cancel?"):
        st.markdown(
            "IndexIQ does not store any personal data beyond your email address. "
            "Cancelling simply revokes your premium access code."
        )


render_pricing()
