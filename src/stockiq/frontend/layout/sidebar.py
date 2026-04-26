import streamlit as st


def render_sidebar() -> None:
    """Sidebar content: sponsor button, affiliate broker card, data caption."""
    with st.sidebar:
        st.markdown(
            """
<a href="https://buymeacoffee.com/mamuninfo" target="_blank" rel="noopener noreferrer"
   style="display:block; text-decoration:none;">
  <div style="
    background: #FFDD00; color: #000000; font-weight: 700; font-size: 0.875rem;
    text-align: center; padding: 10px 16px; border-radius: 8px; margin-bottom: 4px;
  ">
    ☕ Buy Me a Coffee
  </div>
</a>
""",
            unsafe_allow_html=True,
        )
        st.caption("Enjoying StockIQ? A coffee keeps it free ❤️")

        st.markdown("---")

        st.markdown("**🤝 Recommended Broker**")
        st.markdown(
            """
<div style="margin-top:6px;">
  <a href="https://act.webull.com/kol-us/share.html?hl=en&inviteCode=stockiq"
     target="_blank" rel="noopener noreferrer"
     style="
       display:block; text-decoration:none;
       background:#1E293B; border:1px solid #334155;
       border-radius:7px; padding:9px 12px;
     ">
    <div style="font-size:0.82rem; font-weight:700; color:#F8FAFC;">Webull</div>
    <div style="font-size:0.75rem; color:#94A3B8; margin-top:2px;">
      Commission-free · Get free stocks
    </div>
  </a>
</div>
<div style="font-size:0.7rem; color:#475569; margin-top:8px;">
  Affiliate link — we may earn a commission at no cost to you.
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.caption("Data sourced from Yahoo Finance · Real-time")
