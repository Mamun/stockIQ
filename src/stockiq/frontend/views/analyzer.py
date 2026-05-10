"""Stock Analyzer page — thin orchestrator that composes panels."""

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from stockiq.backend.services.analyzer_service import (
    get_company_display_name,
    get_stock_df,
    get_stock_fibonacci,
    get_stock_gaps,
    get_stock_signal,
    get_ticker_fundamentals,
    search_stocks,
)
from stockiq.frontend.theme import BG, DN, MUT, NEU, SEP, UP, VAL
from stockiq.frontend.views.components.gap_table import render_gap_table
from stockiq.frontend.views.panels.analyzer_fundamentals import render_fundamentals_panel
from stockiq.frontend.views.panels.analyzer_signals import (
    render_buying_pressure,
    render_signal_analysis,
)

_PERIODS = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "5Y": 1825}
_DEFAULT_PERIOD = "1Y"


def render_analyzer_tab() -> None:
    st.title("🔬 Stock Analyzer")

    params     = st.query_params
    url_ticker = params.get("tic", "").upper().strip()
    url_period = params.get("period", _DEFAULT_PERIOD)
    url_rsi    = params.get("rsi", "1") != "0"

    if url_ticker and st.session_state.ticker_val != url_ticker:
        st.session_state.ticker_val = url_ticker

    # ── Search + Ticker + Actions (single row) ───────────────────────────────
    col_q, col_t, col_srch, col_analyze = st.columns([3, 2, 1, 1], vertical_alignment="bottom")
    search_query = col_q.text_input(
        "company_search",
        placeholder="Company name, e.g. Microsoft…",
        label_visibility="collapsed",
    )
    ticker = col_t.text_input(
        "Ticker Symbol", value=st.session_state.ticker_val, max_chars=10,
        placeholder="Ticker, e.g. MSFT",
    ).upper().strip()
    search_clicked = col_srch.button("Search", width="stretch")
    analyze_btn = col_analyze.button("Analyze", width="stretch", type="primary")

    if search_clicked:
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
            "Select a company", range(len(labels)), format_func=lambda i: labels[i]
        )
        st.session_state.ticker_val = st.session_state.search_results[choice_idx]["symbol"]
        ticker = st.session_state.ticker_val
    elif search_query and not st.session_state.search_results:
        st.caption("No matches found — try a different name.")

    auto_analyze = bool(url_ticker) and url_ticker != st.session_state.get("analyzer_ticker")

    if not (analyze_btn or auto_analyze or ticker):
        st.info("Enter a ticker symbol above and click **Analyze**.")
        return
    if not ticker:
        st.warning("Enter a ticker symbol above.")
        return

    # ── Fetch & cache data ────────────────────────────────────────────────────
    if analyze_btn or auto_analyze or st.session_state.get("analyzer_ticker") != ticker:
        with st.spinner(f"Fetching data for **{ticker}**…"):
            try:
                raw = get_stock_df(ticker)
            except Exception as e:
                st.error(f"Failed to download data: {e}")
                return
        if raw.empty:
            st.error(
                f"No data found for **{ticker}**. "
                "Use the Search box above to find the correct symbol."
            )
            return
        if len(raw) < 2:
            st.error(f"**{ticker}** returned insufficient price data.")
            return

        st.session_state.analyzer_df           = raw
        st.session_state.analyzer_ticker       = ticker
        st.session_state.analyzer_company      = get_company_display_name(ticker)
        st.session_state.analyzer_fundamentals = get_ticker_fundamentals(ticker)
        st.query_params["tic"] = ticker

    df           = st.session_state.analyzer_df
    company_name = st.session_state.analyzer_company
    sig          = get_stock_signal(df)
    latest, prev = sig["latest"], sig["prev"]
    score, signal_label, signal_color = sig["score"], sig["label"], sig["color"]

    price      = float(latest["Close"])
    prev_close = float(prev["Close"])
    chg        = price - prev_close
    chg_pct    = chg / prev_close * 100
    chg_clr    = UP if chg >= 0 else DN
    arrow      = "▲" if chg >= 0 else "▼"

    last_252 = df.tail(252)
    w52_high = float(last_252["High"].max())
    w52_low  = float(last_252["Low"].min())

    rsi_val = float(latest.get("RSI",   0) or 0)
    ma200   = float(latest.get("MA200", 0) or 0)
    vol_now = float(latest.get("Volume", 0) or 0)
    vol_avg = (
        float(df["Volume"].rolling(20).mean().iloc[-1])
        if "Volume" in df.columns else 0.0
    )

    # ── Sections 1 + 2: Combined header + quick stats ────────────────────────
    # Company name + price + signal badge — all on one line
    st.markdown(
        f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">'
        f'<span style="font-size:1.25rem;font-weight:700;color:{VAL}">{company_name}</span>'
        f'<span style="color:{MUT};font-size:0.9rem">{ticker}</span>'
        f'<span style="font-size:1.5rem;font-weight:800;color:{VAL};margin-left:8px">'
        f'${price:,.2f}</span>'
        f'<span style="font-size:0.9rem;color:{chg_clr}">'
        f'{arrow} {abs(chg):.2f} ({chg_pct:+.2f}%)</span>'
        f'<span style="background:{signal_color};color:#fff;font-size:0.82rem;font-weight:700;'
        f'padding:3px 14px;border-radius:20px;letter-spacing:.04em;margin-left:8px">'
        f'{signal_label}</span>'
        f'<span style="color:{MUT};font-size:0.78rem">Score {score:+d}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Quick stats as compact table
    stat_rows = []
    if w52_high > w52_low:
        pos_pct   = (price - w52_low) / (w52_high - w52_low) * 100
        range_clr = UP if pos_pct >= 50 else DN
        stat_rows.append(("52W Range", f"{pos_pct:.1f}% of range",
                           f"${w52_low:,.2f} — ${w52_high:,.2f}", range_clr))
    if rsi_val:
        rsi_clr = DN if rsi_val >= 70 else UP if rsi_val <= 30 else NEU
        rsi_lbl = "Overbought" if rsi_val >= 70 else "Oversold" if rsi_val <= 30 else "Neutral"
        stat_rows.append(("RSI (14)", f"{rsi_val:.1f}", rsi_lbl, rsi_clr))
    if ma200:
        diff200   = (price - ma200) / ma200 * 100
        ma200_clr = UP if diff200 >= 0 else DN
        stat_rows.append(("vs MA 200", f"{diff200:+.1f}%", f"MA200 at ${ma200:,.2f}", ma200_clr))
    if vol_now and vol_avg:
        vol_vs  = (vol_now / vol_avg - 1) * 100
        vol_clr = UP if vol_vs >= 20 else DN if vol_vs <= -20 else MUT
        stat_rows.append(("Volume", f"{vol_now/1e6:.1f}M", f"{vol_vs:+.0f}% vs 20D avg", vol_clr))

    html_rows = ""
    for i, (lbl, val, sub, clr) in enumerate(stat_rows):
        bg = f"background:{BG};" if i % 2 == 0 else ""
        sub_html = (
            f'<span style="color:{clr or MUT};font-size:0.7rem;margin-left:6px">{sub}</span>'
            if sub else ""
        )
        html_rows += (
            f'<div style="{bg}display:flex;align-items:center;gap:8px;'
            f'padding:5px 8px;border-radius:4px">'
            f'<span style="color:{MUT};font-size:0.82rem;white-space:nowrap">{lbl}</span>'
            f'<span style="font-size:0.85rem;font-weight:600;color:{clr or VAL};white-space:nowrap">'
            f'{val}{sub_html}</span>'
            f'</div>'
        )
    if html_rows:
        st.markdown(
            f'<div style="border:1px solid {SEP};border-radius:8px;overflow:hidden">'
            f'{html_rows}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Section 3: Fundamentals ───────────────────────────────────────────────
    render_fundamentals_panel(st.session_state.analyzer_fundamentals, price)
    st.markdown("---")

    # ── Section 4: Chart ──────────────────────────────────────────────────────
    valid_period = url_period if url_period in _PERIODS else _DEFAULT_PERIOD
    period_col, rsi_col = st.columns([6, 1])
    with period_col:
        selected_period = st.radio(
            "period_selector", list(_PERIODS), horizontal=True,
            index=list(_PERIODS).index(valid_period), label_visibility="collapsed",
        )
    show_rsi = rsi_col.checkbox("RSI", value=url_rsi)

    st.query_params["tic"]    = ticker
    st.query_params["period"] = selected_period
    st.query_params["rsi"]    = "1" if show_rsi else "0"

    cutoff     = pd.Timestamp.today() - pd.Timedelta(days=_PERIODS[selected_period])
    display_df = df[df.index >= cutoff].copy()
    if len(display_df) < 2:
        st.warning(f"Not enough data for the **{selected_period}** window. Try a longer period.")
        return

    fib = get_stock_fibonacci(display_df)
    _render_tradingview_chart(ticker, selected_period, show_rsi)
    st.markdown("---")

    # ── Section 5+6: Signals + BX + Key Levels ───────────────────────────────
    sig_col, bx_col, lvl_col = st.columns([3, 2, 2])
    with sig_col:
        render_signal_analysis(sig)
    with bx_col:
        render_buying_pressure(df)
    with lvl_col:
        _render_key_levels(latest, fib, price)

    st.markdown("---")

    # ── Section 7: Gap history ────────────────────────────────────────────────
    st.markdown("#### Gap History")
    last    = display_df.iloc[-1]
    gaps_df = get_stock_gaps(
        display_df, {"day_high": float(last["High"]), "day_low": float(last["Low"])}
    )
    if "RSI" in display_df.columns:
        gaps_df = gaps_df.copy()
        rsi_dedup         = display_df["RSI"][~display_df.index.duplicated(keep="last")]
        gaps_df["RSI"]    = rsi_dedup.reindex(gaps_df.index)
    render_gap_table(gaps_df, show_rsi=True)


# ── TradingView Advanced Chart widget ────────────────────────────────────────

_TV_RANGE = {"1D": "1D", "1W": "5D", "1M": "1M", "3M": "3M", "6M": "6M", "1Y": "12M", "2Y": "24M", "5Y": "60M"}
_TV_INTERVAL = {"1D": "5", "1W": "60", "1M": "D", "3M": "D", "6M": "D", "1Y": "D", "2Y": "W", "5Y": "W"}


def _render_tradingview_chart(ticker: str, period: str, show_rsi: bool) -> None:
    interval = _TV_INTERVAL.get(period, "D")
    range_val = _TV_RANGE.get(period, "12M")
    studies = '["RSI@tv-basicstudies"]' if show_rsi else "[]"

    html = f"""
    <div id="tv_wrap" style="height:520px;width:100%">
      <script src="https://s3.tradingview.com/tv.js"></script>
      <script>
        new TradingView.widget({{
          container_id: "tv_wrap",
          autosize:     true,
          symbol:       "{ticker}",
          interval:     "{interval}",
          range:        "{range_val}",
          timezone:     "America/New_York",
          theme:        "dark",
          style:        "1",
          locale:       "en",
          hide_top_toolbar:   false,
          hide_legend:        false,
          allow_symbol_change: false,
          studies: {studies}
        }});
      </script>
    </div>
    """
    components.html(html, height=540)


# ── Key levels panel (always-visible right column below chart) ────────────────

def _render_key_levels(latest, fib: dict, price: float) -> None:
    st.markdown("**Key Price Levels**")
    st.markdown(
        f'<div style="font-size:11px;color:{MUT};text-transform:uppercase;'
        f'letter-spacing:.05em;margin-bottom:4px">Moving Averages</div>',
        unsafe_allow_html=True,
    )
    for name, key in [("MA 5", "MA5"), ("MA 20", "MA20"), ("MA 50", "MA50"),
                      ("MA 100", "MA100"), ("MA 200", "MA200"), ("MA 200W", "MA200W")]:
        val = float(latest.get(key, 0) or 0)
        if val:
            diff = (price - val) / val * 100
            clr  = UP if diff >= 0 else DN
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:3px 0;border-bottom:1px solid {SEP}">'
                f'<span style="color:{MUT};font-size:0.85rem">{name}</span>'
                f'<span style="font-size:0.85rem">${val:,.2f}&nbsp;'
                f'<span style="color:{clr}">{diff:+.1f}%</span></span></div>',
                unsafe_allow_html=True,
            )
    st.markdown(
        f'<div style="font-size:11px;color:{MUT};text-transform:uppercase;'
        f'letter-spacing:.05em;margin:10px 0 4px">Fibonacci</div>',
        unsafe_allow_html=True,
    )
    for name, val in sorted(fib.items(), key=lambda x: x[1], reverse=True):
        above = price >= val
        clr   = UP if above else DN
        mark  = "▲" if above else "▼"
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:3px 0;border-bottom:1px solid {SEP}">'
            f'<span style="color:{MUT};font-size:0.85rem">Fib {name}</span>'
            f'<span style="font-size:0.85rem">${val:,.2f}&nbsp;'
            f'<span style="color:{clr}">{mark}</span></span></div>',
            unsafe_allow_html=True,
        )


# ── Session state init & entry point ──────────────────────────────────────────
for _k, _v in [
    ("search_results", []),
    ("ticker_val", "MSFT"),
    ("analyzer_df", None),
    ("analyzer_ticker", None),
    ("analyzer_company", None),
    ("analyzer_fundamentals", {}),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

render_analyzer_tab()
