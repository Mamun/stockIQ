import pandas as pd
import streamlit as st

from indexiq.charts import build_chart

from indexiq.data import fetch_ohlcv, get_company_name, search_companies
from indexiq.indicators import (
    compute_daily_gaps,
    compute_fibonacci,
    compute_mas,
    compute_rsi,
    compute_weekly_ma200,
    detect_reversal_patterns,
)
from indexiq.signals import overall_signal, signal_score
from indexiq.affiliate import render_trade_buttons

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
                st.session_state.search_results = search_companies(search_query.strip())
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
                raw = fetch_ohlcv(ticker, _PERIODS["5Y"])
            except Exception as e:
                st.error(f"Failed to download data: {e}")
                return

        if raw.empty:
            st.error(f"No data found for **{ticker}**. Check the ticker symbol and try again.")
            return
        if len(raw) < 2:
            st.error(f"**{ticker}** returned insufficient price data.")
            return

        df = compute_mas(raw)
        df["MA200W"] = compute_weekly_ma200(df)
        df["RSI"]    = compute_rsi(df)
        df           = detect_reversal_patterns(df)

        st.session_state.analyzer_df      = df
        st.session_state.analyzer_ticker  = ticker
        st.session_state.analyzer_company = get_company_name(ticker)

        # Update URL to reflect the loaded ticker
        st.query_params["tic"] = ticker

    df           = st.session_state.analyzer_df
    company_name = st.session_state.analyzer_company
    latest       = df.iloc[-1]
    prev         = df.iloc[-2]
    score, _     = signal_score(latest, prev)
    label, color = overall_signal(score)

    # ── Overview card ─────────────────────────────────────────────────────────
    st.markdown(f"#### {company_name}  ({ticker})")
    _render_stock_summary(latest, prev, df, label, color, score)

    render_trade_buttons(ticker)

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

    fib = compute_fibonacci(display_df)
    fig = build_chart(display_df, fib, ticker,
                      show_vol=True, show_fib=False,
                      show_patterns=True, show_rsi=show_rsi)
    st.plotly_chart(fig, width="stretch")

    # ── Gap table ─────────────────────────────────────────────────────────────
    _render_gap_table(display_df)


# ── Private helpers ───────────────────────────────────────────────────────────

def _render_stock_summary(latest, prev, df, signal_label: str, signal_color: str, score: int) -> None:
    """Two-row overview card: price data + technicals (mirrors spy_dashboard style)."""
    price     = float(latest["Close"])
    prev_close = float(prev["Close"])
    chg       = price - prev_close
    chg_pct   = chg / prev_close * 100
    high      = float(latest.get("High", 0) or 0)
    low       = float(latest.get("Low",  0) or 0)
    vol       = float(latest.get("Volume", 0) or 0)

    last_252  = df.tail(252)
    w52_high  = float(last_252["High"].max())
    w52_low   = float(last_252["Low"].min())

    rsi_val  = float(latest.get("RSI", 0) or 0)
    ma5      = float(latest.get("MA5",    0) or 0)
    ma50     = float(latest.get("MA50",   0) or 0)
    ma200    = float(latest.get("MA200",  0) or 0)
    ma200w   = float(latest.get("MA200W", 0) or 0)

    if ma50 and ma200:
        cross_label = "🌟 Golden Cross" if ma50 > ma200 else "💀 Death Cross"
        cross_clr   = "#22C55E" if ma50 > ma200 else "#EF4444"
    else:
        cross_label = cross_clr = None

    up_clr  = "#22C55E"
    dn_clr  = "#EF4444"
    neu_clr = "#F59E0B"
    mut_clr = "#64748B"
    val_clr = "#F1F5F9"
    bg      = "#0F172A"
    sep     = "#1E293B"

    def cell(label, value, sub="", sub_clr=None):
        sub_html = (
            f'<div style="font-size:11px;color:{sub_clr or mut_clr};margin-top:2px;white-space:nowrap">{sub}</div>'
            if sub else '<div style="font-size:11px">&nbsp;</div>'
        )
        return (
            f'<div style="padding:10px 18px;border-right:1px solid {sep};'
            f'display:flex;flex-direction:column;justify-content:center">'
            f'<div style="font-size:11px;color:{mut_clr};text-transform:uppercase;'
            f'letter-spacing:.05em;white-space:nowrap">{label}</div>'
            f'<div style="font-size:17px;font-weight:700;color:{val_clr};white-space:nowrap">{value}</div>'
            f'{sub_html}'
            f'</div>'
        )

    def ma_cell(lbl, val):
        if not val:
            return ""
        diff = (price - val) / val * 100
        clr  = up_clr if diff >= 0 else dn_clr
        return cell(lbl, f"${val:,.2f}", f"{diff:+.2f}% vs price", clr)

    # Row 1 — price data
    chg_clr   = up_clr if chg >= 0 else dn_clr
    arrow     = "▲" if chg >= 0 else "▼"
    price_row = "".join([
        cell("Last Close", f"${price:,.2f}", f"{arrow} {abs(chg):.2f} ({chg_pct:+.2f}%)", chg_clr),
        cell("Prev Close", f"${prev_close:,.2f}"),
        cell("Day High",   f"${high:,.2f}"   if high   else "—"),
        cell("Day Low",    f"${low:,.2f}"    if low    else "—"),
        cell("52W High",   f"${w52_high:,.2f}" if w52_high else "—"),
        cell("52W Low",    f"${w52_low:,.2f}"  if w52_low  else "—"),
        cell("Volume",     f"{vol/1_000_000:.1f}M" if vol else "—"),
    ])

    # Row 2 — technicals
    sig_cell  = cell("Signal", signal_label, f"Score {score:+d}", signal_color)

    rsi_clr  = dn_clr if rsi_val >= 70 else up_clr if rsi_val <= 30 else neu_clr
    rsi_sub  = "Overbought" if rsi_val >= 70 else "Oversold" if rsi_val <= 30 else "Neutral"
    rsi_cell = cell("RSI (14)", f"{rsi_val:.1f}", rsi_sub, rsi_clr) if rsi_val else ""

    cross_cell = cell("MA Trend", cross_label, "MA50 vs MA200", cross_clr) if cross_label else ""

    tech_row = "".join([
        sig_cell,
        rsi_cell,
        cross_cell,
        ma_cell("MA 5",    ma5),
        ma_cell("MA 50",   ma50),
        ma_cell("MA 200",  ma200),
        ma_cell("MA 200W", ma200w),
    ])

    row_style = f'display:flex;flex-wrap:wrap;background:{bg};border-bottom:1px solid {sep}'
    st.markdown(
        f'<div style="background:{bg};border:1px solid {sep};border-radius:8px;'
        f'overflow:hidden;margin-bottom:8px">'
        f'<div style="{row_style}">{price_row}</div>'
        f'<div style="{row_style};border-bottom:none">{tech_row}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_gap_table(display_df: pd.DataFrame) -> None:
    st.markdown("#### Daily Gaps (Last 30 Days)")
    gaps_df = compute_daily_gaps(display_df)

    # Attach RSI from display_df — deduplicate index first to prevent row expansion
    if "RSI" in display_df.columns:
        gaps_df = gaps_df.copy()
        rsi_dedup = display_df["RSI"][~display_df.index.duplicated(keep="last")]
        gaps_df["RSI"] = rsi_dedup.reindex(gaps_df.index)

    cols = ["Open", "Prev Close", "Gap", "Gap %", "Gap Filled", "Gap Confirmed"]
    if "RSI" in gaps_df.columns:
        cols.append("RSI")

    gaps_data = gaps_df.tail(30)[cols].reset_index()
    base_cols  = ["Date", "Open", "Prev Close", "Gap $", "Gap %", "Filled", "Gap Confirmed"]
    if "RSI" in gaps_df.columns:
        base_cols.append("RSI")
    gaps_data.columns = base_cols

    gaps_data["Date"] = gaps_data["Date"].dt.strftime("%m-%d")
    gaps_data = gaps_data.sort_values("Date", ascending=False).reset_index(drop=True)

    gaps_data["Status"] = gaps_data.apply(
        lambda r: "—" if r["Gap $"] == 0
        else ("✅ Filled" if r["Filled"]
        else ("⏳ Pending" if not r.get("Gap Confirmed", True)
        else "❌ Open")),
        axis=1,
    )

    def _rsi_zone(rsi):
        if pd.isna(rsi) or rsi == 0:
            return "—"
        if rsi >= 70:
            return "Overbought"
        if rsi <= 30:
            return "Oversold"
        return "Neutral"

    has_rsi = "RSI" in gaps_data.columns
    if has_rsi:
        gaps_data["RSI Zone"] = gaps_data["RSI"].apply(_rsi_zone)

    display_cols = ["Date", "Open", "Prev Close", "Gap $", "Gap %", "Status"]
    if has_rsi:
        display_cols += ["RSI", "RSI Zone"]
    display = gaps_data[display_cols]

    def _highlight(row):
        gap    = gaps_data.loc[row.name, "Gap $"]
        filled = gaps_data.loc[row.name, "Filled"]
        base   = [""] * len(row)
        if gap == 0 or bool(filled):
            return base
        style = (
            "background-color: rgba(34,197,94,0.20); color:#22C55E; font-weight:600"
            if gap > 0
            else "background-color: rgba(239,68,68,0.25); color:#EF4444; font-weight:600"
        )
        return [style] * len(row)

    def _color_rsi_zone(val):
        if val == "Overbought":
            return "color:#EF4444; font-weight:700"
        if val == "Oversold":
            return "color:#22C55E; font-weight:700"
        if val == "Neutral":
            return "color:#F59E0B"
        return ""

    def _color_rsi(val):
        if pd.isna(val) or val == 0:
            return ""
        if val >= 70:
            return "color:#EF4444; font-weight:700"
        if val <= 30:
            return "color:#22C55E; font-weight:700"
        return "color:#F59E0B"

    fmt = {"Open": "${:.2f}", "Prev Close": "${:.2f}", "Gap $": "${:.2f}", "Gap %": "{:+.2f}%"}
    if has_rsi:
        fmt["RSI"] = "{:.1f}"

    styled = display.style.apply(_highlight, axis=1).format(fmt, na_rep="—")
    if has_rsi:
        styled = styled.map(_color_rsi_zone, subset=["RSI Zone"]).map(_color_rsi, subset=["RSI"])

    st.dataframe(styled, width="stretch", hide_index=True, height=600)


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
