import math

import streamlit as st

from stockiq.backend.services.scanners import get_forward_pe_scan
from stockiq.frontend.theme import DN, UP
from stockiq.frontend.views.components.scanner_charts import (
    forward_pe_bar,
    forward_pe_scatter,
    forward_pe_sector_bar,
)


def render_forward_pe_tab() -> None:
    st.title("📊 Forward P/E Value Picks")
    st.markdown(
        "Screens the **S&P 500** for stocks trading at a **discount to their sector's median "
        "forward P/E** with positive earnings growth. "
        "Lower forward P/E + higher EPS growth = higher **Value Growth Score**."
    )

    with st.expander("📖 What is Forward P/E? How to read this screen", expanded=False):
        st.markdown("""
**Forward P/E (Price-to-Earnings)** is the most widely used valuation metric on Wall Street.
It answers one question: *how much are you paying today for every $1 of earnings the company
is expected to make over the next 12 months?*

---

**📉 Is a low Forward P/E good or bad?**

**Usually good** — a low P/E means the market is pricing in modest expectations.
If the company beats those expectations, the stock re-rates sharply higher.

| Forward P/E | What it signals |
|---|---|
| **< 10** | Deep value — market expects slow growth, turnaround, or risk |
| **10 – 18** | Fair value — typical for stable, profitable companies |
| **18 – 30** | Growth premium — market expects above-average earnings growth |
| **> 30** | High expectations — any earnings miss can hurt significantly |

> ⚠️ A very low P/E isn't always a bargain — it can mean the business is declining
> ("value trap"). Always pair it with positive EPS growth to confirm the business is healthy.

---

**🏢 Why compare to the sector median?**

A P/E of 20 is cheap for a tech company (sector avg ~28) but expensive for a utility (avg ~15).
This screen highlights stocks trading **below their sector's own average** — a more meaningful
signal than a raw number.

---

**📐 The three key signals this screen uses:**

🔵 **Forward P/E vs Sector Median**
The lower the stock's P/E relative to peers, the higher it scores (up to 40 pts).
Stocks 20%+ below sector average are highlighted in green.

🟡 **EPS Growth %**
A cheap stock with *growing* earnings is the classic value-growth setup.
Scores up to 30 pts — higher growth = more points.

⭐ **PEG Ratio** (P/E ÷ EPS Growth Rate)
The "fair price" test: a PEG below 1 means you're paying less than 1× the growth rate —
historically one of the strongest value signals. PEG < 1 = +20 pts bonus.

---

**🟢 What makes a strong candidate?**

| Signal | Why it matters |
|---|---|
| Fwd P/E well below sector median | Undervalued vs direct peers |
| EPS Growth ≥ 15% | Business momentum is strong |
| PEG < 1 | Growth available at a genuine discount |
| RSI < 50 | Price has pulled back — better entry point |
| VG Score ≥ 70 | All signals aligning — high conviction setup |

> 💡 **Tip:** Start with **Max Forward P/E ≤ 20** and **Min EPS Growth ≥ 10%** for
> the highest-quality value-growth candidates. Relax the filters to see more results.
""")

    # ── URL params ────────────────────────────────────────────────────────────
    params    = st.query_params
    auto_scan = params.get("scan", "0") == "1"
    try:    _url_pe      = max(5,  min(60, int(params.get("pe",      25))))
    except: _url_pe      = 25
    try:    _url_growth  = max(0,  min(50, int(params.get("growth",   0))))
    except: _url_growth  = 0
    try:    _url_top     = max(5,  min(50, int(params.get("top",     30))))
    except: _url_top     = 30

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    max_fwd_pe = c1.slider(
        "Max Forward P/E",
        min_value=5, max_value=60, value=_url_pe, step=5,
        help="Only show stocks with forward P/E at or below this threshold",
    )
    min_eps_growth = c2.slider(
        "Min EPS Growth %",
        min_value=0, max_value=50, value=_url_growth, step=5,
        help="Require at least this much YoY earnings growth (0 = no filter)",
    )
    top_n = c3.slider(
        "Max results",
        min_value=5, max_value=50, value=_url_top, step=5,
    )
    scan_btn = c4.button("🔍 Scan", width="stretch", type="primary")

    st.markdown("---")

    if not scan_btn and not auto_scan:
        _render_legend()
        return

    st.query_params["pe"]     = str(max_fwd_pe)
    st.query_params["growth"] = str(min_eps_growth)
    st.query_params["top"]    = str(top_n)
    st.query_params["scan"]   = "1"

    with st.spinner("📊 Loading forward earnings data…"):
        df = get_forward_pe_scan(
            top_n=top_n,
            max_fwd_pe=float(max_fwd_pe),
            min_eps_growth=float(min_eps_growth),
        )

    if df.empty:
        st.warning(
            f"No stocks found with Forward P/E ≤ {max_fwd_pe} "
            f"and EPS Growth ≥ {min_eps_growth}%. "
            "Try relaxing the filters, or run the cache build script first: "
            "`python cache/scripts/build_forward_pe_cache.py`"
        )
        return

    st.success(f"✅ Found **{len(df)}** value-growth candidates")

    # ── Summary metrics ───────────────────────────────────────────────────────
    peg_lt1    = int((df["PEG"].dropna() < 1).sum())
    avg_fpe    = df["Fwd P/E"].mean()
    avg_growth = df["EPS Gr %"].dropna().mean()
    avg_score  = df["VG Score"].mean()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Candidates",     len(df))
    m2.metric("Avg Fwd P/E",    f"{avg_fpe:.1f}")
    m3.metric("Avg EPS Growth", f"{avg_growth:.1f}%" if not math.isnan(avg_growth) else "—")
    m4.metric("PEG < 1",        peg_lt1)
    m5.metric("Avg VG Score",   f"{avg_score:.1f}")

    st.markdown("---")

    # ── Score formula explainer ───────────────────────────────────────────────
    with st.expander("📐 How the Value Growth Score is calculated", expanded=False):
        st.markdown("""
        | Component | Formula | Max |
        |---|---|---|
        | P/E Discount to Sector | `(sector_median_pe − stock_pe) / sector_median_pe × 40` — deeper discount = higher score | 40 |
        | EPS Growth | `min(EPS Growth %, 60) × 0.5` — higher expected earnings = higher score | 30 |
        | PEG Bonus | +20 if PEG < 1 (growth at bargain) · +10 if PEG < 2 | 20 |
        | RSI Entry | +5 if RSI < 50 (momentum dip) · −5 if RSI > 70 (overbought) | ±5 |

        **Total max ≈ 95.** Score > 50 = attractive value-growth setup. Score > 70 = high conviction.

        **PEG ratio:** Forward P/E ÷ EPS Growth Rate. PEG < 1 means you're paying less than 1× growth — historically a strong value signal.
        """)

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown("#### Candidates — sorted by Value Growth Score ↓")
    display_cols = [
        "Ticker", "Company", "Sector", "Price",
        "Fwd P/E", "Sector Med P/E", "Trail P/E",
        "Fwd EPS", "EPS Gr %", "Rev Gr %", "PEG", "RSI", "VG Score",
    ]
    st.dataframe(
        _style_table(df[display_cols]),
        width="stretch", hide_index=True,
        height=(len(df) + 1) * 35 + 4,
    )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Forward P/E vs Sector Median")
        st.caption("Bar = stock P/E · Line = sector median · Lower bar = cheaper")
        st.plotly_chart(forward_pe_bar(df), width="stretch")

    with col2:
        st.markdown("#### Forward P/E vs EPS Growth")
        st.caption("Bottom-right quadrant = cheap + fast-growing (ideal)")
        st.plotly_chart(forward_pe_scatter(df), width="stretch")

    st.markdown("---")
    st.markdown("#### Sector Distribution")
    st.plotly_chart(forward_pe_sector_bar(df), width="stretch")


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row(row):
        styles = [""] * len(row)
        cols   = list(df.columns)

        fpe_i = cols.index("Fwd P/E")
        med_i = cols.index("Sector Med P/E")
        if row["Fwd P/E"] and row["Sector Med P/E"]:
            discount = (row["Sector Med P/E"] - row["Fwd P/E"]) / row["Sector Med P/E"]
            if discount >= 0.20:
                styles[fpe_i] = f"color:{UP};font-weight:700"
            elif discount >= 0.05:
                styles[fpe_i] = "color:#86EFAC;font-weight:600"
            elif discount < 0:
                styles[fpe_i] = "color:#F59E0B"

        if "EPS Gr %" in cols and row["EPS Gr %"] is not None:
            eg_i = cols.index("EPS Gr %")
            if row["EPS Gr %"] >= 20:
                styles[eg_i] = f"color:{UP};font-weight:700"
            elif row["EPS Gr %"] >= 10:
                styles[eg_i] = "color:#86EFAC"
            elif row["EPS Gr %"] < 0:
                styles[eg_i] = f"color:{DN}"

        if "PEG" in cols and row["PEG"] is not None:
            peg_i = cols.index("PEG")
            if row["PEG"] < 1:
                styles[peg_i] = "color:#FACC15;font-weight:700"
            elif row["PEG"] < 2:
                styles[peg_i] = f"color:{UP}"

        if "RSI" in cols and row["RSI"] is not None:
            rsi_i = cols.index("RSI")
            if row["RSI"] >= 70:
                styles[rsi_i] = f"color:{DN};font-weight:700"
            elif row["RSI"] <= 40:
                styles[rsi_i] = f"color:{UP};font-weight:600"

        vg_i = cols.index("VG Score")
        if row["VG Score"] >= 70:
            styles[vg_i] = "color:#FACC15;font-weight:700"
        elif row["VG Score"] >= 50:
            styles[vg_i] = f"color:{UP};font-weight:600"

        return styles

    fmt = {
        "Price":          "${:.2f}",
        "Fwd P/E":        "{:.1f}",
        "Sector Med P/E": "{:.1f}",
        "Trail P/E":      "{:.1f}",
        "Fwd EPS":        "${:.2f}",
        "EPS Gr %":       "{:+.1f}%",
        "Rev Gr %":       "{:+.1f}%",
        "PEG":            "{:.2f}",
        "RSI":            "{:.1f}",
        "VG Score":       "{:.1f}",
    }
    return df.style.apply(_row, axis=1).format(fmt, na_rep="—")


def _render_legend() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**What is Forward P/E?**\n\n"
            "Forward P/E = current price ÷ next-12-months earnings estimate. "
            "A low forward P/E relative to peers suggests the market is pricing in "
            "less growth than analysts project — a potential mispricing.\n\n"
            "- 🟢 **Fwd P/E ≥ 20% below sector median** — deep value signal\n"
            "- 🟡 **PEG < 1** — paying less than 1× growth rate (classic value-growth)\n"
            "- 🔴 **Fwd P/E above sector median** — trading at a premium\n\n"
            "Data refreshed weekly from analyst estimates. "
            "Run `cache/scripts/build_forward_pe_cache.py` to update."
        )
    with col2:
        st.markdown("**What to look for:**")
        st.markdown("""
        | Signal | Meaning |
        |---|---|
        | Fwd P/E below sector median | Potentially undervalued vs peers |
        | EPS Growth ≥ 15% | Strong earnings momentum |
        | PEG < 1 | Growth available at a bargain |
        | RSI < 50 | Price pulled back — better entry |
        | VG Score ≥ 70 | 🟡 High-conviction value-growth setup |
        """)
    st.markdown("Adjust filters and click **Scan** to find candidates.")


render_forward_pe_tab()
