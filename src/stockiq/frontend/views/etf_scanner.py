import streamlit as st

from stockiq.backend.services.scanners import get_etf_scan
from stockiq.frontend.views.components.scanner_charts import (
    etf_category_heatmap,
    etf_return_bar,
    etf_score_bar,
)

_ALL_CATEGORIES = (
    "Retail Favorites", "Broad Market", "Sector", "Fixed Income",
    "Commodity", "International", "Semiconductor", "Software",
)


def render_etf_scanner_tab() -> None:
    st.title("🌐 ETF Scanner")
    st.markdown(
        "Scans **30+ ETFs** across Broad Market, Sectors, Fixed Income, Commodities, "
        "and International markets. Surfaces momentum leaders, oversold entries, "
        "MA crossover signals, and volume surges in one view."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([3, 2, 1])

    selected_cats = c1.multiselect(
        "Categories",
        options=list(_ALL_CATEGORIES),
        default=["Retail Favorites"],
        help="Filter by ETF category — Retail Favorites shows the most-watched ETFs first",
    )

    sort_by = c2.selectbox(
        "Sort by",
        options=["ETF Score", "1D %", "1W %", "1M %", "3M %", "vs SPY", "RSI"],
        index=0,
    )

    scan_btn = c3.button("🔍 Scan", type="primary", width="stretch")

    st.markdown("---")

    params    = st.query_params
    auto_scan = params.get("scan", "0") == "1"

    if not scan_btn and not auto_scan:
        _render_legend()
        return

    st.query_params["scan"] = "1"

    cats = tuple(selected_cats) if selected_cats else _ALL_CATEGORIES

    with st.spinner("🌐 Fetching ETF data…"):
        df = get_etf_scan(categories=cats)

    if df.empty:
        st.warning("No ETF data returned. Try again in a moment.")
        return

    asc = sort_by == "RSI"
    df  = df.sort_values(sort_by, ascending=asc, na_position="last").reset_index(drop=True)

    st.success(f"✅ Scanned **{len(df)}** ETFs")

    # ── Summary metrics ───────────────────────────────────────────────────────
    bullish  = int((df["MA Signal"] == "🟢 Bullish").sum())
    bearish  = int((df["MA Signal"] == "🔴 Bearish").sum())
    oversold = int((df["RSI"] <= 35).sum())
    surging  = int((df["Vol"] == "🔼").sum())

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("ETFs Scanned",      len(df))
    m2.metric("🟢 MA Bullish",     bullish)
    m3.metric("🔴 MA Bearish",     bearish)
    m4.metric("Oversold (RSI≤35)", oversold)
    m5.metric("Vol Surging",       surging)
    m6.metric("Avg ETF Score",     f"{df['ETF Score'].mean():.1f}")

    st.markdown("---")

    # ── Score formula expander ────────────────────────────────────────────────
    with st.expander("📐 How the ETF Score is calculated", expanded=False):
        st.markdown("""
        | Component | Formula | Range |
        |---|---|---|
        | Base | Starting score | 50 |
        | 1M Return | `min(ret_1m × 1.5, +15)` — rewards momentum | ±15 |
        | vs SPY | `min(vs_spy × 1.0, +10)` — rewards outperformance | ±10 |
        | RSI Entry | +10 if RSI ≤ 40 (oversold), −10 if RSI ≥ 70 (overbought) | ±10 |
        | MA Cross | +10 if MA20 > MA50 (bullish), −10 if MA20 < MA50 (bearish) | ±10 |
        | Volume | +5 if 5-day avg vol > 1.2× the 20-day avg | +5 |

        **Score > 65** = strong bullish setup · **Score < 35** = weak/bearish
        """)

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### ETF Results")
    display_cols = [
        "Ticker", "Name", "Category", "Price",
        "1D %", "1W %", "1M %", "3M %", "vs SPY",
        "RSI", "RSI Zone", "MA Signal", "MA200 Dist%", "Vol", "ETF Score",
    ]
    st.dataframe(
        _style_table(df[display_cols]),
        width="stretch",
        hide_index=True,
        height=(len(df) + 1) * 35 + 4,
    )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 1M Return by ETF")
        st.plotly_chart(etf_return_bar(df, "1M %", "1M Return %"), width="stretch")
    with col2:
        st.markdown("#### ETF Score Ranking")
        st.plotly_chart(etf_score_bar(df), width="stretch")

    st.markdown("---")
    st.markdown("#### Category Heatmap — Avg 1M Return")
    st.plotly_chart(etf_category_heatmap(df), width="stretch")


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row(row):
        styles = [""] * len(row)
        cols   = list(df.columns)

        for col in ("1D %", "1W %", "1M %", "3M %", "vs SPY"):
            if col in cols:
                i = cols.index(col)
                v = row[col]
                if v is None:
                    continue
                if v >= 3:
                    styles[i] = "color:#22C55E;font-weight:700"
                elif v >= 0:
                    styles[i] = "color:#86EFAC"
                elif v >= -3:
                    styles[i] = "color:#FCA5A5"
                else:
                    styles[i] = "color:#EF4444;font-weight:700"

        if "RSI" in cols:
            i = cols.index("RSI")
            if row["RSI"] <= 30:
                styles[i] = "color:#22C55E;font-weight:700"
            elif row["RSI"] >= 70:
                styles[i] = "color:#EF4444;font-weight:700"

        if "MA Signal" in cols:
            i = cols.index("MA Signal")
            if "Bullish" in str(row["MA Signal"]):
                styles[i] = "color:#22C55E;font-weight:600"
            elif "Bearish" in str(row["MA Signal"]):
                styles[i] = "color:#EF4444;font-weight:600"

        if "ETF Score" in cols:
            i = cols.index("ETF Score")
            if row["ETF Score"] >= 65:
                styles[i] = "color:#FACC15;font-weight:700"
            elif row["ETF Score"] >= 55:
                styles[i] = "color:#22C55E;font-weight:600"
            elif row["ETF Score"] < 35:
                styles[i] = "color:#EF4444;font-weight:600"

        return styles

    fmt = {
        "Price":       "${:.2f}",
        "1D %":        "{:+.2f}%",
        "1W %":        "{:+.1f}%",
        "1M %":        "{:+.1f}%",
        "3M %":        "{:+.1f}%",
        "vs SPY":      "{:+.1f}%",
        "RSI":         "{:.1f}",
        "MA200 Dist%": "{:+.1f}%",
        "ETF Score":   "{:.1f}",
    }
    return df.style.apply(_row, axis=1).format(fmt, na_rep="—")


def _render_legend() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**ETF Scanner covers 8 asset classes:**\n\n"
            "- 🔥 **Retail Favorites** — SPY, QQQ, TQQQ, SOXL, ARKK, VXX, JETS…\n"
            "- 📈 **Broad Market** — SPY, QQQ, IWM, DIA, VTI, VOO\n"
            "- 🏭 **Sectors** — All 11 SPDR sector ETFs (XLK, XLF, XLE…)\n"
            "- 💵 **Fixed Income** — TLT, IEF, SHY, HYG, LQD\n"
            "- 🥇 **Commodities** — GLD, SLV, USO, UNG, DBA\n"
            "- 🌍 **International** — EFA, EEM, FXI, EWJ, IEFA\n"
            "- 🔬 **Semiconductor** — SOXX, SMH, SOXQ, PSI, FTXL\n"
            "- 💻 **Software** — IGV, WCLD, BUG, CIBR, CLOU"
        )
    with col2:
        st.markdown("**Signal guide:**")
        st.markdown("""
        | Signal | Meaning |
        |---|---|
        | ETF Score ≥ 65 | 🟡 Strong bullish setup |
        | MA Signal 🟢 | MA20 crossed above MA50 |
        | RSI ≤ 35 | 🟢 Oversold — potential entry |
        | RSI ≥ 70 | 🔴 Overbought — caution |
        | Vol 🔼 | 5-day avg volume > 1.2× 20-day |
        | vs SPY | Relative outperformance vs S&P 500 |
        """)
    st.markdown("Select categories, choose sort order, and click **Scan**.")


render_etf_scanner_tab()
