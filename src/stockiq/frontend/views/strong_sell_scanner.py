import streamlit as st

from stockiq.backend.services.scanners import get_strong_sell_scan
from stockiq.frontend.theme import DN
from stockiq.frontend.views.components.scanner_charts import (
    analyst_downside_bar,
    analyst_sector_bar,
    analyst_sell_scatter,
)


def render_strong_sell_tab() -> None:
    st.title("🔻 Strong Sell Radar")
    st.markdown(
        "Aggregates **Wall Street analyst consensus** to surface S&P 500 stocks "
        "rated **Sell or Strong Sell** by the most analysts, with the largest "
        "downside to their mean price target. "
        "RSI check flags stocks that are already overbought — higher risk of a drop."
    )

    # ── URL params ────────────────────────────────────────────────────────────
    params    = st.query_params
    auto_scan = params.get("scan", "0") == "1"
    try:
        _url_downside = max(0, min(40, int(params.get("downside", 0))))
    except (ValueError, TypeError):
        _url_downside = 0
    try:
        _url_analysts = max(1, min(20, int(params.get("analysts", 1))))
    except (ValueError, TypeError):
        _url_analysts = 1
    try:
        _r = float(params.get("rating", 2.5))
        _url_rating = _r if _r in (2.5, 3.0, 3.5, 4.0, 4.5) else 2.5
    except (ValueError, TypeError):
        _url_rating = 2.5
    try:
        _url_top = max(5, min(30, int(params.get("top", 30))))
    except (ValueError, TypeError):
        _url_top = 30

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
    min_downside = c1.slider(
        "Min Downside %",
        min_value=0, max_value=40, value=_url_downside, step=5,
        help="Analyst mean target must be at least this % below current price",
    )
    min_analysts = c2.slider(
        "Min # of Analysts",
        min_value=1, max_value=20, value=_url_analysts, step=1,
        help="Require at least this many analysts to avoid thin coverage",
    )
    min_rating = c3.select_slider(
        "Min Rating (least bullish)",
        options=[2.5, 3.0, 3.5, 4.0, 4.5],
        value=_url_rating,
        format_func=lambda v: {
            2.5: "Hold & above (widest)",
            3.0: "Cautious Hold & above",
            3.5: "Moderate Sell & above",
            4.0: "Sell & above",
            4.5: "Strong Sell only",
        }[v],
    )
    top_n = c4.slider(
        "Max results",
        min_value=5, max_value=30, value=_url_top, step=5,
    )
    scan_btn = c5.button("🔍 Scan", width="stretch", type="primary")

    st.markdown("---")

    if not scan_btn and not auto_scan:
        _render_legend()
        return

    # Sync current filter state into URL so the page is shareable
    st.query_params["downside"] = str(min_downside)
    st.query_params["analysts"] = str(min_analysts)
    st.query_params["rating"]   = str(min_rating)
    st.query_params["top"]      = str(top_n)
    st.query_params["scan"]     = "1"

    with st.spinner("🔻 Fetching analyst consensus data…"):
        df = get_strong_sell_scan(
            min_downside=float(min_downside),
            min_analysts=int(min_analysts),
            min_rating=float(min_rating),
            top_n=top_n,
        )

    if df.empty:
        with st.spinner("No exact matches — showing least-bullish stocks available…"):
            df = get_strong_sell_scan(
                min_downside=0.0,
                min_analysts=1,
                min_rating=2.5,
                top_n=top_n,
            )
        if df.empty:
            st.warning(
                "No analyst data available right now. "
                "Yahoo Finance may be rate-limiting — try again in a few minutes."
            )
            return
        st.info(
            f"No stocks matched rating ≥ {min_rating}, downside ≥ {min_downside}%, "
            f"analysts ≥ {min_analysts}. "
            "Showing the **least bullish** S&P 500 stocks instead — tighten filters to narrow down.",
            icon="ℹ️",
        )

    st.success(f"✅ Found **{len(df)}** analyst-flagged candidates")

    # ── Summary metrics ───────────────────────────────────────────────────────
    strong_sells = int((df["Rating"] >= 4.5).sum())
    overbought   = int((df["RSI"].dropna() >= 70).sum())
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Candidates",          len(df))
    m2.metric("🔴 Strong Sell",      strong_sells)
    m3.metric("Avg Downside %",      f"{df['Downside %'].mean():.1f}%")
    m4.metric("Avg Analyst Rating",  f"{df['Rating'].mean():.2f}")
    m5.metric("Avg # Analysts",      f"{df['Analysts'].mean():.0f}")
    m6.metric("Overbought (RSI≥70)", overbought)

    st.markdown("---")

    # ── Score formula explainer ───────────────────────────────────────────────
    with st.expander("📐 How the Strong Sell Score is calculated", expanded=False):
        st.markdown("""
        | Component | Formula | Max |
        |---|---|---|
        | Analyst Rating | `(rating − 3.5) × 26.7` — higher rating scores higher | 40 |
        | Price Target Downside | `min(|downside %|, 50) × 0.5` | 25 |
        | Analyst Coverage | `min(# analysts, 20) × 1.5` — more analysts = more reliable | 30 |
        | RSI Overbought Bonus | +5 if RSI > 60 (stock is elevated — more room to fall) | 5 |

        **Rating scale:** 1.0 = Strong Buy · 2.0 = Buy · 3.0 = Hold · 4.0 = Sell · 5.0 = Strong Sell

        **Total max ≈ 100.** Score > 60 = high-conviction bearish setup. Score > 75 = exceptional.
        """)

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Candidates — sorted by Strong Sell Score ↓")
    display_cols = [
        "Ticker", "Company", "Sector", "Price", "Target",
        "Target Low", "Target High", "Downside %",
        "Consensus", "Rating", "Analysts", "RSI", "SS Score",
    ]
    st.dataframe(
        _style_table(df[display_cols]),
        width="stretch", hide_index=True,
        height=(len(df) + 1) * 35 + 4,
    )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Price Target Downside %")
        st.caption("Mean analyst price target vs current price")
        st.plotly_chart(analyst_downside_bar(df), width="stretch")

    with col2:
        st.markdown("#### Rating vs Downside — bubble = analyst count")
        st.plotly_chart(analyst_sell_scatter(df), width="stretch")

    # ── Sector breakdown ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Sector Distribution")
    st.plotly_chart(
        analyst_sector_bar(df, "SS Score", "Downside %", "downside", DN, "Avg Strong Sell Score"),
        width="stretch",
    )


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row(row):
        styles = [""] * len(row)
        cols   = list(df.columns)

        cons_i = cols.index("Consensus")
        if "Strong Sell" in str(row["Consensus"]):
            styles[cons_i] = f"color:{DN};font-weight:700"
        elif "Sell" in str(row["Consensus"]):
            styles[cons_i] = "color:#F97316;font-weight:600"
        else:
            styles[cons_i] = "color:#FACC15;font-weight:600"

        dn_i = cols.index("Downside %")
        if row["Downside %"] <= -20:
            styles[dn_i] = f"color:{DN};font-weight:700"
        elif row["Downside %"] <= -10:
            styles[dn_i] = "color:#F97316;font-weight:600"

        if "RSI" in cols and row["RSI"] is not None:
            rsi_i = cols.index("RSI")
            if row["RSI"] >= 70:
                styles[rsi_i] = f"color:{DN};font-weight:700"
            elif row["RSI"] >= 60:
                styles[rsi_i] = "color:#F97316;font-weight:600"

        ss_i = cols.index("SS Score")
        if row["SS Score"] >= 75:
            styles[ss_i] = f"color:{DN};font-weight:700"
        elif row["SS Score"] >= 60:
            styles[ss_i] = "color:#F97316;font-weight:600"

        return styles

    fmt = {
        "Price":       "${:.2f}",
        "Target":      "${:.2f}",
        "Target High": "${:.2f}",
        "Target Low":  "${:.2f}",
        "Downside %":  "{:.1f}%",
        "Rating":      "{:.2f}",
        "SS Score":    "{:.1f}",
    }
    if "RSI" in df.columns:
        fmt["RSI"] = "{:.1f}"

    return df.style.apply(_row, axis=1).format(fmt, na_rep="—")


def _render_legend() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**How analyst sell ratings work**\n\n"
            "When analysts issue Sell or Strong Sell ratings, they believe the stock "
            "will underperform — often because of deteriorating fundamentals, "
            "stretched valuation, or sector headwinds.\n\n"
            "- 🔴 **Strong Sell** (≥ 4.5) — overwhelming bearish conviction\n"
            "- 🟠 **Sell** (≥ 4.0) — majority bearish\n"
            "- 🟡 **Moderate Sell** (≥ 3.5) — cautiously bearish\n"
            "- ⚪ **Hold** (≥ 3.0) — neutral to cautious\n\n"
            "**Note:** True Sell ratings are rare in the S&P 500 — analysts skew bullish. "
            "Hold-rated stocks trading above analyst targets are equally useful bearish signals."
        )
    with col2:
        st.markdown("**What to look for:**")
        st.markdown("""
        | Signal | Meaning |
        |---|---|
        | Rating ≥ 4.5 | 🔴 Analysts overwhelmingly bearish |
        | Rating ≥ 3.5 | 🟡 Cautious — below average conviction |
        | Rating ≥ 2.5 | ⚪ Hold — neutral, use as widest filter |
        | Downside ≥ 10% | 🔴 Target well below current price |
        | Analysts ≥ 10 | High-confidence bearish coverage |
        | RSI ≥ 70 | Overbought — elevated short-term risk |
        | SS Score ≥ 60 | Strong bearish setup |
        """)
    st.markdown("Adjust filters and click **Scan** to find candidates.")


render_strong_sell_tab()
