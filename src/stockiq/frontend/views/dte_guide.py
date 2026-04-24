import os
import streamlit as st
import streamlit.components.v1 as components

_HTML_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "spy-0dte-guide.html")

st.markdown(
    """
    <style>
    /* Remove default Streamlit page padding so the embedded guide fills the width */
    .block-container { padding-top: 0 !important; padding-left: 0 !important; padding-right: 0 !important; max-width: 100% !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

with open(os.path.abspath(_HTML_PATH), "r", encoding="utf-8") as _f:
    _html = _f.read()

components.html(_html, height=5500, scrolling=True)
