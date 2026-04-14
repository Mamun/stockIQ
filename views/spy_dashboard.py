import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from data import fetch_index_snapshot, fetch_spx_intraday, fetch_spx_quote, fetch_vix_history, fetch_vix_ohlc
from indicators import compute_daily_gaps, compute_rsi
from views.ai_forecast import render_ai_forecast


# ── Main dashboard tab ─────────────────────────────────────────────────────────

def render_spy_dashboard_tab() -> None:
    st.title("📈 SPY — Live Dashboard")
    st.caption("Prices refresh every 60 s via Yahoo Finance · Intraday data may lag ~15 min")

    quote = fetch_spx_quote()
    if not quote:
        st.error("Could not load SPY data. Please try again in a moment.")
        return

    # ── 1. Major Indices (top of page) ────────────────────────────────────────
    st.markdown("#### Major Indices")
    idx_df = fetch_index_snapshot()
    _render_index_strip(idx_df)

    st.markdown("---")

    # ── 2. SPY metrics + Technical Summary (before chart) ────────────────────
    price   = quote["price"]
    chg     = quote["change"]
    chg_pct = quote["change_pct"]

    st.markdown("#### SPY Overview")
    daily_df = fetch_spx_intraday(period="1y", interval="1d")
    _render_spy_summary(quote, price, chg, chg_pct, daily_df)

    st.markdown("---")

    # ── 3. SPY Chart ──────────────────────────────────────────────────────────
    period_map = {
        "Today":  ("1d",  "5m",  [],            True),
        "5D":     ("5d",  "30m", [],            True),
        "1M":     ("1mo", "1d",  [20],          False),
        "3M":     ("3mo", "1d",  [20, 50],      False),
        "6M":     ("6mo", "1d",  [20, 50, 200], False),
        "1Y":     ("1y",  "1d",  [20, 50, 200], False),
    }
    period_col, rsi_col = st.columns([6, 1])
    with period_col:
        choice = st.radio("Period", list(period_map), horizontal=True, key="spy_period", index=5)
    show_rsi = rsi_col.checkbox("RSI", value=True)

    yf_period, interval, mas, show_prev = period_map[choice]

    chart_df = fetch_spx_intraday(period=yf_period, interval=interval)
    if chart_df.empty:
        st.info("Chart data unavailable — the market may be closed or data is delayed.")
    else:
        prev = quote["prev_close"] if show_prev else None
        st.plotly_chart(_spy_chart(chart_df, mas, prev, show_rsi=show_rsi), width="stretch")

    st.markdown("---")

    # ── 4. AI Forecast slot ───────────────────────────────────────────────────
    ai_slot = st.empty()

    st.markdown("---")

    # ── 5. Gap table ──────────────────────────────────────────────────────────
    if not daily_df.empty:
        _render_spy_gap_table(daily_df)

    st.markdown("---")

    # ── 6. VIX panel ──────────────────────────────────────────────────────────
    st.markdown("#### VIX — Fear & Greed Gauge")
    _render_vix_section()

    # ── Fill AI Forecast slot last (gap table + VIX already visible) ──────────
    if not daily_df.empty:
        try:
            gaps_df_for_ai = compute_daily_gaps(daily_df).copy()
            rsi_dedup = compute_rsi(daily_df)[~daily_df.index.duplicated(keep="last")]
            gaps_df_for_ai["RSI"] = rsi_dedup.reindex(gaps_df_for_ai.index)
            with ai_slot.container():
                render_ai_forecast(gaps_df_for_ai)
        except Exception:
            pass


# ── Private helpers ────────────────────────────────────────────────────────────

def _render_vix_section() -> None:
    """Current VIX level card + 1-year dual-axis SPY vs VIX chart."""
    vix_df = fetch_vix_history(period="1y")
    if vix_df.empty or "VIX" not in vix_df.columns:
        st.info("VIX data unavailable.")
        return

    vix_now = float(vix_df["VIX"].iloc[-1])
    vix_prev = float(vix_df["VIX"].iloc[-2]) if len(vix_df) > 1 else vix_now
    vix_chg  = vix_now - vix_prev
    vix_52hi = float(vix_df["VIX"].max())
    vix_52lo = float(vix_df["VIX"].min())
    vix_avg  = float(vix_df["VIX"].mean())

    # Zone classification
    if vix_now < 15:
        zone, zone_clr, zone_bg = "😌 Complacent", "#22C55E", "rgba(34,197,94,0.08)"
    elif vix_now < 20:
        zone, zone_clr, zone_bg = "😐 Normal",     "#86EFAC", "rgba(134,239,172,0.08)"
    elif vix_now < 30:
        zone, zone_clr, zone_bg = "😨 Elevated",   "#F59E0B", "rgba(245,158,11,0.08)"
    else:
        zone, zone_clr, zone_bg = "🔥 Extreme Fear","#EF4444", "rgba(239,68,68,0.08)"

    # VIX level card + metrics
    c_card, c_metrics = st.columns([1, 3])
    with c_card:
        st.markdown(
            f"""
<div style="background:{zone_bg};border:1px solid {zone_clr}44;border-radius:8px;
            padding:14px 16px;text-align:center;">
  <div style="font-size:10px;color:#94A3B8;font-weight:600;letter-spacing:.06em">VIX · CBOE</div>
  <div style="font-size:36px;font-weight:800;color:#F1F5F9;line-height:1.1;margin:4px 0">{vix_now:.2f}</div>
  <div style="font-size:13px;font-weight:700;color:{zone_clr}">{zone}</div>
  <div style="font-size:11px;color:#64748B;margin-top:6px">
    {'▲' if vix_chg >= 0 else '▼'}&nbsp;{abs(vix_chg):.2f} vs prev close
  </div>
</div>""",
            unsafe_allow_html=True,
        )
    with c_metrics:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("1Y High",  f"{vix_52hi:.2f}", help="Highest VIX close in the past year")
        m2.metric("1Y Low",   f"{vix_52lo:.2f}", help="Lowest VIX close in the past year")
        m3.metric("1Y Avg",   f"{vix_avg:.2f}",  help="Average VIX close over the past year")
        m4.metric("vs 1Y Avg", f"{vix_now - vix_avg:+.2f}",
                  delta_color="inverse",
                  help="Positive = more fearful than average; negative = calmer than average")

        st.markdown("""
<div style="font-size:11px;color:#64748B;line-height:1.8;margin-top:8px">
&nbsp;VIX &lt; 15 &nbsp;😌&nbsp; Complacent — low fear, market confident
&nbsp;·&nbsp;
15–20 &nbsp;😐&nbsp; Normal range
&nbsp;·&nbsp;
20–30 &nbsp;😨&nbsp; Elevated fear / uncertainty
&nbsp;·&nbsp;
&gt; 30 &nbsp;🔥&nbsp; Extreme fear / crisis
</div>""", unsafe_allow_html=True)

    st.plotly_chart(_spy_vix_chart(vix_df), width="stretch")

    st.markdown("---")
    _render_vix_gap_table()


def _spy_vix_chart(df) -> go.Figure:
    """Dual-axis chart: SPY price (left axis) + VIX (right axis, shaded zones)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # SPY line
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SPY"],
        name="SPY",
        mode="lines",
        line=dict(color="#3B82F6", width=2),
        hovertemplate="SPY: <b>%{y:,.2f}</b><extra></extra>",
    ), secondary_y=False)

    # VIX filled area
    fig.add_trace(go.Scatter(
        x=df.index, y=df["VIX"],
        name="VIX",
        mode="lines",
        line=dict(color="#F59E0B", width=1.5),
        fill="tozeroy",
        fillcolor="rgba(245,158,11,0.08)",
        hovertemplate="VIX: <b>%{y:.2f}</b><extra></extra>",
    ), secondary_y=True)

    # Zone reference lines on VIX axis
    for level, color, label in [
        (15, "#22C55E", "VIX 15 — complacent"),
        (20, "#F59E0B", "VIX 20 — caution"),
        (30, "#EF4444", "VIX 30 — fear"),
    ]:
        fig.add_hline(
            y=level, secondary_y=True,
            line_dash="dot", line_color=color, line_width=1,
            annotation_text=label,
            annotation_font_size=9,
            annotation_position="top right",
        )

    fig.update_layout(
        template="plotly_dark",
        height=360,
        margin=dict(l=60, r=80, t=20, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0),
        xaxis=dict(showgrid=False),
    )
    fig.update_yaxes(title_text="SPY Price", secondary_y=False, gridcolor="#1E293B")
    fig.update_yaxes(title_text="VIX", secondary_y=True, gridcolor="rgba(0,0,0,0)", showgrid=False)
    return fig


def _render_vix_gap_table() -> None:
    st.markdown("#### VIX Daily Gaps (Last 30 Days)")
    vix_ohlc = fetch_vix_ohlc(period="1y")
    if vix_ohlc.empty:
        st.info("VIX OHLC data unavailable.")
        return
    gaps_df = compute_daily_gaps(vix_ohlc)
    gaps_data = gaps_df.tail(30)[["Open", "Prev Close", "Gap", "Gap %", "Gap Filled", "Gap Confirmed"]].reset_index()
    gaps_data.columns = ["Date", "Open", "Prev Close", "Gap $", "Gap %", "Filled", "Gap Confirmed"]
    gaps_data["Date"] = gaps_data["Date"].dt.strftime("%m-%d")
    gaps_data = gaps_data.sort_values("Date", ascending=False).reset_index(drop=True)
    gaps_data["Status"] = gaps_data.apply(
        lambda r: "—" if r["Gap $"] == 0
        else ("✅ Filled" if r["Filled"]
        else ("⏳ Pending" if not r.get("Gap Confirmed", True)
        else "❌ Open")),
        axis=1,
    )
    display = gaps_data[["Date", "Open", "Prev Close", "Gap $", "Gap %", "Status"]]

    def _highlight(row):
        gap    = gaps_data.loc[row.name, "Gap $"]
        filled = gaps_data.loc[row.name, "Filled"]
        if gap == 0 or bool(filled):
            return [""] * len(row)
        if gap > 0:
            style = "background-color: rgba(34,197,94,0.20); color:#22C55E; font-weight:600"
        else:
            style = "background-color: rgba(239,68,68,0.25); color:#EF4444; font-weight:600"
        return [style] * len(row)

    st.dataframe(
        display.style.apply(_highlight, axis=1).format(
            {"Open": "{:.2f}", "Prev Close": "{:.2f}", "Gap $": "{:.2f}", "Gap %": "{:+.2f}%"},
            na_rep="—",
        ),
        width="stretch", hide_index=True, height=600,
    )


def _render_spy_gap_table(daily_df) -> None:
    head_col, btn_col = st.columns([8, 1])
    head_col.markdown("#### Daily Gaps (Last 30 Days)")
    with btn_col:
        st.html("""
        <button onclick="
          var url = (window.parent.location.origin || window.location.ancestorOrigins?.[0] || window.location.origin) + '/spy-gaps';
          navigator.clipboard.writeText(url)
            .then(function() {
              var b = document.getElementById('sb');
              b.innerHTML = '✅ Copied!';
              b.style.color = '#22C55E';
              b.style.borderColor = '#22C55E';
              setTimeout(function() {
                b.innerHTML = '🔗 Share';
                b.style.color = '#94A3B8';
                b.style.borderColor = '#334155';
              }, 2000);
            })
            .catch(function() {
              var b = document.getElementById('sb');
              b.innerHTML = window.location.origin + '/spy-gaps';
            });
        " id="sb" style="
          background:#0F172A;color:#94A3B8;border:1px solid #334155;
          border-radius:6px;padding:5px 10px;cursor:pointer;
          font-size:13px;white-space:nowrap;width:100%;
        ">🔗 Share</button>
        """)
    gaps_df = compute_daily_gaps(daily_df)

    # Next-day price direction: shift Close up by 1 so each row shows tomorrow's close
    gaps_df = gaps_df.copy()
    gaps_df["Next Close"] = gaps_df["Close"].shift(-1)
    gaps_df["Next Day"] = gaps_df.apply(
        lambda r: "▲" if (pd.notna(r["Next Close"]) and r["Next Close"] > r["Close"])
                  else ("▼" if (pd.notna(r["Next Close"]) and r["Next Close"] < r["Close"])
                  else "—"),
        axis=1,
    )

    # Attach RSI — deduplicate index first to prevent row expansion on duplicate dates
    rsi_dedup = compute_rsi(daily_df)[~daily_df.index.duplicated(keep="last")]
    gaps_df["RSI"] = rsi_dedup.reindex(gaps_df.index)

    has_vol = "Volume" in gaps_df.columns
    base_cols = ["Open", "Prev Close", "Gap", "Gap %", "Gap Filled", "Gap Confirmed", "RSI", "Next Day"]
    if has_vol:
        base_cols.insert(2, "Volume")
    gaps_data = gaps_df.tail(30)[base_cols].reset_index()
    if has_vol:
        gaps_data.columns = ["Date", "Open", "Prev Close", "Volume", "Gap $", "Gap %", "Filled", "Gap Confirmed", "RSI", "Next Day"]
    else:
        gaps_data.columns = ["Date", "Open", "Prev Close", "Gap $", "Gap %", "Filled", "Gap Confirmed", "RSI", "Next Day"]
    gaps_data["Date"] = gaps_data["Date"].dt.strftime("%m-%d")
    gaps_data = gaps_data.sort_values("Date", ascending=False).reset_index(drop=True)

    gaps_data["Status"] = gaps_data.apply(
        lambda r: "—" if r["Gap $"] == 0
        else ("✅ Filled" if r["Filled"]
        else ("⏳ Pending" if not r.get("Gap Confirmed", True)
        else "❌ Open")),
        axis=1,
    )

    gaps_data["RSI Zone"] = gaps_data["RSI"].apply(
        lambda v: "—" if pd.isna(v) or v == 0
        else ("Overbought" if v >= 70 else ("Oversold" if v <= 30 else "Neutral"))
    )

    display_cols = (
        ["Date", "Open", "Prev Close"]
        + (["Volume"] if has_vol else [])
        + ["Gap $", "Gap %", "Status", "RSI", "RSI Zone", "Next Day"]
    )
    display = gaps_data[display_cols]

    def _color_next_day(val):
        if val == "▲":
            return "color: #22C55E; font-weight: 700"
        if val == "▼":
            return "color: #EF4444; font-weight: 700"
        return ""

    def _highlight(row):
        gap    = gaps_data.loc[row.name, "Gap $"]
        filled = gaps_data.loc[row.name, "Filled"]
        if gap == 0 or bool(filled):
            return [""] * len(row)
        style = (
            "background-color: rgba(34,197,94,0.20); color:#22C55E; font-weight:600"
            if gap > 0
            else "background-color: rgba(239,68,68,0.25); color:#EF4444; font-weight:600"
        )
        return [style] * len(row)

    def _color_rsi_zone(val):
        if val == "Overbought":
            return "color:#EF4444; font-weight:700"
        if val == "Oversold":
            return "color:#22C55E; font-weight:700"
        if val == "Neutral":
            return "color:#F59E0B"
        return ""

    def _color_rsi(val):
        if pd.isna(val) or val == 0:
            return ""
        if val >= 70:
            return "color:#EF4444; font-weight:700"
        if val <= 30:
            return "color:#22C55E; font-weight:700"
        return "color:#F59E0B"

    fmt = {"Open": "${:.2f}", "Prev Close": "${:.2f}", "Gap $": "${:.2f}", "Gap %": "{:+.2f}%", "RSI": "{:.1f}"}
    if has_vol:
        fmt["Volume"] = lambda x: f"{x/1_000_000:.1f}M" if x and x > 0 else "—"
    st.dataframe(
        display.style
            .apply(_highlight, axis=1)
            .map(_color_next_day, subset=["Next Day"])
            .map(_color_rsi_zone, subset=["RSI Zone"])
            .map(_color_rsi, subset=["RSI"])
            .format(fmt, na_rep="—"),
        width="stretch", hide_index=True, height=600,
    )


def _render_spy_summary(quote, price, chg, chg_pct, daily_df) -> None:
    """Two-row summary card: price data row + technicals row."""
    # ── Compute technicals ────────────────────────────────────────────────────
    rsi_val = ma5 = ma50 = ma100 = ma200 = cross_label = cross_clr = None
    if not daily_df.empty:
        rsi_val = float(compute_rsi(daily_df).iloc[-1])

        def _ma(p):
            return float(daily_df["Close"].rolling(p).mean().iloc[-1]) if len(daily_df) >= p else None

        ma5   = _ma(5)
        ma50  = _ma(50)
        ma100 = _ma(100)
        ma200 = _ma(200)
        if ma50 and ma200:
            cross_label = "🌟 Golden Cross" if ma50 > ma200 else "💀 Death Cross"
            cross_clr   = "#22C55E" if ma50 > ma200 else "#EF4444"

    up_clr  = "#22C55E"
    dn_clr  = "#EF4444"
    neu_clr = "#F59E0B"
    mut_clr = "#64748B"
    val_clr = "#F1F5F9"
    bg      = "#0F172A"
    sep     = "#1E293B"

    def cell(label, value, sub="", sub_clr=None):
        sub_html = (
            f'<div style="font-size:11px;color:{sub_clr or mut_clr};margin-top:2px;white-space:nowrap">{sub}</div>'
            if sub else '<div style="font-size:11px">&nbsp;</div>'
        )
        return (
            f'<div style="padding:10px 18px;border-right:1px solid {sep};'
            f'display:flex;flex-direction:column;justify-content:center">'
            f'<div style="font-size:11px;color:{mut_clr};text-transform:uppercase;'
            f'letter-spacing:.05em;white-space:nowrap">{label}</div>'
            f'<div style="font-size:17px;font-weight:700;color:{val_clr};white-space:nowrap">{value}</div>'
            f'{sub_html}'
            f'</div>'
        )

    def ma_cell(label, val):
        if not val:
            return ""
        diff = (price - val) / val * 100
        clr  = up_clr if diff >= 0 else dn_clr
        return cell(label, f"{val:,.2f}", f"{diff:+.2f}% vs price", clr)

    # ── Row 1: Price data ─────────────────────────────────────────────────────
    chg_clr   = up_clr if chg >= 0 else dn_clr
    arrow     = "▲" if chg >= 0 else "▼"
    vol       = quote.get("volume", 0)
    prev_close = quote.get("prev_close", 0)

    price_row = "".join([
        cell("SPY Price", f"{price:,.2f}", f"{arrow} {abs(chg):.2f} ({chg_pct:+.2f}%)", chg_clr),
        cell("Prev Close", f"{prev_close:,.2f}" if prev_close else "—"),
        cell("Day High",  f"{quote['day_high']:,.2f}" if quote["day_high"] else "—"),
        cell("Day Low",   f"{quote['day_low']:,.2f}"  if quote["day_low"]  else "—"),
        cell("52W High",  f"{quote['w52_high']:,.2f}" if quote["w52_high"] else "—"),
        cell("52W Low",   f"{quote['w52_low']:,.2f}"  if quote["w52_low"]  else "—"),
        cell("Volume",    f"{vol/1_000_000:.1f}M"     if vol else "—"),
    ])

    # ── Row 2: Technicals ─────────────────────────────────────────────────────
    if rsi_val is not None:
        rsi_clr = dn_clr if rsi_val >= 70 else up_clr if rsi_val <= 30 else neu_clr
        rsi_sub = "Overbought" if rsi_val >= 70 else "Oversold" if rsi_val <= 30 else "Neutral"
        rsi_cell = cell("RSI (14)", f"{rsi_val:.1f}", rsi_sub, rsi_clr)
    else:
        rsi_cell = ""

    cross_cell = cell("MA Trend", cross_label, "MA50 vs MA200", cross_clr) if cross_label else ""

    tech_row = "".join([
        rsi_cell,
        cross_cell,
        ma_cell("MA 5",   ma5),
        ma_cell("MA 50",  ma50),
        ma_cell("MA 100", ma100),
        ma_cell("MA 200", ma200),
    ])

    row_style = (
        f'display:flex;flex-wrap:wrap;background:{bg};'
        f'border-bottom:1px solid {sep}'
    )
    st.markdown(
        f'<div style="background:{bg};border:1px solid {sep};border-radius:8px;'
        f'overflow:hidden;margin-bottom:8px">'
        f'<div style="{row_style}">{price_row}</div>'
        f'<div style="{row_style};border-bottom:none">{tech_row}</div>'
        f'</div>',
        unsafe_allow_html=True,
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


def _spy_chart(df, ma_periods: list, prev_close: float | None = None, show_rsi: bool = False) -> go.Figure:
    """Candlestick + volume + optional RSI chart for any period/interval."""
    if show_rsi:
        rows, row_heights = 3, [0.55, 0.2, 0.25]
        vol_row, rsi_row  = 2, 3
    else:
        rows, row_heights = 2, [0.75, 0.25]
        vol_row, rsi_row  = 2, None

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
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
    ma_colors = {20: "#F59E0B", 50: "#3B82F6", 200: "#EF4444"}
    for p in ma_periods:
        if len(df) >= p:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df["Close"].rolling(p).mean(),
                mode="lines",
                line=dict(color=ma_colors[p], width=1.5),
                name=f"MA{p}",
            ), row=1, col=1)

    # Prev close reference line (intraday only)
    if prev_close is not None:
        fig.add_hline(
            y=prev_close, row=1, col=1,
            line_dash="dot", line_color="#64748B", line_width=1,
            annotation_text=f"Prev close {prev_close:,.2f}",
            annotation_font_size=9,
            annotation_position="top right",
        )

    # Volume bars
    if "Volume" in df.columns:
        bar_colors = ["#22C55E" if c >= o else "#EF4444" for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index,
            y=df["Volume"],
            marker_color=bar_colors,
            opacity=0.5,
            name="Volume",
            showlegend=False,
        ), row=vol_row, col=1)

    # RSI subplot
    if show_rsi and rsi_row:
        rsi = compute_rsi(df)
        fig.add_trace(go.Scatter(
            x=df.index, y=rsi,
            name="RSI (14)",
            line=dict(color="#A78BFA", width=1.5),
            hovertemplate="RSI: %{y:.1f}<extra></extra>",
        ), row=rsi_row, col=1)

        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.08)",
                      line_width=0, row=rsi_row, col=1)
        fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(34,197,94,0.08)",
                      line_width=0, row=rsi_row, col=1)

        for level, label, color in [(70, "OB 70", "#EF4444"),
                                     (50, "50",    "#64748B"),
                                     (30, "OS 30", "#22C55E")]:
            fig.add_hline(y=level, line_dash="dot", line_color=color, line_width=1,
                          annotation_text=label, annotation_position="right",
                          annotation_font_size=9, row=rsi_row, col=1)

        fig.update_yaxes(title_text="RSI", range=[0, 100], row=rsi_row, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=460 + (200 if show_rsi else 0),
        margin=dict(l=60, r=80, t=10, b=40),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.04, x=0),
        yaxis=dict(title="Price", gridcolor="#1E293B"),
        yaxis2=dict(title="Volume", gridcolor="#1E293B"),
        hovermode="x unified",
    )
    return fig


render_spy_dashboard_tab()


