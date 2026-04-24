import pandas as pd
import streamlit as st

from stockiq.backend.services.analyzer_service import (
    get_buying_pressure,
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

_PERIODS = {
    "1M":  30,
    "3M":  90,
    "6M":  180,
    "1Y":  365,
    "2Y":  730,
    "5Y":  1825,
}
_DEFAULT_PERIOD = "1Y"

_UP  = "#22C55E"
_DN  = "#EF4444"
_NEU = "#F59E0B"
_MUT = "#64748B"
_VAL = "#F1F5F9"
_BG  = "#0F172A"
_SEP = "#1E293B"


def _stat_card(label: str, value: str, sub: str = "", sub_color: str | None = None) -> str:
    sub_html = (
        f'<div style="font-size:11px;color:{sub_color or _MUT};margin-top:3px">{sub}</div>'
        if sub else ""
    )
    return (
        f'<div style="background:{_BG};border:1px solid {_SEP};border-radius:8px;'
        f'padding:14px 16px">'
        f'<div style="font-size:11px;color:{_MUT};text-transform:uppercase;'
        f'letter-spacing:.05em;margin-bottom:4px">{label}</div>'
        f'<div style="font-size:19px;font-weight:700;color:{_VAL}">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def _reason_icon(text: str) -> str:
    """Prefix a signal reason with a coloured bullet based on its sentiment."""
    lc = text.lower()
    if any(w in lc for w in ("above", "golden cross", "positive", "uptrend", "oversold")):
        return f"🟢 {text}"
    if any(w in lc for w in ("below", "death cross", "negative", "downtrend", "overbought")):
        return f"🔴 {text}"
    return f"⚪ {text}"


def _render_bx_panel(bx: dict, label: str) -> None:
    strength = bx["strength"]
    if bx["signal"] and strength == 3:
        badge_bg, badge_txt = "#16A34A", "BX TRIGGERED ✓✓✓"
    elif bx["signal"]:
        badge_bg, badge_txt = "#22C55E", "BX TRIGGERED ✓✓"
    else:
        badge_bg, badge_txt = "#475569", "WAITING FOR BX"

    bar_label = bx.get("bar_label", "")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
        f'<span style="font-weight:600">{label}</span>'
        f'<span style="background:{badge_bg};color:#fff;padding:2px 10px;'
        f'border-radius:4px;font-size:0.78rem">{badge_txt}</span>'
        f'<span style="color:{_MUT};font-size:0.72rem">{bar_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    for cond in bx["conditions_met"]:
        st.markdown(f"&nbsp;&nbsp;✅ {cond}")
    for cond in bx["conditions_missing"]:
        st.markdown(f"&nbsp;&nbsp;❌ {cond}")


def render_analyzer_tab() -> None:
    st.title("🔬 Stock Analyzer")

    # ── URL params ────────────────────────────────────────────────────────────
    params     = st.query_params
    url_ticker = params.get("tic", "").upper().strip()
    url_period = params.get("period", _DEFAULT_PERIOD)
    url_rsi    = params.get("rsi", "1") != "0"

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

    # ── Ticker input + Analyze ────────────────────────────────────────────────
    col_ticker, col_btn2 = st.columns([5, 1], vertical_alignment="bottom")
    ticker = col_ticker.text_input(
        "Ticker Symbol", value=st.session_state.ticker_val, max_chars=10,
    ).upper().strip()
    analyze_btn = col_btn2.button("Analyze", width="stretch", type="primary")

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
                "Use the Search box above to find the correct symbol, "
                "or check that it's a valid ticker (e.g. AAPL, MSFT, GOOGL)."
            )
            return
        if len(raw) < 2:
            st.error(f"**{ticker}** returned insufficient price data.")
            return

        st.session_state.analyzer_df      = raw
        st.session_state.analyzer_ticker  = ticker
        st.session_state.analyzer_company = get_company_display_name(ticker)
        st.query_params["tic"] = ticker

    df           = st.session_state.analyzer_df
    company_name = st.session_state.analyzer_company
    sig          = get_stock_signal(df)
    latest, prev = sig["latest"], sig["prev"]
    score, signal_label, signal_color = sig["score"], sig["label"], sig["color"]

    # ── Pre-compute values used across sections ───────────────────────────────
    price      = float(latest["Close"])
    prev_close = float(prev["Close"])
    chg        = price - prev_close
    chg_pct    = chg / prev_close * 100
    chg_clr    = _UP if chg >= 0 else _DN
    arrow      = "▲" if chg >= 0 else "▼"

    last_252 = df.tail(252)
    w52_high = float(last_252["High"].max())
    w52_low  = float(last_252["Low"].min())

    rsi_val  = float(latest.get("RSI",   0) or 0)
    ma5      = float(latest.get("MA5",   0) or 0)
    ma20     = float(latest.get("MA20",  0) or 0)
    ma50     = float(latest.get("MA50",  0) or 0)
    ma100    = float(latest.get("MA100", 0) or 0)
    ma200    = float(latest.get("MA200", 0) or 0)
    ma200w   = float(latest.get("MA200W",0) or 0)
    vol_now  = float(latest.get("Volume",0) or 0)
    vol_avg  = (
        float(df["Volume"].rolling(20).mean().iloc[-1])
        if "Volume" in df.columns else 0.0
    )

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Header: company name · price · signal badge
    # ═════════════════════════════════════════════════════════════════════════
    h_name, h_price, h_signal = st.columns([3, 3, 1])

    with h_name:
        st.markdown(
            f'<div style="padding-top:6px">'
            f'<div style="font-size:1.4rem;font-weight:700;color:{_VAL}">{company_name}</div>'
            f'<div style="font-size:0.9rem;color:{_MUT};margin-top:2px">{ticker}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with h_price:
        st.markdown(
            f'<div style="padding-top:4px">'
            f'<div style="font-size:2rem;font-weight:800;color:{_VAL}">${price:,.2f}</div>'
            f'<div style="font-size:0.95rem;color:{chg_clr};margin-top:2px">'
            f'{arrow} {abs(chg):.2f} &nbsp;({chg_pct:+.2f}%)'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with h_signal:
        st.markdown(
            f'<div style="background:{signal_color};border-radius:8px;padding:12px 8px;'
            f'text-align:center">'
            f'<div style="font-size:0.85rem;font-weight:800;color:#fff;'
            f'letter-spacing:.03em">{signal_label}</div>'
            f'<div style="font-size:0.78rem;color:rgba(255,255,255,.8);margin-top:2px">'
            f'Score {score:+d}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Quick stats: 52W range · RSI · vs MA200 · volume
    # ═════════════════════════════════════════════════════════════════════════
    qs1, qs2, qs3, qs4 = st.columns(4)

    with qs1:
        if w52_high > w52_low:
            pos_pct  = (price - w52_low) / (w52_high - w52_low) * 100
            range_clr = _UP if pos_pct >= 50 else _DN
            st.markdown(
                _stat_card("52W Range", f"{pos_pct:.1f}% of range",
                           f"${w52_low:,.2f} — ${w52_high:,.2f}", range_clr),
                unsafe_allow_html=True,
            )

    with qs2:
        if rsi_val:
            rsi_clr = _DN if rsi_val >= 70 else _UP if rsi_val <= 30 else _NEU
            rsi_lbl = "Overbought" if rsi_val >= 70 else "Oversold" if rsi_val <= 30 else "Neutral"
            st.markdown(
                _stat_card("RSI (14)", f"{rsi_val:.1f}", rsi_lbl, rsi_clr),
                unsafe_allow_html=True,
            )

    with qs3:
        if ma200:
            diff200    = (price - ma200) / ma200 * 100
            ma200_clr  = _UP if diff200 >= 0 else _DN
            st.markdown(
                _stat_card("vs MA 200", f"{diff200:+.1f}%",
                           f"MA200 at ${ma200:,.2f}", ma200_clr),
                unsafe_allow_html=True,
            )

    with qs4:
        if vol_now and vol_avg:
            vol_vs   = (vol_now / vol_avg - 1) * 100
            vol_clr  = _UP if vol_vs >= 20 else _DN if vol_vs <= -20 else _MUT
            st.markdown(
                _stat_card("Volume", f"{vol_now/1e6:.1f}M",
                           f"{vol_vs:+.0f}% vs 20D avg", vol_clr),
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 3 — Chart
    # ═════════════════════════════════════════════════════════════════════════
    valid_period = url_period if url_period in _PERIODS else _DEFAULT_PERIOD

    period_col, rsi_col = st.columns([6, 1])
    with period_col:
        selected_period = st.radio(
            "period_selector", list(_PERIODS), horizontal=True,
            index=list(_PERIODS).index(valid_period),
            label_visibility="collapsed",
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
    golden, death = get_stock_crosses(display_df)
    fig = build_chart(display_df, fib, ticker,
                      show_vol=True, show_fib=False,
                      show_patterns=True, show_rsi=show_rsi,
                      golden_dates=golden, death_dates=death)
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 4 — Signal analysis (left) + BX signal (right)
    # ═════════════════════════════════════════════════════════════════════════
    sig_col, bx_col = st.columns([3, 2])

    with sig_col:
        st.markdown("**Signal Analysis**")
        score_bar_pct = min(100, max(0, (score + 8) / 16 * 100))
        score_clr     = signal_color
        st.markdown(
            f'<div style="background:{_SEP};border-radius:6px;height:6px;margin-bottom:10px">'
            f'<div style="width:{score_bar_pct:.0f}%;height:100%;background:{score_clr};'
            f'border-radius:6px"></div></div>',
            unsafe_allow_html=True,
        )
        for reason in sig["reasons"]:
            st.markdown(_reason_icon(reason))

    with bx_col:
        st.markdown("**Buying Pressure (BX)**")
        st.caption("2/3 conditions = signal · 3/3 = strong · based on completed bars only")

        bx_monthly = get_buying_pressure(df, "monthly")
        bx_weekly  = get_buying_pressure(df, "weekly")

        _render_bx_panel(bx_monthly, "Monthly")
        st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
        _render_bx_panel(bx_weekly, "Weekly")

    st.markdown("---")

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 5 — Key price levels (collapsible)
    # ═════════════════════════════════════════════════════════════════════════
    with st.expander("Key Price Levels", expanded=False):
        ma_col, fib_col = st.columns(2)

        with ma_col:
            st.markdown("**Moving Averages**")
            for name, val in [
                ("MA 5",    ma5),
                ("MA 20",   ma20),
                ("MA 50",   ma50),
                ("MA 100",  ma100),
                ("MA 200",  ma200),
                ("MA 200W", ma200w),
            ]:
                if val:
                    diff = (price - val) / val * 100
                    clr  = _UP if diff >= 0 else _DN
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'padding:4px 0;border-bottom:1px solid {_SEP}">'
                        f'<span style="color:{_MUT}">{name}</span>'
                        f'<span>${val:,.2f} &nbsp;'
                        f'<span style="color:{clr};font-size:0.85rem">{diff:+.1f}%</span>'
                        f'</span></div>',
                        unsafe_allow_html=True,
                    )

        with fib_col:
            st.markdown("**Fibonacci Levels**")
            for name, val in sorted(fib.items(), key=lambda x: x[1], reverse=True):
                above = price >= val
                clr   = _MUT
                marker = "▲ above" if above else "▼ below"
                marker_clr = _UP if above else _DN
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:4px 0;border-bottom:1px solid {_SEP}">'
                    f'<span style="color:{_MUT}">Fib {name}</span>'
                    f'<span>${val:,.2f} &nbsp;'
                    f'<span style="color:{marker_clr};font-size:0.85rem">{marker}</span>'
                    f'</span></div>',
                    unsafe_allow_html=True,
                )

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 6 — Gap history
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown("#### Gap History")

    last      = display_df.iloc[-1]
    gaps_df   = get_stock_gaps(
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
