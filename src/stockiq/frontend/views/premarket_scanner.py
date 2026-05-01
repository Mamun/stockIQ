"""
Pre-Market Scanner — NASDAQ-100
Shows today's pre-market movers alongside a 7-day daily close heatmap.
"""
import pandas as pd
import streamlit as st

from stockiq.backend.services.scanners import get_premarket_scan


def _market_session() -> tuple[str, str]:
    """Return (label, description) for the current ET market session."""
    now = pd.Timestamp.now(tz="America/New_York")
    h, m = now.hour, now.minute
    mins = h * 60 + m
    wd = now.dayofweek  # 0=Mon, 6=Sun

    if wd >= 5:
        return "🗓️ Weekend", "Markets closed. Showing last available data."
    if mins < 4 * 60:
        return "🌙 Pre-Pre-Market", f"Premarket opens at 4:00 AM ET (in {4*60 - mins} min)."
    if mins < 9 * 60 + 30:
        return "🟡 Pre-Market Live", "Premarket session active until 9:30 AM ET."
    if mins < 16 * 60:
        return "🟢 Market Open", "Regular session. Pre-market data is from this morning."
    if mins < 20 * 60:
        return "🔵 After Hours", "After-hours session. Pre-market data is from this morning."
    return "🌙 Closed", "Market closed. Pre-market data is from this morning."


def render_premarket_tab() -> None:
    st.title("🌅 Pre-Market Scanner")

    session_label, session_desc = _market_session()
    st.markdown(
        f"**{session_label}** — {session_desc}  \n"
        "Scans all **NASDAQ-100** stocks for pre-market price moves vs the previous close. "
        "Data refreshes every 5 minutes. Scroll down for the 7-day close heatmap."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    min_chg = c1.slider(
        "Min |PM Chg %|",
        min_value=0.0, max_value=10.0, value=0.0, step=0.5,
        help="Show only stocks whose premarket move exceeds this threshold.",
    )
    direction = c2.selectbox(
        "Direction",
        ["All movers", "🟢 Gainers only", "🔴 Losers only"],
    )
    pm_only = c3.checkbox("Only stocks with PM data", value=True)
    scan_btn = c4.button("🔍 Scan", use_container_width=True, type="primary")

    if not scan_btn:
        _render_legend()
        return

    # ── Fetch data ────────────────────────────────────────────────────────────
    with st.spinner("Fetching pre-market data…"):
        data = get_premarket_scan()
        df   = data["scan"]
        hist = data["history"]

    if df.empty:
        st.warning("Could not fetch data. Please try again in a moment.")
        return

    # ── Apply filters ─────────────────────────────────────────────────────────
    if pm_only:
        df = df[df["PM Chg %"].notna()]
    if min_chg > 0:
        df = df[df["PM Chg %"].abs() >= min_chg]
    if direction == "🟢 Gainers only":
        df = df[df["PM Chg %"] > 0]
    elif direction == "🔴 Losers only":
        df = df[df["PM Chg %"] < 0]

    df = df.reset_index(drop=True)

    if df.empty:
        st.warning("No stocks match the current filters. Try loosening the thresholds.")
        return

    # ── Merge 7-day close history ─────────────────────────────────────────────
    date_cols: list[str] = []
    if not hist.empty:
        df = df.merge(hist.reset_index(), on="Ticker", how="left")
        _movers_cols = {"Ticker", "Company", "PM Price", "PM Chg %", "PM Vol %", "Prev Close", "7D Chg %"}
        date_cols = [c for c in df.columns if c not in _movers_cols]

    # ── Summary metrics ───────────────────────────────────────────────────────
    has_pm   = df["PM Chg %"].notna()
    gainers  = int((df["PM Chg %"] > 0).sum())
    losers   = int((df["PM Chg %"] < 0).sum())
    biggest  = df.loc[df["PM Chg %"].abs().idxmax(), "PM Chg %"] if has_pm.any() else None
    bk_tick  = df.loc[df["PM Chg %"].abs().idxmax(), "Ticker"]   if has_pm.any() else "—"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Stocks shown",  len(df))
    m2.metric("🟢 PM Gainers", gainers)
    m3.metric("🔴 PM Losers",  losers)
    if biggest is not None:
        sign = "+" if biggest >= 0 else ""
        m4.metric("Biggest mover", f"{bk_tick}  {sign}{biggest:.2f}%")
    else:
        m4.metric("Biggest mover", "—")

    # ── Combined table ────────────────────────────────────────────────────────
    st.caption(
        "PM Price = latest premarket price · "
        "PM Vol % = premarket volume as % of avg daily volume · "
        "7D Chg % = 7 trading-day change · "
        "Date columns = daily close (🟢 up / 🔴 down vs prior day)"
    )

    row_h = 36
    st.dataframe(
        _style_combined(df, date_cols),
        hide_index=True,
        use_container_width=True,
        height=(len(df) + 1) * row_h + 4,
    )
    st.caption("Data from Yahoo Finance · Pre-market: 4:00–9:30 AM ET · Cached 5 min")


# ── Private helpers ────────────────────────────────────────────────────────────

def _style_combined(df: pd.DataFrame, date_cols: list[str]):
    """Single styler for the merged premarket + 7-day history table."""

    def _all_cells(data: pd.DataFrame) -> pd.DataFrame:
        styles = pd.DataFrame("", index=data.index, columns=data.columns)

        for idx in data.index:
            # ── PM Chg % ──────────────────────────────────────────────────────
            if "PM Chg %" in data.columns:
                v = data.at[idx, "PM Chg %"]
                if pd.notna(v):
                    if v <= -5:
                        s = "color:#EF4444;font-weight:800"
                    elif v < -2:
                        s = "color:#F97316;font-weight:700"
                    elif v < 0:
                        s = "color:#F97316"
                    elif v >= 5:
                        s = "color:#22C55E;font-weight:800"
                    elif v >= 2:
                        s = "color:#22C55E;font-weight:700"
                    else:
                        s = "color:#4ADE80"
                    styles.at[idx, "PM Chg %"] = s

            # ── PM Vol % ──────────────────────────────────────────────────────
            if "PM Vol %" in data.columns:
                v = data.at[idx, "PM Vol %"]
                if pd.notna(v):
                    if v >= 15:
                        styles.at[idx, "PM Vol %"] = "color:#F1C40F;font-weight:700"
                    elif v >= 8:
                        styles.at[idx, "PM Vol %"] = "color:#F59E0B"

            # ── 7D Chg % ──────────────────────────────────────────────────────
            if "7D Chg %" in data.columns:
                v = data.at[idx, "7D Chg %"]
                if pd.notna(v):
                    if v < -10:
                        s = "color:#EF4444;font-weight:700"
                    elif v < 0:
                        s = "color:#F97316"
                    elif v >= 10:
                        s = "color:#22C55E;font-weight:700"
                    else:
                        s = "color:#4ADE80"
                    styles.at[idx, "7D Chg %"] = s

            # ── Date columns: green/red vs prior day ─────────────────────────
            for i, col in enumerate(date_cols):
                if i == 0:
                    continue
                prev_col = date_cols[i - 1]
                curr = data.at[idx, col]
                prev = data.at[idx, prev_col]
                if pd.notna(curr) and pd.notna(prev):
                    if curr > prev:
                        styles.at[idx, col] = "color:#22C55E"
                    elif curr < prev:
                        styles.at[idx, col] = "color:#EF4444"

        return styles

    def _pct(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"

    fmt: dict = {
        "PM Price":   lambda v: f"${v:.2f}" if pd.notna(v) else "—",
        "PM Chg %":   _pct,
        "PM Vol %":   lambda v: f"{v:.1f}%" if pd.notna(v) else "—",
        "Prev Close": lambda v: f"${v:.2f}" if pd.notna(v) else "—",
        "7D Chg %":   _pct,
        **{col: lambda v: f"${v:.2f}" if pd.notna(v) else "—" for col in date_cols},
    }
    return df.style.apply(_all_cells, axis=None).format(fmt)


def _render_legend() -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.info(
            "**How this scanner works**\n\n"
            "Two batch downloads — no per-ticker API calls:\n\n"
            "1. **5-min bars** (last 2 days, prepost=True) → premarket prices & volume\n"
            "2. **Daily bars** (last 12 days) → prev close + 7-day trend\n\n"
            "Results are cached for 5 minutes. Click **Scan** to get fresh data."
        )
    with c2:
        st.markdown("**Column guide:**")
        st.markdown("""
        | Column | What it tells you |
        |---|---|
        | **PM Price** | Latest premarket price (4:00–9:30 AM ET) |
        | **PM Chg %** | Change vs previous regular close |
        | **PM Vol %** | Premarket volume as % of avg daily vol |
        | **Prev Close** | Last regular session close price |
        | **7D Chg %** | Price change over last 7 trading days |
        """)
        st.markdown(
            "**PM Vol %** example: 12% means 12% of a typical full day's "
            "volume has already traded in pre-market — unusually active."
        )
    st.markdown("Set filters and click **Scan** to start.")


render_premarket_tab()
