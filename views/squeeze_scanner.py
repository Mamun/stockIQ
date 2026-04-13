import plotly.graph_objects as go
import streamlit as st

from data import fetch_squeeze_candidates


def render_squeeze_scanner_tab() -> None:
    st.title("🔥 Squeeze Scanner")
    st.markdown(
        "Finds stocks that are **overbought** (high RSI) **and** heavily shorted. "
        "As price rises, short sellers are forced to buy to cut losses — "
        "that buying pressure accelerates the move upward. "
        "High Squeeze Score = stronger pressure on shorts."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    rsi_min = c1.slider(
        "Min RSI",
        min_value=45, max_value=85, value=55, step=5,
        help="Only include stocks with RSI at or above this level",
    )
    min_short_float = c2.slider(
        "Min Short % of Float",
        min_value=0.1, max_value=5.0, value=0.5, step=0.1,
        help="S&P 500 large-caps typically range 0.5–3%. Even 2%+ is elevated for this universe.",
    )
    top_n = c3.slider(
        "Max results",
        min_value=10, max_value=50, value=30, step=5,
    )
    scan_btn = c4.button("🔍 Scan", use_container_width=True, type="primary")

    st.markdown("---")

    if not scan_btn:
        _render_legend()
        return

    with st.spinner("🔥 Scanning for squeeze setups…"):
        df = fetch_squeeze_candidates(
            rsi_min=float(rsi_min),
            min_short_float=float(min_short_float),
            top_n=top_n,
        )

    if df.empty:
        st.warning(
            f"No stocks found with RSI ≥ {rsi_min} and Short Float ≥ {min_short_float}%. "
            "Try lowering the thresholds."
        )
        return

    st.success(f"✅ Found **{len(df)}** squeeze candidates")

    # ── Summary metrics ───────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Candidates",        len(df))
    m2.metric("Extreme OB (≥80)",  int((df["RSI"] >= 80).sum()))
    m3.metric("Overbought (≥70)",  int((df["RSI"] >= 70).sum()))
    m4.metric("Avg Short % Float", f"{df['Short % Float'].mean():.1f}%")
    m5.metric("Shorts Building",   int((df["Short Chg % MoM"] > 0).sum()))

    st.markdown("---")

    # ── Score formula explainer ───────────────────────────────────────────────
    with st.expander("📐 How the Squeeze Score is calculated", expanded=False):
        st.markdown("""
        | Component | Formula | Max |
        |---|---|---|
        | RSI elevation | `(RSI − 50) × 0.4` | ~20 |
        | Short % of float | ≥ 5% → 40 pts · ≥ 3% → 25 · ≥ 1.5% → 15 · else → pct × 8 | 40 |
        | Days to cover | ≥ 10 days → 20 pts · ≥ 5 → 12 · ≥ 2 → 6 · else → ratio × 2 | 20 |
        | Shorts building | +5 if short interest increased month-over-month | 5 |

        **Total max ≈ 85.** Tiers are calibrated for S&P 500 large-caps where
        1–3% short float is normal and ≥ 5% is genuinely elevated.
        A score > 25 is noteworthy. > 45 is a strong setup.
        """)

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Candidates — sorted by Squeeze Score ↓")
    st.dataframe(_style_table(df), use_container_width=True, hide_index=True)

    # ── Scatter: Short Float vs RSI (bubble = Squeeze Score) ─────────────────
    st.markdown("#### Short Float % vs RSI — bubble size = Squeeze Score")
    st.plotly_chart(_scatter_chart(df), use_container_width=True)

    # ── Days-to-cover bar chart ────────────────────────────────────────────────
    st.markdown("#### Days to Cover")
    st.caption("Higher = shorts need more trading days to exit → more fuel if squeeze ignites")
    st.plotly_chart(_days_to_cover_chart(df), use_container_width=True)


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row(row):
        n = len(row)
        styles = [""] * n
        cols = list(df.columns)

        rsi = row["RSI"]
        rsi_i = cols.index("RSI")
        if rsi >= 80:
            styles[rsi_i] = "color:#EF4444;font-weight:700"
        elif rsi >= 70:
            styles[rsi_i] = "color:#F97316;font-weight:700"
        else:
            styles[rsi_i] = "color:#FACC15;font-weight:600"

        spf = row["Short % Float"]
        spf_i = cols.index("Short % Float")
        if spf >= 15:
            styles[spf_i] = "color:#EF4444;font-weight:700"
        elif spf >= 8:
            styles[spf_i] = "color:#F97316;font-weight:600"

        chg = row["Short Chg % MoM"]
        chg_i = cols.index("Short Chg % MoM")
        if chg > 0:
            styles[chg_i] = "color:#EF4444"   # shorts growing = more pressure
        elif chg < 0:
            styles[chg_i] = "color:#22C55E"   # shorts covering = pressure easing

        sc_i = cols.index("Squeeze Score")
        if row["Squeeze Score"] >= 50:
            styles[sc_i] = "color:#EF4444;font-weight:700"
        elif row["Squeeze Score"] >= 30:
            styles[sc_i] = "color:#F97316;font-weight:600"

        return styles

    return df.style.apply(_row, axis=1).format({
        "Price":           "${:.2f}",
        "RSI":             "{:.1f}",
        "Short % Float":   "{:.1f}%",
        "Days to Cover":   "{:.1f}",
        "Short Chg % MoM": "{:+.1f}%",
        "Squeeze Score":   "{:.1f}",
    })


def _scatter_chart(df) -> go.Figure:
    """Short Float % (x) vs RSI (y), bubble size = Squeeze Score."""
    bubble_size = (df["Squeeze Score"] / df["Squeeze Score"].max() * 40 + 10).tolist()
    colors      = [
        "#EF4444" if r >= 80 else "#F97316" if r >= 70 else "#FACC15"
        for r in df["RSI"]
    ]
    fig = go.Figure(go.Scatter(
        x=df["Short % Float"],
        y=df["RSI"],
        mode="markers+text",
        text=df["Ticker"],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(size=bubble_size, color=colors, opacity=0.85,
                    line=dict(color="#FFFFFF", width=0.5)),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Short Float: %{x:.1f}%<br>"
            "RSI: %{y:.1f}<br>"
            "<extra></extra>"
        ),
    ))
    # Overbought / oversold reference lines
    fig.add_hline(y=80, line_dash="dot", line_color="#EF4444",
                  annotation_text="Extreme OB 80", annotation_font_size=9)
    fig.add_hline(y=70, line_dash="dot", line_color="#F97316",
                  annotation_text="Overbought 70", annotation_font_size=9)
    # Quadrant labels
    fig.add_annotation(x=df["Short % Float"].max() * 0.8, y=85,
                       text="⚡ High-risk zone", showarrow=False,
                       font=dict(color="#EF4444", size=11))
    fig.update_layout(
        template="plotly_dark",
        height=380,
        margin=dict(l=40, r=120, t=20, b=40),
        xaxis=dict(title="Short % of Float"),
        yaxis=dict(title="RSI (14)", range=[55, 100]),
    )
    return fig


def _days_to_cover_chart(df) -> go.Figure:
    sorted_df = df.sort_values("Days to Cover", ascending=False)
    colors = [
        "#EF4444" if d >= 10 else "#F97316" if d >= 5 else "#64748B"
        for d in sorted_df["Days to Cover"]
    ]
    fig = go.Figure(go.Bar(
        x=sorted_df["Ticker"],
        y=sorted_df["Days to Cover"],
        marker_color=colors,
        text=sorted_df["Days to Cover"].apply(lambda v: f"{v:.1f}d"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Days to Cover: %{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=10, line_dash="dot", line_color="#EF4444",
                  annotation_text="≥10 days (high pressure)", annotation_font_size=9)
    fig.add_hline(y=5, line_dash="dot", line_color="#F97316",
                  annotation_text="≥5 days", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark",
        height=300,
        margin=dict(l=20, r=120, t=10, b=40),
        yaxis=dict(title="Days to Cover"),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def _render_legend() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**What is a Short Squeeze?**\n\n"
            "Short sellers borrow shares and sell them, betting the price will fall. "
            "When price rises instead, they face unlimited losses and must buy shares to exit "
            "(*cover* their position). That forced buying pushes the price even higher — "
            "a self-reinforcing loop called a **short squeeze**."
        )
    with col2:
        st.markdown("**Squeeze Score breakdown:**")
        st.markdown("""
        | Signal | What to look for |
        |---|---|
        | RSI Zone | 🔴 ≥ 80 extreme · 🟠 ≥ 70 OB · 🟡 ≥ 55 elevated |
        | Short % Float | For S&P 500: ≥ 3% is high · ≥ 5% is very high |
        | Days to Cover | Higher = shorts need more days to exit — more fuel |
        | Short Chg MoM | 🔴 rising = shorts building · 🟢 falling = covering |
        | Squeeze Score | > 25 noteworthy · > 45 strong setup |
        """)
    st.markdown("Adjust thresholds and click **Scan** to start.")
