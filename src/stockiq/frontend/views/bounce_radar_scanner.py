import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stockiq.backend.services.scanners import get_bounce_radar_scan


def render_bounce_radar_tab() -> None:
    st.title("📡 Bounce Radar")
    st.markdown(
        "Scans S&P 500 stocks trading **near their 200-day moving average** — a key long-term "
        "support/resistance level. Low RSI + price near MA200 from below = highest bounce potential."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([2, 2, 1])
    threshold = c1.slider(
        "Max distance from MA 200 (%)",
        min_value=1, max_value=10, value=10, step=1,
        help="Only include stocks whose price is within this % of the 200-day MA",
    )
    top_n = c2.slider(
        "Max results to show",
        min_value=10, max_value=50, value=50, step=5,
    )
    scan_btn = c3.button("🔍 Scan", width='stretch', type="primary")

    st.markdown("---")

    if not scan_btn:
        _render_legend()
        return

    with st.spinner(f"Scanning for stocks within ±{threshold}% of MA 200…"):
        df = get_bounce_radar_scan(threshold_pct=float(threshold), top_n=top_n)

    if df.empty:
        st.warning(
            f"No stocks found within ±{threshold}% of their 200-day MA. "
            "Try increasing the distance threshold."
        )
        return

    st.success(f"✅ Found **{len(df)}** candidates within ±{threshold}% of MA 200")

    # ── Summary metrics ───────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Candidates found", len(df))
    m2.metric("Oversold (RSI ≤ 30)", int((df["RSI"] <= 30).sum()))
    m3.metric("Below MA 200",        int((df["Distance %"] < 0).sum()))
    m4.metric("Avg RSI",             f"{df['RSI'].mean():.1f}")

    st.markdown("---")

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Candidates — sorted by Bounce Score ↓")
    st.caption(
        "**Bounce Score** = proximity to MA200 + RSI oversold bonus + below-MA200 support bonus"
    )

    styled = _style_table(df)
    st.dataframe(styled, width='stretch', hide_index=True, height=(len(df) + 1) * 35 + 4)

    # ── RSI bar chart ─────────────────────────────────────────────────────────
    st.markdown("#### RSI Distribution")
    st.plotly_chart(_rsi_chart(df), width='stretch')


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df: pd.DataFrame):
    """Colour-code Distance % and RSI columns."""
    def _row_style(row):
        styles = [""] * len(row)
        dist_idx = df.columns.get_loc("Distance %")
        rsi_idx  = df.columns.get_loc("RSI")

        # Distance %: green tint below MA200, amber tint above
        dist = row["Distance %"]
        if dist < 0:
            styles[dist_idx] = "color:#22C55E;font-weight:600"
        else:
            styles[dist_idx] = "color:#F59E0B;font-weight:600"

        # RSI: red = overbought, green = oversold
        rsi = row["RSI"]
        if rsi <= 30:
            styles[rsi_idx] = "color:#22C55E;font-weight:700"
        elif rsi >= 70:
            styles[rsi_idx] = "color:#EF4444;font-weight:700"

        return styles

    return df.style.apply(_row_style, axis=1).format({
        "Price":        "${:.2f}",
        "MA 200":       "${:.2f}",
        "Distance %":   "{:+.2f}%",
        "RSI":          "{:.1f}",
        "Bounce Score": "{:.1f}",
    })


def _rsi_chart(df: pd.DataFrame) -> go.Figure:
    colors = [
        "#22C55E" if r <= 30 else "#EF4444" if r >= 70 else "#64748B"
        for r in df["RSI"]
    ]
    fig = go.Figure(go.Bar(
        x=df["Ticker"],
        y=df["RSI"],
        marker_color=colors,
        text=df["RSI"].apply(lambda v: f"{v:.1f}"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>RSI: %{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=70, line_dash="dot", line_color="#EF4444",
                  annotation_text="Overbought 70", annotation_position="right",
                  annotation_font_size=10)
    fig.add_hline(y=30, line_dash="dot", line_color="#22C55E",
                  annotation_text="Oversold 30", annotation_position="right",
                  annotation_font_size=10)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(100,116,139,0.07)", line_width=0)
    fig.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=20, r=100, t=20, b=40),
        yaxis=dict(title="RSI", range=[0, 105]),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def _render_legend() -> None:
    st.info(
        "**How Bounce Radar works**\n\n"
        "1. Scans the configured S&P 500 universe for stocks near their **200-day MA**\n"
        "2. Stocks **below** MA200 get a support-bounce bonus (testing a major floor)\n"
        "3. **Low RSI** (< 30 = oversold) adds further to the bounce score\n"
        "4. Results sorted by **Bounce Score** — highest = strongest setup\n\n"
        "Adjust the distance slider and click **Scan** to start."
    )
    st.markdown("| RSI Zone | Meaning |")
    st.markdown("|---|---|")
    st.markdown("| 🟢 ≤ 30 | Oversold — potential bounce |")
    st.markdown("| ⚪ 30–70 | Neutral |")
    st.markdown("| 🔴 ≥ 70 | Overbought — bounce less likely |")


render_bounce_radar_tab()

