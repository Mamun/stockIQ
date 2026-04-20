import pandas as pd
import streamlit as st

from stockiq.backend.services.analyzer_service import (
    get_company_display_name,
    get_stock_crosses,
    get_stock_df,
    get_stock_fibonacci,
    get_stock_gaps,
    get_stock_signal,
    search_stocks,
)
from stockiq.frontend.views.components.charts import build_chart
from stockiq.frontend.views.components.gap_table import render_gap_table
from stockiq.frontend.views.components.summary_card import render_stock_summary_card

_PERIODS = {
    "1M":  30,
    "3M":  90,
    "6M":  180,
    "1Y":  365,
    "2Y":  730,
    "5Y":  1825,
}
_DEFAULT_PERIOD = "1Y"


def render_analyzer_tab() -> None:
    st.title("🔬 Stock Analyzer")

    # ── Read URL query params ─────────────────────────────────────────────────
    params     = st.query_params
    url_ticker = params.get("tic", "").upper().strip()
    url_period = params.get("period", _DEFAULT_PERIOD)
    url_rsi    = params.get("rsi", "1") != "0"

    # Seed session state from URL on first load
    if url_ticker and st.session_state.ticker_val != url_ticker:
        st.session_state.ticker_val = url_ticker

    # ── Company search ────────────────────────────────────────────────────────
    col_q, col_btn = st.columns([5, 1])
    search_query = col_q.text_input(
        "company_search",
        placeholder="Search by company name, e.g. Microsoft, Apple, Tesla…",
        label_visibility="collapsed",
    )
    if col_btn.button("Search", width="stretch"):
        if search_query.strip():
            with st.spinner("Searching…"):
                st.session_state.search_results = search_stocks(search_query.strip())
        else:
            st.session_state.search_results = []

    if st.session_state.search_results:
        labels = [
            f"{r['symbol']}  —  {r['name']}  ({r['exchange']})"
            for r in st.session_state.search_results
        ]
        choice_idx = st.selectbox(
            "Select a company", range(len(labels)),
            format_func=lambda i: labels[i],
        )
        st.session_state.ticker_val = st.session_state.search_results[choice_idx]["symbol"]
    elif search_query and not st.session_state.search_results:
        st.caption("No matches found — try a different name.")

    st.markdown("---")

    # ── Ticker + Analyze ──────────────────────────────────────────────────────
    col_ticker, col_btn2 = st.columns([5, 1], vertical_alignment="bottom")
    ticker = col_ticker.text_input(
        "Ticker Symbol", value=st.session_state.ticker_val, max_chars=10,
    ).upper().strip()
    analyze_btn = col_btn2.button("Analyze", width="stretch", type="primary")

    # Auto-analyze when ticker arrives via URL and isn't already cached
    auto_analyze = bool(url_ticker) and url_ticker != st.session_state.get("analyzer_ticker")

    if not (analyze_btn or auto_analyze or ticker):
        st.info("Enter a ticker symbol above and click **Analyze**.")
        return
    if not ticker:
        st.warning("Enter a ticker symbol above.")
        return

    # ── Fetch & compute (cached in session state; re-runs only on new ticker) ─
    if analyze_btn or auto_analyze or st.session_state.get("analyzer_ticker") != ticker:
        with st.spinner(f"Fetching data for **{ticker}**…"):
            try:
                raw = get_stock_df(ticker)
            except Exception as e:
                st.error(f"Failed to download data: {e}")
                return

        if raw.empty:
            st.error(f"No data found for **{ticker}**. Check the ticker symbol and try again.")
            return
        if len(raw) < 2:
            st.error(f"**{ticker}** returned insufficient price data.")
            return

        st.session_state.analyzer_df      = raw
        st.session_state.analyzer_ticker  = ticker
        st.session_state.analyzer_company = get_company_display_name(ticker)

        # Update URL to reflect the loaded ticker
        st.query_params["tic"] = ticker

    df           = st.session_state.analyzer_df
    company_name = st.session_state.analyzer_company
    sig          = get_stock_signal(df)
    latest, prev = sig["latest"], sig["prev"]
    score, label, color = sig["score"], sig["label"], sig["color"]

    # ── Overview card ─────────────────────────────────────────────────────────
    st.markdown(f"#### {company_name}  ({ticker})")
    render_stock_summary_card(latest, prev, df, label, color, score)

    st.markdown("---")

    # ── Chart section ─────────────────────────────────────────────────────────
    valid_period = url_period if url_period in _PERIODS else _DEFAULT_PERIOD

    period_col, rsi_col = st.columns([6, 1])
    with period_col:
        selected_period = st.radio(
            "period_selector", list(_PERIODS), horizontal=True,
            index=list(_PERIODS).index(valid_period),
            label_visibility="collapsed",
        )
    show_rsi = rsi_col.checkbox("RSI", value=url_rsi)

    # Keep URL in sync with current chart state (no rerun — just updates address bar)
    st.query_params["tic"]    = ticker
    st.query_params["period"] = selected_period
    st.query_params["rsi"]    = "1" if show_rsi else "0"

    cutoff     = pd.Timestamp.today() - pd.Timedelta(days=_PERIODS[selected_period])
    display_df = df[df.index >= cutoff].copy()

    if len(display_df) < 2:
        st.warning(f"Not enough data for the **{selected_period}** window. Try a longer period.")
        return

    fib = get_stock_fibonacci(display_df)
    golden, death = get_stock_crosses(display_df)
    fig = build_chart(display_df, fib, ticker,
                      show_vol=True, show_fib=False,
                      show_patterns=True, show_rsi=show_rsi,
                      golden_dates=golden, death_dates=death)
    st.plotly_chart(fig, width="stretch")

    # ── Gap table ─────────────────────────────────────────────────────────────
    last = display_df.iloc[-1]
    gaps_df = get_stock_gaps(
        display_df,
        {"day_high": float(last["High"]), "day_low": float(last["Low"])},
    )
    if "RSI" in display_df.columns:
        gaps_df = gaps_df.copy()
        rsi_dedup = display_df["RSI"][~display_df.index.duplicated(keep="last")]
        gaps_df["RSI"] = rsi_dedup.reindex(gaps_df.index)

    render_gap_table(gaps_df, show_rsi=True)


# ── Session state & page entry point ──────────────────────────────────────────
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "ticker_val" not in st.session_state:
    st.session_state.ticker_val = "MSFT"
if "analyzer_df" not in st.session_state:
    st.session_state.analyzer_df = None
if "analyzer_ticker" not in st.session_state:
    st.session_state.analyzer_ticker = None
if "analyzer_company" not in st.session_state:
    st.session_state.analyzer_company = None

render_analyzer_tab()
