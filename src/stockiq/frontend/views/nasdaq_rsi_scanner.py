import streamlit as st

from stockiq.backend.services.scanners import get_nasdaq_rsi_scan

_COMPANY = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon",
    "META": "Meta Platforms", "GOOGL": "Alphabet A", "GOOG": "Alphabet C",
    "TSLA": "Tesla", "AVGO": "Broadcom", "COST": "Costco", "NFLX": "Netflix",
    "AMD": "Advanced Micro Devices", "ADBE": "Adobe", "QCOM": "Qualcomm",
    "TXN": "Texas Instruments", "CSCO": "Cisco", "INTU": "Intuit",
    "AMGN": "Amgen", "ISRG": "Intuitive Surgical", "CMCSA": "Comcast",
    "REGN": "Regeneron", "VRTX": "Vertex Pharma", "MDLZ": "Mondelez",
    "GILD": "Gilead Sciences", "MU": "Micron Technology", "LRCX": "Lam Research",
    "KLAC": "KLA Corp", "AMAT": "Applied Materials", "PANW": "Palo Alto Networks",
    "SNPS": "Synopsys", "CDNS": "Cadence Design", "ADI": "Analog Devices",
    "MRVL": "Marvell Technology", "ASML": "ASML Holding", "MELI": "MercadoLibre",
    "ADP": "Automatic Data Processing", "PYPL": "PayPal", "WDAY": "Workday",
    "DDOG": "Datadog", "CRWD": "CrowdStrike", "ZS": "Zscaler", "FTNT": "Fortinet",
    "MNST": "Monster Beverage", "ROST": "Ross Stores", "AEP": "American Electric Power",
    "IDXX": "IDEXX Laboratories", "PCAR": "PACCAR", "EXC": "Exelon",
    "GEHC": "GE HealthCare", "ODFL": "Old Dominion Freight", "FAST": "Fastenal",
    "VRSK": "Verisk Analytics", "CTSH": "Cognizant", "DLTR": "Dollar Tree",
    "EA": "Electronic Arts", "ALGN": "Align Technology", "ANSS": "ANSYS",
    "TEAM": "Atlassian", "NXPI": "NXP Semiconductors", "PAYX": "Paychex",
    "CHTR": "Charter Communications", "CPRT": "Copart", "CTAS": "Cintas",
    "LULU": "Lululemon", "BKNG": "Booking Holdings", "KHC": "Kraft Heinz",
    "CEG": "Constellation Energy", "DXCM": "Dexcom", "MRNA": "Moderna",
    "TTD": "The Trade Desk", "NDAQ": "Nasdaq Inc", "INTC": "Intel",
    "SBUX": "Starbucks", "MAR": "Marriott", "ORLY": "O'Reilly Auto",
    "KDP": "Keurig Dr Pepper", "FANG": "Diamondback Energy", "ON": "ON Semiconductor",
    "BIIB": "Biogen", "OKTA": "Okta", "WBD": "Warner Bros Discovery",
    "ABNB": "Airbnb", "ENPH": "Enphase Energy", "FSLR": "First Solar",
    "TTWO": "Take-Two Interactive", "EBAY": "eBay", "ILMN": "Illumina",
    "ZM": "Zoom Video", "FISV": "Fiserv", "SMCI": "Super Micro Computer",
    "HON": "Honeywell", "PDD": "PDD Holdings", "JD": "JD.com",
    "SIRI": "Sirius XM", "MTCH": "Match Group", "GFS": "GlobalFoundries",
    "RIVN": "Rivian", "LCID": "Lucid Group", "MSTR": "MicroStrategy", "ARM": "Arm Holdings",
}

_STATUS_OPTIONS = ["All", "🟢 Oversold (RSI ≤ 30)", "🔴 Overbought (RSI ≥ 70)", "⚪ Neutral"]


def render_nasdaq_rsi_tab() -> None:
    st.title("📊 NASDAQ-100 RSI Scanner")
    st.markdown(
        "Scans all **NASDAQ-100** stocks using a single batch download. "
        "Shows RSI, MA50, MA200, and status for every stock. "
        "Filter by Oversold, Overbought, or Neutral — or view the full list."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([3, 2, 1])
    status_filter = c1.select_slider(
        "Status filter",
        options=_STATUS_OPTIONS,
        value="All",
        help="Filter by RSI signal: Oversold (RSI ≤ 30), Overbought (RSI ≥ 70), Neutral, or show all.",
    )
    top_n = c2.slider(
        "Max results",
        min_value=10, max_value=100, value=100, step=10,
    )
    scan_btn = c3.button("🔍 Scan", use_container_width=True, type="primary")

    if not scan_btn:
        _render_legend()
        return

    with st.spinner("Fetching NASDAQ-100 data (batch download)…"):
        df = get_nasdaq_rsi_scan()

    if df.empty:
        st.warning("Could not fetch NASDAQ-100 data. Please try again in a moment.")
        return

    # ── Add company names ─────────────────────────────────────────────────────
    df.insert(1, "Company", df["Ticker"].map(_COMPANY).fillna("—"))

    # ── Apply status filter ───────────────────────────────────────────────────
    if status_filter == "🟢 Oversold (RSI ≤ 30)":
        filtered = df[df["Status"] == "🟢 Oversold"].sort_values("RSI", ascending=True)
        sort_label = "sorted by RSI ↑ (most oversold first)"
    elif status_filter == "🔴 Overbought (RSI ≥ 70)":
        filtered = df[df["Status"] == "🔴 Overbought"].sort_values("RSI", ascending=False)
        sort_label = "sorted by RSI ↓ (most overbought first)"
    elif status_filter == "⚪ Neutral":
        filtered = df[df["Status"] == "⚪ Neutral"].sort_values("RSI", ascending=True)
        sort_label = "sorted by RSI ↑"
    else:
        filtered = df.sort_values("RSI", ascending=False)
        sort_label = "overbought → neutral → oversold"

    filtered = filtered.head(top_n).reset_index(drop=True)

    # ── Summary metrics ───────────────────────────────────────────────────────
    total      = len(df)
    oversold   = int((df["Status"] == "🟢 Oversold").sum())
    overbought = int((df["Status"] == "🔴 Overbought").sum())
    neutral    = int((df["Status"] == "⚪ Neutral").sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total stocks",  total)
    m2.metric("🟢 Oversold",   oversold,   help="RSI ≤ 30")
    m3.metric("🔴 Overbought", overbought, help="RSI ≥ 70")
    m4.metric("⚪ Neutral",    neutral,    help="30 < RSI < 70")

    # ── Results table ─────────────────────────────────────────────────────────
    label = status_filter if status_filter != "All" else "All NASDAQ-100"
    st.markdown(f"#### {len(filtered)} stocks — {label} — {sort_label}")
    st.caption(
        "RSI-14 · % vs MA50/MA200 = distance of price from moving average · "
        "Vol Ratio = today's volume ÷ 20-day avg volume (>1.5 = elevated activity)"
    )

    row_height = 36
    table_height = (len(filtered) + 1) * row_height + 4
    st.dataframe(
        _style_table(filtered),
        hide_index=True,
        use_container_width=True,
        height=table_height,
    )

    st.caption("Data sourced from Yahoo Finance · Cached 30 min")


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_table(df):
    def _row(row):
        styles = [""] * len(row)
        cols = list(df.columns)

        def _idx(col):
            return cols.index(col) if col in cols else None

        # RSI colouring
        rsi = row.get("RSI")
        if rsi is not None and (i := _idx("RSI")) is not None:
            if rsi <= 20:
                styles[i] = "color:#22C55E;font-weight:800"    # extreme oversold
            elif rsi <= 30:
                styles[i] = "color:#4ADE80;font-weight:700"    # strongly oversold
            elif rsi >= 80:
                styles[i] = "color:#EF4444;font-weight:800"    # extreme overbought
            elif rsi >= 70:
                styles[i] = "color:#F97316;font-weight:700"    # overbought

        # Day change colouring
        chg = row.get("Day Chg %")
        if chg is not None and (i := _idx("Day Chg %")) is not None:
            if chg <= -3:
                styles[i] = "color:#EF4444;font-weight:700"
            elif chg < 0:
                styles[i] = "color:#F97316"
            elif chg >= 3:
                styles[i] = "color:#22C55E;font-weight:700"
            elif chg > 0:
                styles[i] = "color:#4ADE80"

        # % vs MA50 — green = above, red = below
        pma50 = row.get("% vs MA50")
        if pma50 is not None and (i := _idx("% vs MA50")) is not None:
            if pma50 <= -10:
                styles[i] = "color:#22C55E;font-weight:700"   # deep below MA50 → oversold signal
            elif pma50 < 0:
                styles[i] = "color:#4ADE80"
            elif pma50 >= 10:
                styles[i] = "color:#EF4444;font-weight:700"   # far above MA50 → stretched
            else:
                styles[i] = "color:#F97316"

        # % vs MA200
        pma200 = row.get("% vs MA200")
        if pma200 is not None and (i := _idx("% vs MA200")) is not None:
            if pma200 <= -15:
                styles[i] = "color:#22C55E;font-weight:700"
            elif pma200 < 0:
                styles[i] = "color:#4ADE80"
            elif pma200 >= 15:
                styles[i] = "color:#EF4444;font-weight:700"
            else:
                styles[i] = "color:#F97316"

        # Trend colouring
        trend = row.get("Trend", "")
        if (i := _idx("Trend")) is not None:
            if "Uptrend" in str(trend):
                styles[i] = "color:#22C55E"
            elif "Downtrend" in str(trend):
                styles[i] = "color:#EF4444"

        # Vol Ratio — highlight elevated volume
        vol = row.get("Vol Ratio")
        if vol is not None and (i := _idx("Vol Ratio")) is not None:
            if vol >= 2.0:
                styles[i] = "color:#F1C40F;font-weight:700"   # very high volume
            elif vol >= 1.5:
                styles[i] = "color:#F59E0B"                   # elevated volume

        # Status colouring
        status = row.get("Status", "")
        if (i := _idx("Status")) is not None:
            if "Oversold" in str(status):
                styles[i] = "color:#22C55E;font-weight:700"
            elif "Overbought" in str(status):
                styles[i] = "color:#EF4444;font-weight:700"
            else:
                styles[i] = "color:#94A3B8"

        return styles

    def _signed(v):
        if v is None:
            return "—"
        return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"

    def _signed1(v):
        if v is None:
            return "—"
        return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"

    fmt = {
        "Price":      lambda v: f"${v:.2f}" if v is not None else "—",
        "Day Chg %":  _signed,
        "RSI":        lambda v: f"{v:.1f}" if v is not None else "—",
        "% vs MA50":  _signed1,
        "% vs MA200": _signed1,
        "Vol Ratio":  lambda v: f"{v:.2f}x" if v is not None else "—",
    }
    return df.style.apply(_row, axis=1).format(fmt)


def _render_legend() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**How this scanner works**\n\n"
            "Downloads all NASDAQ-100 price data in a **single batch call**.\n\n"
            "1. Fetches 300 days of OHLCV for all 100 stocks at once\n"
            "2. Computes RSI-14, MA50, MA200, trend, day change, and volume ratio\n"
            "3. Labels each stock: Oversold / Overbought / Neutral\n"
            "4. Filter by status or view the full NASDAQ-100 list"
        )
    with col2:
        st.markdown("**Column guide:**")
        st.markdown("""
        | Column | What it tells you |
        |---|---|
        | **Day Chg %** | Today's price move — momentum signal |
        | **RSI** | Relative Strength Index (14-day) |
        | **% vs MA50** | How far price is from 50-day avg |
        | **% vs MA200** | How far price is from 200-day avg |
        | **Trend** | MA50 vs MA200 — 📈 up / 📉 down |
        | **Vol Ratio** | Today's volume ÷ 20-day avg (>1.5 = elevated) |
        """)
    st.markdown("Select a filter and click **Scan** to start.")


render_nasdaq_rsi_tab()
