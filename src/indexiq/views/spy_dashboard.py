import urllib.parse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from indexiq.data import fetch_index_snapshot, fetch_spx_intraday, fetch_spx_quote, fetch_vix_history, fetch_vix_ohlc
from indexiq.models.indicators import compute_daily_gaps, compute_rsi, patch_today_gap
from indexiq.views.ai_forecast import render_ai_forecast
from indexiq.views.components.gap_table import render_gap_table
from indexiq.views.components.summary_card import render_spy_summary_card


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
    render_spy_summary_card(quote, price, chg, chg_pct, daily_df)

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
    spy_period_keys = list(period_map)
    _spy_qp = st.query_params.get("period", "1Y")
    spy_default_idx = spy_period_keys.index(_spy_qp) if _spy_qp in spy_period_keys else 5

    period_col, rsi_col = st.columns([6, 1])
    with period_col:
        choice = st.radio("Period", spy_period_keys, horizontal=True, key="spy_period", index=spy_default_idx)
    show_rsi = rsi_col.checkbox("RSI", value=True)
    st.query_params["period"] = choice

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
        _render_spy_gap_table(daily_df, quote)

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
    """Current VIX level card + dual-axis SPY vs VIX chart with period selection."""
    vix_periods = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
    vix_period_map = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "2Y": "2y", "5Y": "5y"}

    vix_df = fetch_vix_history(period="1y")
    if vix_df.empty or "VIX" not in vix_df.columns:
        st.info("VIX data unavailable.")
        return

    vix_now  = float(vix_df["VIX"].iloc[-1])
    vix_prev = float(vix_df["VIX"].iloc[-2]) if len(vix_df) > 1 else vix_now
    vix_chg  = vix_now - vix_prev
    vix_52hi = float(vix_df["VIX"].max())
    vix_52lo = float(vix_df["VIX"].min())
    vix_avg  = float(vix_df["VIX"].mean())

    if vix_now < 15:
        zone, zone_clr, zone_bg = "😌 Complacent", "#22C55E", "rgba(34,197,94,0.08)"
    elif vix_now < 20:
        zone, zone_clr, zone_bg = "😐 Normal",      "#86EFAC", "rgba(134,239,172,0.08)"
    elif vix_now < 30:
        zone, zone_clr, zone_bg = "😨 Elevated",    "#F59E0B", "rgba(245,158,11,0.08)"
    else:
        zone, zone_clr, zone_bg = "🔥 Extreme Fear", "#EF4444", "rgba(239,68,68,0.08)"

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

    _vix_qp = st.query_params.get("vix_period", "1Y")
    vix_default_idx = vix_periods.index(_vix_qp) if _vix_qp in vix_periods else 3

    vix_choice = st.radio(
        "Period", vix_periods, horizontal=True, key="vix_period", index=vix_default_idx
    )
    st.query_params["vix_period"] = vix_choice
    yf_vix_period = vix_period_map[vix_choice]
    vix_chart_df = fetch_vix_history(period=yf_vix_period)

    if vix_chart_df.empty or "VIX" not in vix_chart_df.columns:
        st.info("VIX chart data unavailable for this period.")
    else:
        st.plotly_chart(_spy_vix_chart(vix_chart_df), width="stretch")

    st.markdown("---")

    # VIX gap table — no RSI, no $ prefix (VIX is not a dollar price)
    vix_ohlc = fetch_vix_ohlc(period=yf_vix_period)
    if not vix_ohlc.empty:
        vix_gaps = compute_daily_gaps(vix_ohlc)
        render_gap_table(
            vix_gaps,
            title="VIX Daily Gaps (Last 30 Days)",
            price_prefix="",
        )


def _spy_vix_chart(df) -> go.Figure:
    """Dual-axis chart: SPY price (left axis) + VIX with MAs (right axis)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # ── Compute tight y-axis ranges from actual data ───────────────────────────
    spy_min, spy_max = df["SPY"].min(), df["SPY"].max()
    vix_min, vix_max = df["VIX"].min(), df["VIX"].max()
    spy_pad = (spy_max - spy_min) * 0.05
    vix_pad = (vix_max - vix_min) * 0.12
    spy_range = [spy_min - spy_pad, spy_max + spy_pad]
    vix_range = [max(0, vix_min - vix_pad), vix_max + vix_pad]

    # ── SPY line ──────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SPY"],
        name="SPY",
        mode="lines",
        line=dict(color="#3B82F6", width=2),
        hovertemplate="SPY: <b>%{y:,.2f}</b><extra></extra>",
    ), secondary_y=False)

    # ── VIX fill floor (to data min, not 0) ───────────────────────────────────
    vix_floor = vix_range[0]
    fig.add_trace(go.Scatter(
        x=df.index, y=[vix_floor] * len(df),
        mode="lines", line=dict(width=0), showlegend=False,
        hoverinfo="skip",
    ), secondary_y=True)

    # ── VIX line ──────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df.index, y=df["VIX"],
        name="VIX",
        mode="lines",
        line=dict(color="#F59E0B", width=1.5),
        fill="tonexty",
        fillcolor="rgba(245,158,11,0.10)",
        hovertemplate="VIX: <b>%{y:.2f}</b><extra></extra>",
    ), secondary_y=True)

    # ── VIX Moving Averages ───────────────────────────────────────────────────
    ma_colors = {5: "#A78BFA", 20: "#34D399", 50: "#3B82F6", 100: "#F87171"}
    for period, color in ma_colors.items():
        if len(df) >= period:
            ma = df["VIX"].rolling(period).mean()
            fig.add_trace(go.Scatter(
                x=df.index, y=ma,
                name=f"VIX MA{period}",
                mode="lines",
                line=dict(color=color, width=1.2, dash="dot"),
                hovertemplate=f"MA{period}: <b>%{{y:.2f}}</b><extra></extra>",
            ), secondary_y=True)

    # ── VIX zone reference lines ───────────────────────────────────────────────
    for level, color, label in [
        (15, "#22C55E", "VIX 15 — complacent"),
        (20, "#F59E0B", "VIX 20 — caution"),
        (30, "#EF4444", "VIX 30 — fear"),
    ]:
        if vix_range[0] <= level <= vix_range[1]:
            fig.add_hline(
                y=level, secondary_y=True,
                line_dash="dot", line_color=color, line_width=1,
                annotation_text=label,
                annotation_font_size=9,
                annotation_position="top right",
            )

    fig.update_layout(
        template="plotly_dark",
        height=380,
        margin=dict(l=60, r=80, t=20, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0),
        xaxis=dict(showgrid=False),
    )
    fig.update_yaxes(
        title_text="SPY Price", secondary_y=False,
        gridcolor="#1E293B", range=spy_range,
    )
    fig.update_yaxes(
        title_text="VIX", secondary_y=True,
        gridcolor="rgba(0,0,0,0)", showgrid=False, range=vix_range,
    )
    return fig


def _render_spy_gap_table(daily_df: pd.DataFrame, quote: dict) -> None:
    gaps_df = patch_today_gap(compute_daily_gaps(daily_df), quote)
    gaps_df = gaps_df.copy()

    # Next-day price direction
    gaps_df["Next Close"] = gaps_df["Close"].shift(-1)
    gaps_df["Next Day"] = gaps_df.apply(
        lambda r: "▲" if (pd.notna(r["Next Close"]) and r["Next Close"] > r["Close"])
                  else ("▼" if (pd.notna(r["Next Close"]) and r["Next Close"] < r["Close"])
                  else "—"),
        axis=1,
    )

    rsi_dedup = compute_rsi(daily_df)[~daily_df.index.duplicated(keep="last")]
    gaps_df["RSI"] = rsi_dedup.reindex(gaps_df.index)

    try:
        parsed    = urllib.parse.urlparse(st.context.url)
        share_url = f"{parsed.scheme}://{parsed.netloc}/spy-gaps"
    except Exception:
        share_url = "/spy-gaps"

    render_gap_table(
        gaps_df,
        title="Daily Gaps (Last 30 Days)",
        show_rsi=True,
        show_next_day=True,
        share_url=share_url,
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

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        increasing_line_color="#22C55E",
        decreasing_line_color="#EF4444",
        name="SPY",
        showlegend=False,
    ), row=1, col=1)

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

    if prev_close is not None:
        fig.add_hline(
            y=prev_close, row=1, col=1,
            line_dash="dot", line_color="#64748B", line_width=1,
            annotation_text=f"Prev close {prev_close:,.2f}",
            annotation_font_size=9,
            annotation_position="top right",
        )

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
