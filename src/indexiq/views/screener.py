import plotly.graph_objects as go
import streamlit as st

from indexiq.config import SCREENER_TICKER_COUNT, _SPX_UNIVERSE
from indexiq.premium import is_premium, render_upgrade_prompt, FREE_TICKER_COUNT, PREMIUM_TICKER_COUNT
from indexiq.data import fetch_spx_recommendations

_SIGNAL_TIERS = [
    "🟢 Strong Buy",
    "🟢 Buy",
    "🟡 Accumulate",
    "🟠 Caution",
    "🔴 Sell",
]

_TIER_COLORS = {
    "🟢 Strong Buy": "#22C55E",
    "🟢 Buy":        "#86EFAC",
    "🟡 Accumulate": "#FACC15",
    "🟠 Caution":    "#F97316",
    "🔴 Sell":       "#EF4444",
}


def render_screener_tab() -> None:
    st.title("📊 Weekly/Monthly Screener")
    st.markdown(
        "Scans the S&P 500 universe for **candle momentum** across weekly and monthly timeframes. "
        "Adds RSI, price returns, volume trend, and relative strength vs the index "
        "so you can spot real momentum — not just green dots."
    )

    ticker_count = PREMIUM_TICKER_COUNT if is_premium() else FREE_TICKER_COUNT
    tier_label   = "✨ Premium" if is_premium() else f"Free · [upgrade for {PREMIUM_TICKER_COUNT} tickers](/premium)"
    st.caption(f"Universe: top **{ticker_count}** S&P 500 stocks · {tier_label} · Cached 1 hour")
    st.markdown("---")

    if not st.button("🔄 Run Screener", width="stretch", type="primary"):
        _render_legend()
        return

    with st.spinner(f"📊 Analyzing {ticker_count} stocks…"):
        df = fetch_spx_recommendations()

    if df.empty:
        st.warning("Could not fetch data. Please try again.")
        return

    st.success(f"✅ Scanned **{len(df)}** stocks")

    # ── Summary metrics ───────────────────────────────────────────────────────
    counts = {t: int((df["Signal"] == t).sum()) for t in _SIGNAL_TIERS}
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total",          len(df))
    m2.metric("🟢 Strong Buy",  counts["🟢 Strong Buy"])
    m3.metric("🟢 Buy",         counts["🟢 Buy"])
    m4.metric("🟡 Accumulate",  counts["🟡 Accumulate"])
    m5.metric("🟠 Caution",     counts["🟠 Caution"])
    m6.metric("🔴 Sell",        counts["🔴 Sell"])

    st.markdown("---")

    # ── Sector tabs ───────────────────────────────────────────────────────────
    sectors   = sorted(df[df["Sector"] != "—"]["Sector"].dropna().unique().tolist())
    tab_names = ["All"] + sectors
    tabs      = st.tabs(tab_names)

    for tab, sector in zip(tabs, tab_names):
        with tab:
            view = df if sector == "All" else df[df["Sector"] == sector]
            _render_signal_sections(view)

    # ── Sector momentum chart ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Sector Momentum Overview")
    st.caption("Stacked signal distribution per sector — more green = stronger sector momentum")
    st.plotly_chart(_sector_chart(df), width="stretch")


# ── Private helpers ────────────────────────────────────────────────────────────

def _render_signal_sections(df) -> None:
    display_cols = [
        "Ticker", "Company", "Sector", "Price",
        "1W %", "1M %", "3M %", "vs SPX",
        "Vol", "RSI",
        "🔷 Weeks", "W Score",
        "🔶 Months", "M Score",
    ]
    for signal in _SIGNAL_TIERS:
        tier_df = df[df["Signal"] == signal].copy()
        if tier_df.empty:
            continue
        st.markdown(f"### {signal} &nbsp; <span style='font-size:14px;color:#94A3B8'>({len(tier_df)} stocks)</span>",
                    unsafe_allow_html=True)
        cols = [c for c in display_cols if c in tier_df.columns]
        st.dataframe(
            _style_table(tier_df[cols]),
            width="stretch", hide_index=True,
        )


def _style_table(df):
    pct_cols = {"1W %", "1M %", "3M %", "vs SPX"}

    def _row(row):
        styles = [""] * len(row)
        cols   = list(df.columns)

        for col in pct_cols:
            if col not in cols:
                continue
            i   = cols.index(col)
            val = row[col]
            if val is None or (hasattr(val, "__class__") and val != val):
                continue
            if val > 0:
                styles[i] = "color:#22C55E;font-weight:600"
            elif val < 0:
                styles[i] = "color:#EF4444;font-weight:600"

        if "RSI" in cols:
            i   = cols.index("RSI")
            rsi = row["RSI"]
            if rsi >= 70:
                styles[i] = "color:#EF4444;font-weight:700"
            elif rsi <= 30:
                styles[i] = "color:#22C55E;font-weight:700"

        return styles

    fmt: dict = {"Price": "${:.2f}"}
    for col in pct_cols:
        if col in df.columns:
            fmt[col] = "{:+.1f}%"
    if "RSI" in df.columns:
        fmt["RSI"] = "{:.1f}"

    return df.style.apply(_row, axis=1).format(fmt, na_rep="—")


def _sector_chart(df) -> go.Figure:
    sector_signal = (
        df[df["Sector"] != "—"]
        .groupby(["Sector", "Signal"])
        .size()
        .reset_index(name="Count")
    )

    fig = go.Figure()
    for signal in reversed(_SIGNAL_TIERS):   # reversed so Strong Buy is on top
        sub = sector_signal[sector_signal["Signal"] == signal]
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            name=signal,
            x=sub["Sector"],
            y=sub["Count"],
            marker_color=_TIER_COLORS[signal],
            hovertemplate=f"<b>%{{x}}</b><br>{signal}: %{{y}}<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        template="plotly_dark",
        height=360,
        margin=dict(l=20, r=20, t=20, b=80),
        legend=dict(orientation="h", y=1.08, x=0),
        xaxis=dict(title="", tickangle=-30),
        yaxis=dict(title="# Stocks"),
    )
    return fig


def _render_legend() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**How the screener works**\n\n"
            "1. Downloads 9 months of daily price data for each stock\n"
            "2. Resamples to **weekly** and **monthly** candles\n"
            "3. Counts green candles (Close > Open) in the last 4 periods\n"
            "4. Assigns a 5-tier signal based on candle momentum\n"
            "5. Adds RSI, price returns, volume trend, and vs-SPX performance\n\n"
            "Click **Run Screener** to start."
        )
    with col2:
        st.markdown("**Signal tiers:**")
        st.markdown("""
        | Signal | Criteria |
        |---|---|
        | 🟢 Strong Buy | 4/4 weeks green **and** 4/4 months green |
        | 🟢 Buy | 4/4 weeks green **and** 3/4 months green |
        | 🟡 Accumulate | 3/4 weeks **and** ≥3/4 months green |
        | 🟠 Caution | 2/4 weeks green |
        | 🔴 Sell | ≤1/4 weeks green |

        **Columns:**
        `vs SPX` = stock 1M return minus S&P 500 1M return (positive = outperforming)
        `Vol` 🔼 = recent volume above 20-day avg · 🔽 = below
        """)


render_screener_tab()

