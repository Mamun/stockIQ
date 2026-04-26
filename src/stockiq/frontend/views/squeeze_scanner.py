import streamlit as st

from stockiq.backend.services.scanners import get_squeeze_scan
from stockiq.frontend.theme import DN, UP
from stockiq.frontend.views.components.scanner_charts import (
    days_to_cover_bar,
    squeeze_scatter,
)


def render_squeeze_scanner_tab() -> None:
    st.title("🔥 Squeeze Scanner")
    st.markdown(
        "Finds stocks that are **overbought** (high RSI) **and** heavily shorted. "
        "As price rises, short sellers are forced to buy to cut losses — "
        "that buying pressure accelerates the move upward. "
        "High Squeeze Score = stronger pressure on shorts."
    )

    # ── URL params ────────────────────────────────────────────────────────────
    params    = st.query_params
    auto_scan = params.get("scan", "0") == "1"
    try:    _url_rsi   = max(45,  min(85,  int(params.get("rsi",   45))))
    except: _url_rsi   = 45
    try:    _url_short = max(0.1, min(5.0, round(float(params.get("short", 0.1)), 1)))
    except: _url_short = 0.1
    try:    _url_top   = max(10,  min(50,  int(params.get("top",   50))))
    except: _url_top   = 50

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    rsi_min = c1.slider(
        "Min RSI",
        min_value=45, max_value=85, value=_url_rsi, step=5,
        help="Only include stocks with RSI at or above this level",
    )
    min_short_float = c2.slider(
        "Min Short % of Float",
        min_value=0.1, max_value=5.0, value=_url_short, step=0.1,
        help="S&P 500 large-caps typically range 0.5–3%. Even 2%+ is elevated for this universe.",
    )
    top_n = c3.slider(
        "Max results",
        min_value=10, max_value=50, value=_url_top, step=5,
    )
    scan_btn = c4.button("🔍 Scan", width="stretch", type="primary")

    st.markdown("---")

    if not scan_btn and not auto_scan:
        _render_legend()
        return

    st.query_params["rsi"]   = str(rsi_min)
    st.query_params["short"] = str(min_short_float)
    st.query_params["top"]   = str(top_n)
    st.query_params["scan"]  = "1"

    with st.spinner("🔥 Scanning for squeeze setups…"):
        df = get_squeeze_scan(
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
    st.dataframe(_style_table(df), width="stretch", hide_index=True, height=(len(df) + 1) * 35 + 4)

    # ── Charts ────────────────────────────────────────────────────────────────
    st.markdown("#### Short Float % vs RSI — bubble size = Squeeze Score")
    st.plotly_chart(squeeze_scatter(df), width="stretch")

    st.markdown("#### Days to Cover")
    st.caption("Higher = shorts need more trading days to exit → more fuel if squeeze ignites")
    st.plotly_chart(days_to_cover_bar(df), width="stretch")


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row(row):
        styles = [""] * len(row)
        cols   = list(df.columns)

        rsi_i = cols.index("RSI")
        rsi   = row["RSI"]
        if rsi >= 80:
            styles[rsi_i] = f"color:{DN};font-weight:700"
        elif rsi >= 70:
            styles[rsi_i] = "color:#F97316;font-weight:700"
        else:
            styles[rsi_i] = "color:#FACC15;font-weight:600"

        spf_i = cols.index("Short % Float")
        spf   = row["Short % Float"]
        if spf >= 15:
            styles[spf_i] = f"color:{DN};font-weight:700"
        elif spf >= 8:
            styles[spf_i] = "color:#F97316;font-weight:600"

        chg_i = cols.index("Short Chg % MoM")
        chg   = row["Short Chg % MoM"]
        if chg > 0:
            styles[chg_i] = f"color:{DN}"
        elif chg < 0:
            styles[chg_i] = f"color:{UP}"

        sc_i = cols.index("Squeeze Score")
        if row["Squeeze Score"] >= 50:
            styles[sc_i] = f"color:{DN};font-weight:700"
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


render_squeeze_scanner_tab()
