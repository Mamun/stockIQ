import plotly.graph_objects as go
import streamlit as st

from data import fetch_strong_buy_candidates


def render_strong_buy_tab() -> None:
    st.title("💎 Strong Buy Radar")
    st.markdown(
        "Aggregates **Wall Street analyst consensus** across the S&P 500 universe. "
        "Stocks rated **Buy or Strong Buy** by the most analysts, with the highest "
        "price-target upside, rise to the top. "
        "RSI entry check ensures you're not chasing an already-overbought name."
    )

    # ── URL params ────────────────────────────────────────────────────────────
    params    = st.query_params
    auto_scan = params.get("scan", "0") == "1"
    try:    _url_upside   = max(0,   min(40, int(params.get("upside",   5))))
    except: _url_upside   = 5
    try:    _url_analysts = max(1,   min(20, int(params.get("analysts", 5))))
    except: _url_analysts = 5
    try:
        _r = float(params.get("rating", 2.5))
        _url_rating = _r if _r in (1.5, 2.0, 2.5) else 2.5
    except: _url_rating = 2.5
    try:    _url_top      = max(5,   min(30, int(params.get("top",      20))))
    except: _url_top      = 20

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
    min_upside = c1.slider(
        "Min Upside %",
        min_value=0, max_value=40, value=_url_upside, step=5,
        help="Analyst mean price target must be at least this % above current price",
    )
    min_analysts = c2.slider(
        "Min # of Analysts",
        min_value=1, max_value=20, value=_url_analysts, step=1,
        help="Require at least this many analysts to avoid thin coverage",
    )
    max_rating = c3.select_slider(
        "Max Rating (consensus)",
        options=[1.5, 2.0, 2.5],
        value=_url_rating,
        format_func=lambda v: {1.5: "Strong Buy only", 2.0: "Buy & above", 2.5: "Moderate Buy & above"}[v],
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
    st.query_params["upside"]   = str(min_upside)
    st.query_params["analysts"] = str(min_analysts)
    st.query_params["rating"]   = str(max_rating)
    st.query_params["top"]      = str(top_n)
    st.query_params["scan"]     = "1"

    with st.spinner("💎 Fetching analyst consensus data…"):
        df = fetch_strong_buy_candidates(
            min_upside=float(min_upside),
            min_analysts=int(min_analysts),
            max_rating=float(max_rating),
            top_n=top_n,
        )

    if df.empty:
        st.warning(
            f"No stocks found with analyst rating ≤ {max_rating}, "
            f"upside ≥ {min_upside}%, and ≥ {min_analysts} analysts. "
            "Try relaxing the filters."
        )
        return

    st.success(f"✅ Found **{len(df)}** analyst-backed candidates")

    # ── Summary metrics ───────────────────────────────────────────────────────
    strong_buys = int((df["Rating"] <= 1.5).sum())
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Candidates",         len(df))
    m2.metric("⭐ Strong Buy",      strong_buys)
    m3.metric("Avg Upside %",       f"{df['Upside %'].mean():.1f}%")
    m4.metric("Avg Analyst Rating", f"{df['Rating'].mean():.2f}")
    m5.metric("Avg # Analysts",     f"{df['Analysts'].mean():.0f}")
    m6.metric("Avg SB Score",       f"{df['SB Score'].mean():.1f}")

    st.markdown("---")

    # ── Score formula explainer ───────────────────────────────────────────────
    with st.expander("📐 How the Strong Buy Score is calculated", expanded=False):
        st.markdown("""
        | Component | Formula | Max |
        |---|---|---|
        | Analyst Rating | `(2.5 − rating) × 26.7` — lower rating scores higher | 40 |
        | Price Target Upside | `min(upside %, 50) × 0.5` | 25 |
        | Analyst Coverage | `min(# analysts, 20) × 1.5` — more analysts = more reliable | 30 |
        | RSI Entry Bonus | +5 if RSI < 60 (stock is not overbought at entry) | 5 |

        **Rating scale:** 1.0 = Strong Buy · 2.0 = Buy · 3.0 = Hold · 4.0 = Sell · 5.0 = Strong Sell

        **Total max ≈ 100.** Score > 60 = high-conviction setup. Score > 75 = exceptional.
        """)

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Candidates — sorted by Strong Buy Score ↓")
    display_cols = [
        "Ticker", "Company", "Sector", "Price", "Target",
        "Target Low", "Target High", "Upside %",
        "Consensus", "Rating", "Analysts", "RSI", "SB Score",
    ]
    st.dataframe(
        _style_table(df[display_cols]),
        width="stretch", hide_index=True,
    )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        # ── Upside % bar chart ─────────────────────────────────────────────
        st.markdown("#### Price Target Upside %")
        st.caption("Mean analyst price target vs current price")
        st.plotly_chart(_upside_bar_chart(df), width="stretch")

    with col2:
        # ── Rating vs Upside scatter ───────────────────────────────────────
        st.markdown("#### Rating vs Upside — bubble = analyst count")
        st.plotly_chart(_scatter_chart(df), width="stretch")

    # ── Sector breakdown ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Sector Distribution")
    st.plotly_chart(_sector_chart(df), width="stretch")


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row(row):
        styles = [""] * len(row)
        cols   = list(df.columns)

        # Consensus
        cons_i = cols.index("Consensus")
        if "Strong Buy" in str(row["Consensus"]):
            styles[cons_i] = "color:#FACC15;font-weight:700"
        elif "Buy" in str(row["Consensus"]):
            styles[cons_i] = "color:#22C55E;font-weight:600"
        else:
            styles[cons_i] = "color:#F59E0B;font-weight:600"

        # Upside %
        up_i = cols.index("Upside %")
        if row["Upside %"] >= 20:
            styles[up_i] = "color:#22C55E;font-weight:700"
        elif row["Upside %"] >= 10:
            styles[up_i] = "color:#86EFAC;font-weight:600"

        # RSI — flag if overbought
        if "RSI" in cols and row["RSI"] is not None:
            rsi_i = cols.index("RSI")
            if row["RSI"] >= 70:
                styles[rsi_i] = "color:#EF4444;font-weight:700"
            elif row["RSI"] <= 40:
                styles[rsi_i] = "color:#22C55E;font-weight:600"

        # SB Score
        sb_i = cols.index("SB Score")
        if row["SB Score"] >= 75:
            styles[sb_i] = "color:#FACC15;font-weight:700"
        elif row["SB Score"] >= 60:
            styles[sb_i] = "color:#22C55E;font-weight:600"

        return styles

    fmt = {
        "Price":       "${:.2f}",
        "Target":      "${:.2f}",
        "Target High": "${:.2f}",
        "Target Low":  "${:.2f}",
        "Upside %":    "{:+.1f}%",
        "Rating":      "{:.2f}",
        "SB Score":    "{:.1f}",
    }
    if "RSI" in df.columns:
        fmt["RSI"] = "{:.1f}"

    return df.style.apply(_row, axis=1).format(fmt, na_rep="—")


def _upside_bar_chart(df) -> go.Figure:
    sorted_df = df.sort_values("Upside %", ascending=False)
    colors = [
        "#22C55E" if u >= 20 else "#86EFAC" if u >= 10 else "#64748B"
        for u in sorted_df["Upside %"]
    ]
    fig = go.Figure(go.Bar(
        x=sorted_df["Ticker"],
        y=sorted_df["Upside %"],
        marker_color=colors,
        text=sorted_df["Upside %"].apply(lambda v: f"+{v:.1f}%"),
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Current: $%{customdata[0]:.2f}<br>"
            "Target:  $%{customdata[1]:.2f}<br>"
            "Upside:  +%{y:.1f}%<extra></extra>"
        ),
        customdata=sorted_df[["Price", "Target"]].values,
    ))
    fig.add_hline(y=20, line_dash="dot", line_color="#22C55E",
                  annotation_text="≥20% upside", annotation_font_size=9)
    fig.add_hline(y=10, line_dash="dot", line_color="#86EFAC",
                  annotation_text="≥10% upside", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=20, r=80, t=10, b=40),
        yaxis=dict(title="Upside %", ticksuffix="%"),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def _scatter_chart(df) -> go.Figure:
    bubble_size = (df["Analysts"] / df["Analysts"].max() * 35 + 10).tolist()
    colors = [
        "#FACC15" if r <= 1.5 else "#22C55E" if r <= 2.0 else "#F59E0B"
        for r in df["Rating"]
    ]
    fig = go.Figure(go.Scatter(
        x=df["Rating"],
        y=df["Upside %"],
        mode="markers+text",
        text=df["Ticker"],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(size=bubble_size, color=colors, opacity=0.85,
                    line=dict(color="#FFFFFF", width=0.5)),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Rating: %{x:.2f}<br>"
            "Upside: +%{y:.1f}%<br>"
            "<extra></extra>"
        ),
    ))
    fig.add_vline(x=1.5, line_dash="dot", line_color="#FACC15",
                  annotation_text="Strong Buy", annotation_font_size=9)
    fig.add_vline(x=2.0, line_dash="dot", line_color="#22C55E",
                  annotation_text="Buy", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=40, r=40, t=20, b=40),
        xaxis=dict(title="Analyst Rating (lower = more bullish)", autorange="reversed"),
        yaxis=dict(title="Upside %", ticksuffix="%"),
        showlegend=False,
    )
    return fig


def _sector_chart(df) -> go.Figure:
    sector_counts = df.groupby("Sector").agg(
        Count=("Ticker", "count"),
        Avg_Upside=("Upside %", "mean"),
        Avg_Score=("SB Score", "mean"),
    ).reset_index().sort_values("Avg_Score", ascending=True)

    fig = go.Figure(go.Bar(
        x=sector_counts["Avg_Score"],
        y=sector_counts["Sector"],
        orientation="h",
        marker_color="#3B82F6",
        text=sector_counts.apply(
            lambda r: f"{r['Count']} stocks · avg +{r['Avg_Upside']:.1f}% upside", axis=1
        ),
        textposition="inside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Avg SB Score: %{x:.1f}<br>"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(
        template="plotly_dark",
        height=max(200, len(sector_counts) * 40),
        margin=dict(l=20, r=40, t=10, b=40),
        xaxis=dict(title="Avg Strong Buy Score"),
        yaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def _render_legend() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**How analyst ratings work**\n\n"
            "Wall Street analysts publish price targets and ratings for the stocks they cover. "
            "The **consensus rating** averages all active analyst opinions:\n\n"
            "- ⭐ **Strong Buy** (≤ 1.5) — overwhelming bullish conviction\n"
            "- 🟢 **Buy** (≤ 2.0) — majority bullish\n"
            "- 🟡 **Moderate Buy** (≤ 2.5) — cautiously bullish\n\n"
            "More analysts covering a stock = more reliable consensus signal."
        )
    with col2:
        st.markdown("**What to look for:**")
        st.markdown("""
        | Signal | Meaning |
        |---|---|
        | Rating ≤ 1.5 | ⭐ Analysts overwhelmingly bullish |
        | Upside ≥ 20% | 🟢 Large gap to consensus target |
        | Analysts ≥ 10 | High-confidence coverage |
        | RSI < 60 | Not overbought — good entry |
        | SB Score ≥ 75 | 🟡 Exceptional conviction setup |
        """)
    st.markdown("Adjust filters and click **Scan** to find candidates.")


render_strong_buy_tab()

