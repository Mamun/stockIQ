import plotly.graph_objects as go
import streamlit as st

from indexiq.data import fetch_munger_candidates


def render_munger_tab() -> None:
    st.title("🎩 Munger Watchlist")
    st.markdown(
        "_\"It's far better to buy a wonderful company at a fair price "
        "than a fair company at a wonderful price.\"_ — Charlie Munger\n\n"
        "Finds **high-quality S&P 500 companies** trading near their "
        "**200-week moving average** — Munger's preferred entry zone for "
        "long-term compounding machines."
    )

    # ── URL params ────────────────────────────────────────────────────────────
    params    = st.query_params
    auto_scan = params.get("scan", "0") == "1"
    try:    _url_dist    = max(5,  min(30, int(params.get("dist",    30))))
    except: _url_dist    = 30
    try:    _url_quality = max(10, min(60, int(params.get("quality", 10))))
    except: _url_quality = 10
    try:    _url_top     = max(10, min(50, int(params.get("top",     50))))
    except: _url_top     = 50

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    threshold = c1.slider(
        "Max distance from MA 200W (%)",
        min_value=5, max_value=30, value=_url_dist, step=5,
        help="Only include stocks whose price is within this % of the 200-week MA",
    )
    min_quality = c2.slider(
        "Min Quality Score",
        min_value=10, max_value=60, value=_url_quality, step=5,
        help="Quality Score is built from ROE, Profit Margin, Revenue Growth, D/E, EPS Growth (max 85)",
    )
    top_n = c3.slider(
        "Max results",
        min_value=10, max_value=50, value=_url_top, step=5,
    )
    scan_btn = c4.button("🔍 Scan", width='stretch', type="primary")

    st.markdown("---")

    if not scan_btn and not auto_scan:
        _render_legend()
        return

    # Sync current filter state into URL so the page is shareable
    st.query_params["dist"]    = str(threshold)
    st.query_params["quality"] = str(min_quality)
    st.query_params["top"]     = str(top_n)
    st.query_params["scan"]    = "1"

    with st.spinner("🎩 Scanning for Munger-style setups…"):
        df = fetch_munger_candidates(
            threshold_pct=float(threshold),
            min_quality=float(min_quality),
            top_n=top_n,
        )

    if df.empty:
        st.warning(
            f"No stocks found within ±{threshold}% of their 200-week MA "
            f"with Quality Score ≥ {min_quality}. "
            "Try widening the thresholds."
        )
        return

    st.success(f"✅ Found **{len(df)}** Munger-style candidates")

    # ── Summary metrics ───────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Candidates",           len(df))
    m2.metric("Below MA 200W",        int((df["Distance %"] < 0).sum()))
    m3.metric("Avg Quality Score",    f"{df['Quality Score'].mean():.1f}")
    m4.metric("Avg Munger Score",     f"{df['Munger Score'].mean():.1f}")
    m5.metric("Score ≥ 70",           int((df["Munger Score"] >= 70).sum()))

    st.markdown("---")

    # ── Score formula explainer ───────────────────────────────────────────────
    with st.expander("📐 How the Munger Score is calculated", expanded=False):
        st.markdown("""
        ### Quality Score (max 85)

        | Component | Formula | Max |
        |---|---|---|
        | Return on Equity (ROE) | ≥20% → 25 · ≥15% → 18 · ≥10% → 10 · >0% → 5 | 25 |
        | Profit Margin | ≥20% → 20 · ≥10% → 14 · ≥5% → 8 · >0% → 3 | 20 |
        | Revenue Growth (YoY) | ≥15% → 15 · ≥8% → 10 · ≥3% → 6 · ≥0% → 2 | 15 |
        | Debt/Equity ratio | <0.30× → 15 · <0.70× → 10 · <1.50× → 5 | 15 |
        | EPS Growth (YoY) | ≥15% → 10 · ≥8% → 7 · ≥0% → 3 | 10 |

        ### Proximity Score (max 15)

        | Distance from MA 200W | Points |
        |---|---|
        | ≤ 2% | 15 |
        | ≤ 5% | 12 |
        | ≤ 10% | 8 |
        | ≤ 15% | 4 |
        | ≤ 20% | 2 |

        **Munger Score = Quality Score + Proximity Score (max 100)**

        A score > 50 is a solid setup. > 70 is exceptional.
        Prefer stocks **below** the 200W MA (Distance % < 0) — price is testing long-term support.
        """)

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Candidates — sorted by Munger Score ↓")
    display_cols = [
        "Ticker", "Company", "Sector", "Price", "MA 200W",
        "Distance %", "RSI", "Quality Score", "Prox Score", "Munger Score",
    ]
    st.dataframe(_style_table(df[display_cols]), width='stretch', hide_index=True)

    # ── Quality breakdown expander per ticker ─────────────────────────────────
    with st.expander("🔬 Fundamental breakdown per stock", expanded=False):
        bd_df = df[["Ticker", "Company", "Quality Score", "Breakdown"]].copy()
        st.dataframe(bd_df, width='stretch', hide_index=True)

    # ── Scatter: Distance % vs Quality Score ──────────────────────────────────
    st.markdown("#### Distance from MA 200W vs Quality Score — bubble size = Munger Score")
    st.plotly_chart(_scatter_chart(df), width='stretch')

    # ── Quality score bar chart ───────────────────────────────────────────────
    st.markdown("#### Quality Score by Company")
    st.plotly_chart(_quality_bar_chart(df), width='stretch')


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row(row):
        n = len(row)
        styles = [""] * n
        cols = list(df.columns)

        # Distance %: green = below MA200W, amber = above
        dist_i = cols.index("Distance %")
        if row["Distance %"] < 0:
            styles[dist_i] = "color:#22C55E;font-weight:600"
        else:
            styles[dist_i] = "color:#F59E0B;font-weight:600"

        # RSI
        rsi_i = cols.index("RSI")
        rsi = row["RSI"]
        if rsi <= 30:
            styles[rsi_i] = "color:#22C55E;font-weight:700"
        elif rsi >= 70:
            styles[rsi_i] = "color:#EF4444;font-weight:700"

        # Quality Score
        qs_i = cols.index("Quality Score")
        if row["Quality Score"] >= 60:
            styles[qs_i] = "color:#22C55E;font-weight:700"
        elif row["Quality Score"] >= 40:
            styles[qs_i] = "color:#F59E0B;font-weight:600"

        # Munger Score
        ms_i = cols.index("Munger Score")
        if row["Munger Score"] >= 70:
            styles[ms_i] = "color:#22C55E;font-weight:700"
        elif row["Munger Score"] >= 50:
            styles[ms_i] = "color:#F59E0B;font-weight:600"

        return styles

    return df.style.apply(_row, axis=1).format({
        "Price":         "${:.2f}",
        "MA 200W":       "${:.2f}",
        "Distance %":    "{:+.2f}%",
        "RSI":           "{:.1f}",
        "Quality Score": "{:.1f}",
        "Munger Score":  "{:.1f}",
    })


def _scatter_chart(df) -> go.Figure:
    bubble_size = (df["Munger Score"] / df["Munger Score"].max() * 40 + 10).tolist()
    colors = [
        "#22C55E" if d < 0 else "#F59E0B"
        for d in df["Distance %"]
    ]
    fig = go.Figure(go.Scatter(
        x=df["Distance %"],
        y=df["Quality Score"],
        mode="markers+text",
        text=df["Ticker"],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(size=bubble_size, color=colors, opacity=0.85,
                    line=dict(color="#FFFFFF", width=0.5)),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Distance from MA200W: %{x:+.2f}%<br>"
            "Quality Score: %{y:.1f}<br>"
            "<extra></extra>"
        ),
    ))
    fig.add_vline(x=0, line_dash="dot", line_color="#64748B",
                  annotation_text="At MA 200W", annotation_font_size=9)
    fig.add_annotation(x=-12, y=df["Quality Score"].max() * 0.95,
                       text="🟢 Sweet spot", showarrow=False,
                       font=dict(color="#22C55E", size=11))
    fig.update_layout(
        template="plotly_dark",
        height=380,
        margin=dict(l=40, r=80, t=20, b=40),
        xaxis=dict(title="Distance from 200-Week MA (%)"),
        yaxis=dict(title="Quality Score"),
    )
    return fig


def _quality_bar_chart(df) -> go.Figure:
    sorted_df = df.sort_values("Quality Score", ascending=False)
    colors = [
        "#22C55E" if q >= 60 else "#F59E0B" if q >= 40 else "#64748B"
        for q in sorted_df["Quality Score"]
    ]
    fig = go.Figure(go.Bar(
        x=sorted_df["Ticker"],
        y=sorted_df["Quality Score"],
        marker_color=colors,
        text=sorted_df["Quality Score"].apply(lambda v: f"{v:.0f}"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Quality Score: %{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=60, line_dash="dot", line_color="#22C55E",
                  annotation_text="≥60 excellent", annotation_font_size=9)
    fig.add_hline(y=40, line_dash="dot", line_color="#F59E0B",
                  annotation_text="≥40 good", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark",
        height=300,
        margin=dict(l=20, r=120, t=10, b=40),
        yaxis=dict(title="Quality Score", range=[0, 100]),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def _render_legend() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**Charlie Munger's investing philosophy**\n\n"
            "Munger looked for *moat companies* — businesses with durable competitive "
            "advantages, high returns on equity, clean balance sheets, and growing earnings. "
            "He was willing to pay a fair price but preferred buying near long-term support "
            "levels like the **200-week moving average** to maximise margin of safety."
        )
    with col2:
        st.markdown("**What the scores mean:**")
        st.markdown("""
        | Score | Meaning |
        |---|---|
        | Quality ≥ 60 | 🟢 Excellent fundamentals |
        | Quality ≥ 40 | 🟡 Good fundamentals |
        | Distance < 0% | 🟢 Below MA 200W — testing support |
        | Distance > 0% | 🟡 Above MA 200W |
        | Munger ≥ 70 | 🟢 Strong setup |
        | Munger ≥ 50 | 🟡 Solid setup |
        """)
    st.markdown("Adjust thresholds and click **Scan** to find candidates.")


render_munger_tab()

