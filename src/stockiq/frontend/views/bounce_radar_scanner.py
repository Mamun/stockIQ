import streamlit as st

from stockiq.backend.services.scanners import get_bounce_radar_scan
from stockiq.frontend.theme import DN, UP
from stockiq.frontend.views.components.scanner_charts import rsi_bar


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
    scan_btn = c3.button("🔍 Scan", width="stretch", type="primary")

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
    m1.metric("Candidates found",   len(df))
    m2.metric("Oversold (RSI ≤ 30)", int((df["RSI"] <= 30).sum()))
    m3.metric("Below MA 200",        int((df["Distance %"] < 0).sum()))
    m4.metric("Avg RSI",             f"{df['RSI'].mean():.1f}")

    st.markdown("---")

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Candidates — sorted by Bounce Score ↓")
    st.caption(
        "**Bounce Score** = proximity to MA200 + RSI oversold bonus + below-MA200 support bonus"
    )
    st.dataframe(_style_table(df), width="stretch", hide_index=True, height=(len(df) + 1) * 35 + 4)

    # ── RSI bar chart ─────────────────────────────────────────────────────────
    st.markdown("#### RSI Distribution")
    st.plotly_chart(rsi_bar(df), width="stretch")


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row_style(row):
        styles   = [""] * len(row)
        dist_idx = df.columns.get_loc("Distance %")
        rsi_idx  = df.columns.get_loc("RSI")

        dist = row["Distance %"]
        if dist < 0:
            styles[dist_idx] = f"color:{UP};font-weight:600"
        else:
            styles[dist_idx] = "color:#F59E0B;font-weight:600"

        rsi = row["RSI"]
        if rsi <= 30:
            styles[rsi_idx] = f"color:{UP};font-weight:700"
        elif rsi >= 70:
            styles[rsi_idx] = f"color:{DN};font-weight:700"

        return styles

    return df.style.apply(_row_style, axis=1).format({
        "Price":        "${:.2f}",
        "MA 200":       "${:.2f}",
        "Distance %":   "{:+.2f}%",
        "RSI":          "{:.1f}",
        "Bounce Score": "{:.1f}",
    })


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
