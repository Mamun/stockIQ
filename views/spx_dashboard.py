import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from data import fetch_index_snapshot, fetch_spx_intraday, fetch_spx_quote
from indicators import compute_daily_gaps


# ── Sidebar ticker (auto-refreshes every 60 s without rerunning the full app) ──

@st.fragment(run_every="60s")
def render_spx_sidebar_ticker() -> None:
    """Compact SPY card for the sidebar. Lives inside ``with st.sidebar:``."""
    quote = fetch_spx_quote()
    if not quote:
        st.caption("SPY: unavailable")
        return

    price   = quote["price"]
    chg     = quote["change"]
    chg_pct = quote["change_pct"]
    up      = chg >= 0
    clr     = "#22C55E" if up else "#EF4444"
    arrow   = "▲" if up else "▼"
    bg      = "rgba(34,197,94,0.08)" if up else "rgba(239,68,68,0.08)"
    border  = "#22C55E55" if up else "#EF444455"

    hi = f"{quote['day_high']:,.0f}" if quote["day_high"] else "—"
    lo = f"{quote['day_low']:,.0f}"  if quote["day_low"]  else "—"

    st.markdown(
        f"""
<div style="
  background:{bg};border:1px solid {border};border-radius:8px;
  padding:10px 12px;text-align:center;margin-bottom:4px
">
  <div style="font-size:10px;color:#94A3B8;font-weight:600;letter-spacing:.06em">
    SPY &nbsp;·&nbsp; LIVE
  </div>
  <div style="font-size:24px;font-weight:800;color:#F1F5F9;line-height:1.2;margin:2px 0">
    {price:,.2f}
  </div>
  <div style="font-size:13px;font-weight:700;color:{clr}">
    {arrow}&nbsp;{abs(chg):.2f}&nbsp;({chg_pct:+.2f}%)
  </div>
  <div style="font-size:10px;color:#64748B;margin-top:4px">
    H&nbsp;{hi}&nbsp;&nbsp;·&nbsp;&nbsp;L&nbsp;{lo}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ── Main dashboard tab ─────────────────────────────────────────────────────────

def render_spx_dashboard_tab() -> None:
    st.title("📈 SPY — Live Dashboard")
    st.caption("Prices refresh every 60 s via Yahoo Finance · Intraday data may lag ~15 min")

    quote = fetch_spx_quote()
    if not quote:
        st.error("Could not load SPY data. Please try again in a moment.")
        return

    # ── Top metrics ───────────────────────────────────────────────────────────
    price   = quote["price"]
    chg     = quote["change"]
    chg_pct = quote["change_pct"]

    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("SPY",       f"{price:,.2f}",  f"{chg:+.2f}")
    m2.metric("Day %",     f"{chg_pct:+.2f}%")
    m3.metric("Day High",  f"{quote['day_high']:,.2f}"  if quote["day_high"] else "—")
    m4.metric("Day Low",   f"{quote['day_low']:,.2f}"   if quote["day_low"]  else "—")
    m5.metric("52W High",  f"{quote['w52_high']:,.2f}"  if quote["w52_high"] else "—")
    m6.metric("52W Low",   f"{quote['w52_low']:,.2f}"   if quote["w52_low"]  else "—")
    vol = quote["volume"]
    m7.metric("Volume",    f"{vol/1_000_000:.1f}M"      if vol else "—")

    st.markdown("---")

    # ── Related indices ───────────────────────────────────────────────────────
    st.markdown("#### Major Indices")
    idx_df = fetch_index_snapshot()
    _render_index_strip(idx_df)

    st.markdown("---")

    # ── Intraday chart ────────────────────────────────────────────────────────
    st.markdown("#### Intraday Chart")
    period_choice = st.radio(
        "Period",
        ["Today (5 min)", "5 Days (30 min)", "1 Month (1 hr)"],
        horizontal=True,
        key="spx_intraday_period",
    )
    period_map = {
        "Today (5 min)":    ("1d",  "5m"),
        "5 Days (30 min)":  ("5d",  "30m"),
        "1 Month (1 hr)":   ("1mo", "1h"),
    }
    period, interval = period_map[period_choice]

    intra_df = fetch_spx_intraday(period=period, interval=interval)
    if intra_df.empty:
        st.info("Intraday data unavailable — the market may be closed or data is delayed.")
    else:
        st.plotly_chart(
            _intraday_chart(intra_df, quote["prev_close"]),
            width='stretch',
        )

    st.markdown("---")

    # ── Daily chart (1 year with MA overlays) ─────────────────────────────────
    st.markdown("#### Daily Chart — 1 Year  ·  MA20 / MA50 / MA200")
    daily_df = fetch_spx_intraday(period="1y", interval="1d")
    if daily_df.empty:
        st.info("Daily data unavailable.")
    else:
        st.plotly_chart(_daily_chart(daily_df), width='stretch')

        st.markdown("---")
        st.markdown("#### Technical Summary")
        _render_technical_summary(daily_df, price)

        st.markdown("---")
        _render_spy_gap_table(daily_df)


# ── Private helpers ────────────────────────────────────────────────────────────

def _render_spy_gap_table(daily_df) -> None:
    st.markdown("#### Daily Gaps (Last 30 Days)")
    gaps_df   = compute_daily_gaps(daily_df)
    gaps_data = gaps_df.tail(30)[["Open", "Prev Close", "Gap", "Gap %", "Gap Filled"]].reset_index()
    gaps_data.columns = ["Date", "Open", "Prev Close", "Gap $", "Gap %", "Filled"]
    gaps_data["Date"] = gaps_data["Date"].dt.strftime("%m-%d")
    gaps_data = gaps_data.sort_values("Date", ascending=False).reset_index(drop=True)
    gaps_data["Status"] = gaps_data.apply(
        lambda r: "—" if r["Gap $"] == 0 else ("✅ Filled" if r["Filled"] else "❌ Open"),
        axis=1,
    )
    display = gaps_data[["Date", "Open", "Prev Close", "Gap $", "Gap %", "Status"]]

    def _highlight(row):
        gap    = gaps_data.loc[row.name, "Gap $"]
        filled = gaps_data.loc[row.name, "Filled"]
        if gap == 0 or bool(filled):
            return [""] * len(row)
        style = "background-color: rgba(239,68,68,0.25); color:#EF4444; font-weight:600"
        return [style] * len(row)

    st.dataframe(
        display.style.apply(_highlight, axis=1).format(
            {"Open": "${:.2f}", "Prev Close": "${:.2f}", "Gap $": "${:.2f}", "Gap %": "{:+.2f}%"},
            na_rep="—",
        ),
        width="stretch", hide_index=True, height=600,
    )


def _render_index_strip(df) -> None:
    if df.empty:
        st.caption("Index data unavailable.")
        return
    cols = st.columns(len(df))
    for col, (_, row) in zip(cols, df.iterrows()):
        is_vix  = row["Index"] == "VIX"
        price_s = f"{row['Price']:.2f}" if is_vix else f"{row['Price']:,.2f}"
        delta_s = f"{row['Change']:+.2f} ({row['Change %']:+.2f}%)"
        # VIX rising = bad → invert delta colour
        col.metric(
            label=row["Index"],
            value=price_s,
            delta=delta_s,
            delta_color="inverse" if is_vix else "normal",
        )


def _intraday_chart(df, prev_close: float) -> go.Figure:
    """Filled area chart coloured by whether price is above/below prev close."""
    last  = float(df["Close"].iloc[-1])
    up    = last >= prev_close
    lclr  = "#22C55E" if up else "#EF4444"
    fclr  = "rgba(34,197,94,0.10)" if up else "rgba(239,68,68,0.10)"

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["Close"],
        mode="lines",
        line=dict(color=lclr, width=2),
        fill="tozeroy",
        fillcolor=fclr,
        name="SPY",
        hovertemplate="%{x|%b %d %H:%M}<br><b>%{y:,.2f}</b><extra></extra>",
    ))

    # Previous close reference
    fig.add_hline(
        y=prev_close,
        line_dash="dot",
        line_color="#64748B",
        line_width=1,
        annotation_text=f"Prev close {prev_close:,.2f}",
        annotation_font_size=9,
        annotation_position="top right",
    )

    # Current price label at right edge
    fig.add_annotation(
        x=df.index[-1], y=last,
        text=f"  {last:,.2f}",
        showarrow=False,
        font=dict(color=lclr, size=12),
        xanchor="left",
    )

    fig.update_layout(
        template="plotly_dark",
        height=340,
        margin=dict(l=60, r=100, t=20, b=40),
        xaxis=dict(showgrid=False, title=""),
        yaxis=dict(title="SPY", gridcolor="#1E293B"),
        showlegend=False,
        hovermode="x unified",
    )
    return fig


def _daily_chart(df) -> go.Figure:
    """Candlestick + MA20/50/200 + volume sub-panel."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
    )

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        increasing_line_color="#22C55E",
        decreasing_line_color="#EF4444",
        name="SPY",
        showlegend=False,
    ), row=1, col=1)

    # MA overlays
    ma_cfg = [(20, "#F59E0B", "MA20"), (50, "#3B82F6", "MA50"), (200, "#EF4444", "MA200")]
    for period, color, label in ma_cfg:
        if len(df) >= period:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df["Close"].rolling(period).mean(),
                mode="lines",
                line=dict(color=color, width=1.5),
                name=label,
            ), row=1, col=1)

    # Volume bars (coloured by direction)
    bar_colors = [
        "#22C55E" if c >= o else "#EF4444"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(go.Bar(
        x=df.index,
        y=df["Volume"],
        marker_color=bar_colors,
        opacity=0.5,
        name="Volume",
        showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=460,
        margin=dict(l=60, r=60, t=10, b=40),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.04, x=0),
        yaxis=dict(title="Price", gridcolor="#1E293B"),
        yaxis2=dict(title="Volume", gridcolor="#1E293B"),
        hovermode="x unified",
    )
    return fig


def _render_technical_summary(df, current_price: float) -> None:
    """RSI, trend (MA cross), distance from MA200, and key MA levels."""
    # RSI-14
    delta    = df["Close"].diff()
    avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi      = float((100 - 100 / (1 + rs)).iloc[-1])

    # Moving averages
    ma20  = float(df["Close"].rolling(20).mean().iloc[-1])  if len(df) >= 20  else None
    ma50  = float(df["Close"].rolling(50).mean().iloc[-1])  if len(df) >= 50  else None
    ma200 = float(df["Close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

    c1, c2, c3, c4 = st.columns(4)

    # RSI
    rsi_label = "🔴 Overbought" if rsi >= 70 else "🟢 Oversold" if rsi <= 30 else "⚪ Neutral"
    c1.metric("RSI (14)", f"{rsi:.1f}", rsi_label, delta_color="off")

    # Trend cross
    if ma50 and ma200:
        cross = "📈 Golden Cross" if ma50 > ma200 else "📉 Death Cross"
        trend = "Uptrend" if ma50 > ma200 else "Downtrend"
        c2.metric("MA50 vs MA200", trend, cross, delta_color="off")

    # Distance from MA200
    if ma200:
        dist = (current_price - ma200) / ma200 * 100
        zone = "Above" if dist > 0 else "Below"
        c3.metric("Distance from MA200", f"{dist:+.2f}%", zone, delta_color="off")

    # Key MA levels
    if ma20 and ma50:
        c4.metric("MA20", f"{ma20:,.2f}", f"MA50: {ma50:,.2f}", delta_color="off")
