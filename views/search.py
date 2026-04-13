import numpy as np
import pandas as pd
import streamlit as st

from charts import build_chart
from config import MA_PERIODS, PERIOD_OPTIONS, REVERSAL_PATTERNS
from data import fetch_ohlcv, get_company_name, search_companies
from indicators import (
    compute_daily_gaps,
    compute_fibonacci,
    compute_mas,
    compute_rsi,
    compute_weekly_ma200,
    detect_reversal_patterns,
)
from signals import overall_signal, signal_score


def render_search_tab() -> None:
    st.title("🔍 Search by Company")

    # ── Company name search ───────────────────────────────────────────────────
    col_q, col_btn = st.columns([5, 1])
    search_query = col_q.text_input(
        "company_search",
        placeholder="Search by company name, e.g. Microsoft, Apple, Tesla…",
        label_visibility="collapsed",
    )
    search_go = col_btn.button("Search", use_container_width=True)

    if search_go:
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
    elif search_query and not st.session_state.search_results and search_go:
        st.caption("No matches found — try a different name.")

    st.markdown("---")

    # ── Analysis controls ─────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 2, 1, 1, 1, 1, 1])
    ticker = c1.text_input(
        "Ticker Symbol", value=st.session_state.ticker_val, max_chars=10,
    ).upper().strip()

    period_label   = c2.selectbox("Historical Period", list(PERIOD_OPTIONS.keys()), index=2)
    period_days    = PERIOD_OPTIONS[period_label]
    show_volume    = c3.checkbox("Volume",    value=True)
    show_fibonacci = c4.checkbox("Fibonacci", value=True)
    show_patterns  = c5.checkbox("Patterns",  value=True)
    show_rsi       = c6.checkbox("RSI",       value=True)
    analyze_btn    = c7.button("Analyze", use_container_width=True, type="primary")

    # ── Analysis execution ────────────────────────────────────────────────────
    if not (analyze_btn or ticker):
        st.info("Enter a ticker symbol above and click **Analyze**.")
        return

    if not ticker:
        st.warning("Enter a ticker symbol above.")
        return

    with st.spinner(f"Fetching data for **{ticker}**…"):
        try:
            raw = fetch_ohlcv(ticker, period_days)
        except Exception as e:
            st.error(f"Failed to download data: {e}")
            return

    if raw.empty:
        st.error(f"No data found for **{ticker}**. Check the ticker symbol and try again.")
        return

    if len(raw) < 2:
        st.error(f"**{ticker}** returned insufficient price data. "
                 "It may be an invalid ticker, delisted, or too new.")
        return

    df = compute_mas(raw)
    df["MA200W"] = compute_weekly_ma200(df)
    df["RSI"]    = compute_rsi(df)
    df = detect_reversal_patterns(df)
    display_df = df.tail(period_days).copy()

    if len(display_df) < 2:
        st.error(f"Not enough data in the selected period for **{ticker}**. "
                 "Try a longer historical period.")
        return

    fib          = compute_fibonacci(display_df)
    latest       = display_df.iloc[-1]
    prev         = display_df.iloc[-2]
    score, why   = signal_score(latest, prev)
    label, color = overall_signal(score)
    company_name = get_company_name(ticker)

    # ── Header metrics ────────────────────────────────────────────────────────
    st.subheader(f"{company_name}  ({ticker})")

    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    price_now  = float(latest["Close"])
    price_prev = float(prev["Close"])
    change_pct = (price_now - price_prev) / price_prev * 100
    rsi_val    = latest.get("RSI", np.nan)

    k1.metric("Last Close", f"${price_now:.2f}", f"{change_pct:+.2f}%")
    k2.metric("MA 5",    f"${latest['MA5']:.2f}"    if not np.isnan(latest['MA5'])    else "N/A")
    k3.metric("MA 20",   f"${latest['MA20']:.2f}"   if not np.isnan(latest['MA20'])   else "N/A")
    k4.metric("MA 50",   f"${latest['MA50']:.2f}"   if not np.isnan(latest['MA50'])   else "N/A")
    k5.metric("MA 200",  f"${latest['MA200']:.2f}"  if not np.isnan(latest['MA200'])  else "N/A")
    k6.metric("MA 200W", f"${latest['MA200W']:.2f}" if not np.isnan(latest['MA200W']) else "N/A")
    if not np.isnan(rsi_val):
        rsi_label = "Overbought" if rsi_val >= 70 else "Oversold" if rsi_val <= 30 else "Neutral"
        k7.metric("RSI (14)", f"{rsi_val:.1f}", rsi_label)

    # ── Signal badge ──────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="
            background:{color}22;
            border:2px solid {color};
            border-radius:12px;
            padding:20px 28px;
            margin:16px 0;
        ">
            <span style="font-size:2rem;font-weight:800;color:{color};">{label}</span>
            <span style="font-size:1rem;color:#94A3B8;margin-left:16px;">
                Signal Score: {score:+d}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── RSI condition badge ───────────────────────────────────────────────────
    if not np.isnan(rsi_val):
        if rsi_val >= 70:
            rsi_color, rsi_text = "#EF4444", f"🔴 OVERBOUGHT  ·  RSI {rsi_val:.1f}"
        elif rsi_val <= 30:
            rsi_color, rsi_text = "#22C55E", f"🟢 OVERSOLD  ·  RSI {rsi_val:.1f}"
        else:
            rsi_color, rsi_text = "#64748B", f"⚪ RSI NEUTRAL  ·  RSI {rsi_val:.1f}"
        st.markdown(
            f"""<div style="
                background:{rsi_color}18;
                border:1px solid {rsi_color};
                border-radius:8px;
                padding:10px 20px;
                margin-bottom:12px;
                font-size:1rem;
                font-weight:600;
                color:{rsi_color};
            ">{rsi_text}</div>""",
            unsafe_allow_html=True,
        )

    with st.expander("Signal Reasoning", expanded=True):
        for r in why:
            icon = "✅" if any(w in r.lower() for w in ("bullish", "above", "golden", "oversold")) else "🔴"
            st.markdown(f"- {icon} {r}")

    # ── Chart + gaps side by side ─────────────────────────────────────────────
    chart_col, gap_col = st.columns([2, 1])

    with chart_col:
        fig = build_chart(display_df, fib, ticker, show_volume, show_fibonacci, show_patterns, show_rsi)
        st.plotly_chart(fig, use_container_width=True)

    with gap_col:
        _render_gap_table(display_df)

    # ── Pattern summary ───────────────────────────────────────────────────────
    if show_patterns:
        _render_pattern_summary(display_df)

    # ── Fibonacci table ───────────────────────────────────────────────────────
    if show_fibonacci:
        st.markdown("#### Fibonacci Retracement Levels (200-session range)")
        fib_df = pd.DataFrame([
            {
                "Level": k,
                "Price": f"${v:.2f}",
                "vs Last Close": f"{(v - price_now) / price_now * 100:+.2f}%",
                "Signal": "🟢 Support (Bullish)" if v < price_now else "🔴 Resistance (Bearish)",
            }
            for k, v in fib.items()
        ])
        st.dataframe(fib_df, use_container_width=True, hide_index=True)

    # ── MA summary table ──────────────────────────────────────────────────────
    _render_ma_summary(latest, price_now)


# ── Private helpers ───────────────────────────────────────────────────────────

def _render_gap_table(display_df: pd.DataFrame) -> None:
    st.markdown("#### Daily Gaps (Last 30 Days)")
    gaps_df   = compute_daily_gaps(display_df)
    gaps_data = gaps_df.tail(30)[["Open", "Prev Close", "Gap", "Gap %", "Gap Filled"]].reset_index()
    gaps_data.columns = ["Date", "Open", "Prev Close", "Gap $", "Gap %", "Filled"]
    gaps_data["Date"] = gaps_data["Date"].dt.strftime("%m-%d")
    gaps_data = gaps_data.sort_values("Date", ascending=False).reset_index(drop=True)

    display = gaps_data.drop("Filled", axis=1)

    def _highlight(row):
        unfilled = gaps_data.loc[row.name, "Filled"] is False
        style = "background-color: rgba(239,68,68,0.3); color:#EF4444; font-weight:bold"
        return [style] * len(row) if unfilled else [""] * len(row)

    st.dataframe(display.style.apply(_highlight, axis=1),
                 use_container_width=True, hide_index=True, height=600)


def _render_pattern_summary(display_df: pd.DataFrame) -> None:
    pattern_rows = []
    for col, label, bullish, *_ in REVERSAL_PATTERNS:
        count = int(display_df[col].sum()) if col in display_df.columns else 0
        if count:
            pattern_rows.append({
                "Pattern": label,
                "Count": count,
                "Bias": "Bullish" if bullish is True else "Bearish" if bullish is False else "Neutral",
            })
    if pattern_rows:
        st.markdown("#### Reversal Patterns Detected")
        st.dataframe(pd.DataFrame(pattern_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No reversal patterns were detected in the selected period.")


def _render_ma_summary(latest: pd.Series, price_now: float) -> None:
    st.markdown("#### Moving Average Summary")
    rows = []
    for p in MA_PERIODS:
        val = latest.get(f"MA{p}", np.nan)
        if np.isnan(val):
            continue
        diff_pct = (price_now - val) / val * 100
        rows.append({
            "MA Period":   f"MA {p} (daily)",
            "Value":       f"${val:.2f}",
            "Price vs MA": f"{diff_pct:+.2f}%",
            "Stance":      "Above" if price_now > val else "Below",
            "Signal":      "🟢 Bullish (Uptrend)" if price_now > val else "🔴 Bearish (Downtrend)",
        })
    val_w = latest.get("MA200W", np.nan)
    if not np.isnan(val_w):
        diff_pct_w = (price_now - val_w) / val_w * 100
        rows.append({
            "MA Period":   "MA 200 (weekly)",
            "Value":       f"${val_w:.2f}",
            "Price vs MA": f"{diff_pct_w:+.2f}%",
            "Stance":      "Above" if price_now > val_w else "Below",
            "Signal":      "🟢 Bullish (Long-term Uptrend)" if price_now > val_w else "🔴 Bearish (Long-term Downtrend)",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
