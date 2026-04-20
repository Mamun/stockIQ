import urllib.parse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from stockiq.backend.services.spy_dashboard_service import (
    get_market_overview,
    get_put_call_ratio,
    get_spy_chart_df,
    get_spy_gap_table_data,
    get_spy_options_analysis,
    get_spy_quote,
    get_vix_chart_df,
    get_vix_gap_history,
    get_vix_ohlc_df,
)
from stockiq.frontend.views.ai_forecast import render_ai_forecast
from stockiq.frontend.views.components.gap_table import render_gap_table
from stockiq.frontend.views.components.summary_card import render_spy_summary_card

_VIX_ZONE_COLORS = {
    "Calm":         ("#22C55E", "rgba(34,197,94,0.10)"),
    "Normal":       ("#86EFAC", "rgba(134,239,172,0.10)"),
    "Elevated":     ("#F59E0B", "rgba(245,158,11,0.10)"),
    "Extreme Fear": ("#EF4444", "rgba(239,68,68,0.10)"),
}


# ── Main dashboard tab ─────────────────────────────────────────────────────────

def render_spy_dashboard_tab() -> None:
    quote = get_spy_quote()
    if not quote:
        st.error("Could not load SPY data. Please try again in a moment.")
        return
    overview = get_market_overview()
    gap_data = get_spy_gap_table_data()

    # ── 1. Compact page header + index strip ─────────────────────────────────
    _render_header(quote, overview["indices"])

    # ── 2. SPY snapshot + signal cells (RSI · VIX · P/C · MAs) ─────────────
    _rsi, _pc = None, None
    try:
        _daily = get_spy_chart_df(period="1y", interval="1d")
        if not _daily.empty and "RSI" in _daily.columns:
            _rsi_s = _daily["RSI"].dropna()
            if not _rsi_s.empty:
                _rsi = float(_rsi_s.iloc[-1])
    except Exception:
        pass
    try:
        _pc = get_put_call_ratio(scope="daily")
    except Exception:
        pass

    render_spy_summary_card(
        quote, quote["price"], quote["change"], quote["change_pct"],
        gap_data["daily_df"],
        rsi=_rsi,
        vix_snapshot=overview["vix"],
        pc_data=_pc,
    )

    st.divider()

    # ── 4. SPY chart (VWAP intraday · options levels daily) ──────────────────
    _render_spy_chart_section(quote)

    st.divider()

    # ── 5. Options Intelligence — Max Pain · OI · P/C (moved up) ─────────────
    _render_options_section(quote["price"])

    st.divider()

    # ── 6. AI Forecast slot ───────────────────────────────────────────────────
    ai_slot = st.empty()

    st.divider()

    # ── 7. SPY gap table ──────────────────────────────────────────────────────
    _render_spy_gap_table(gap_data)

    st.divider()

    # ── 8. Fear Gauge — VIX ───────────────────────────────────────────────────
    _render_vix_section(overview["vix"])

    # ── Fill AI slot last ─────────────────────────────────────────────────────
    try:
        with ai_slot.container():
            render_ai_forecast(gap_data["gaps_df"], gap_data["quote"])
    except Exception:
        pass


# ── Private helpers ────────────────────────────────────────────────────────────

def _render_header(quote: dict, idx_df: pd.DataFrame) -> None:
    """Compact page header: SPY price badge left, index strip right."""
    price   = quote["price"]
    chg     = quote["change"]
    chg_pct = quote["change_pct"]
    clr     = "#22C55E" if chg >= 0 else "#EF4444"
    arrow   = "▲" if chg >= 0 else "▼"

    title_col, indices_col = st.columns([1, 3])

    with title_col:
        st.markdown(
            f"""
<div style="padding:0 0 6px 0">
  <div style="font-size:10px;color:#64748B;font-weight:600;letter-spacing:.08em;
              text-transform:uppercase">S&P 500 ETF · Live</div>
  <div style="font-size:32px;font-weight:900;color:#F1F5F9;line-height:1.1;
              letter-spacing:-.5px">SPY</div>
  <div style="font-size:22px;font-weight:700;color:{clr};line-height:1.2">
    {price:,.2f}
    <span style="font-size:13px;font-weight:500">
      &nbsp;{arrow} {abs(chg):.2f} ({chg_pct:+.2f}%)
    </span>
  </div>
  <div style="font-size:10px;color:#475569;margin-top:4px">
    Refreshes every 60 s · ~15 min delayed
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    with indices_col:
        if not idx_df.empty:
            cols = st.columns(len(idx_df))
            for col, (_, row) in zip(cols, idx_df.iterrows()):
                is_vix  = row["Index"] == "VIX"
                price_s = f"{row['Price']:.2f}" if is_vix else f"{row['Price']:,.2f}"
                delta_s = f"{row['Change']:+.2f} ({row['Change %']:+.2f}%)"
                col.metric(
                    label=row["Index"],
                    value=price_s,
                    delta=delta_s,
                    delta_color="inverse" if is_vix else "normal",
                )


def _render_spy_chart_section(quote: dict) -> None:
    """SPY candlestick: VWAP on Today view, options levels (max pain + walls) on daily views."""
    period_map = {
        "Today": ("1d",  "5m",  [],            True),
        "5D":    ("5d",  "30m", [],            True),
        "1M":    ("1mo", "1d",  [20],          False),
        "3M":    ("3mo", "1d",  [20, 50],      False),
        "6M":    ("6mo", "1d",  [20, 50, 200], False),
        "1Y":    ("1y",  "1d",  [20, 50, 200], False),
    }
    spy_period_keys = list(period_map)
    _spy_qp = st.query_params.get("period", "1Y")
    spy_default_idx = spy_period_keys.index(_spy_qp) if _spy_qp in spy_period_keys else 5

    period_col, rsi_col = st.columns([6, 1])
    with period_col:
        choice = st.radio("Period", spy_period_keys, horizontal=True,
                          key="spy_period", index=spy_default_idx)
    show_rsi = rsi_col.checkbox("RSI", value=True)
    st.query_params["period"] = choice

    yf_period, interval, mas, show_prev = period_map[choice]
    chart_df = get_spy_chart_df(period=yf_period, interval=interval)
    if chart_df.empty:
        st.info("Chart data unavailable — the market may be closed or data is delayed.")
        return

    prev = quote["prev_close"] if show_prev else None

    # VWAP for Today intraday view only
    vwap = None
    if choice == "Today" and "Volume" in chart_df.columns and not chart_df["Volume"].isna().all():
        tp   = (chart_df["High"] + chart_df["Low"] + chart_df["Close"]) / 3
        cumvol = chart_df["Volume"].cumsum()
        vwap   = (tp * chart_df["Volume"]).cumsum() / cumvol.replace(0, float("nan"))

    # Max pain + call/put walls for daily+ views (cached options fetch)
    max_pain = call_wall = put_wall = None
    if not show_prev:
        try:
            seed = get_spy_options_analysis(expiration="", current_price=quote["price"])
            if seed:
                max_pain = seed["max_pain"]
                oi_df    = seed["oi_df"]
                if not oi_df.empty:
                    call_wall = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"])
                    put_wall  = float(oi_df.loc[oi_df["put_oi"].idxmax(), "strike"])
        except Exception:
            pass

    st.plotly_chart(
        _spy_chart(chart_df, mas, prev, show_rsi=show_rsi,
                   vwap=vwap, max_pain=max_pain,
                   call_wall=call_wall, put_wall=put_wall),
        width="stretch",
    )


def _render_spy_gap_table(gap_data: dict) -> None:
    gaps_df = gap_data["gaps_df"]
    try:
        parsed    = urllib.parse.urlparse(st.context.url)
        share_url = f"{parsed.scheme}://{parsed.netloc}/spy-gaps"
    except Exception:
        share_url = "/spy-gaps"

    render_gap_table(gaps_df, title="Daily Gaps (Last 30 Days)",
                     show_rsi=True, show_next_day=True, share_url=share_url)


def _render_vix_section(vix_snapshot: dict) -> None:
    """VIX zone card + 52w stats + dual-axis chart + gap table."""
    if not vix_snapshot:
        st.info("VIX data unavailable.")
        return

    vix_periods    = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
    vix_period_map = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "2Y": "2y", "5Y": "5y"}

    vix_now  = vix_snapshot["current"]
    vix_chg  = vix_snapshot["change"]
    vix_52hi = vix_snapshot["high_52w"]
    vix_52lo = vix_snapshot["low_52w"]
    vix_avg  = vix_snapshot["avg"]
    zone     = vix_snapshot["zone"]
    zone_clr, zone_bg = _VIX_ZONE_COLORS.get(zone, ("#94A3B8", "rgba(148,163,184,0.10)"))

    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;'
        'letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">'
        'Fear Gauge — VIX</div>',
        unsafe_allow_html=True,
    )

    col_vix, col_stats = st.columns([1, 2])

    with col_vix:
        chg_arrow = "▲" if vix_chg >= 0 else "▼"
        st.markdown(
            f"""
<div style="background:{zone_bg};border:1px solid {zone_clr}55;border-radius:10px;
            padding:16px;height:100%;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase">VIX · CBOE</div>
  <div style="font-size:38px;font-weight:900;color:#F1F5F9;line-height:1;margin:6px 0 4px">
    {vix_now:.2f}
  </div>
  <div style="font-size:13px;font-weight:700;color:{zone_clr}">{zone}</div>
  <div style="font-size:11px;color:#64748B;margin-top:6px">
    {chg_arrow}&nbsp;{abs(vix_chg):.2f} vs prev close
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    with col_stats:
        s1, s2 = st.columns(2)
        s1.metric("1Y High",   f"{vix_52hi:.2f}", help="Highest VIX close in the past year")
        s1.metric("1Y Avg",    f"{vix_avg:.2f}",  help="Average VIX close over the past year")
        s2.metric("1Y Low",    f"{vix_52lo:.2f}", help="Lowest VIX close in the past year")
        s2.metric("vs 1Y Avg", f"{vix_now - vix_avg:+.2f}",
                  delta_color="inverse",
                  help="Positive = more fearful than average")
        st.markdown(
            '<div style="font-size:10px;color:#475569;margin-top:6px;line-height:1.6">'
            '&lt;15 😌 Calm &nbsp;·&nbsp; 15–20 😐 Normal &nbsp;·&nbsp;'
            '20–30 😨 Elevated &nbsp;·&nbsp; &gt;30 🔥 Extreme Fear'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)

    _vix_qp = st.query_params.get("vix_period", "1Y")
    vix_default_idx = vix_periods.index(_vix_qp) if _vix_qp in vix_periods else 3

    vix_choice = st.radio("Period ", vix_periods, horizontal=True,
                          key="vix_period", index=vix_default_idx)
    st.query_params["vix_period"] = vix_choice
    yf_vix_period = vix_period_map[vix_choice]
    vix_chart_df  = get_vix_chart_df(period=yf_vix_period)

    if not vix_chart_df.empty and "VIX" in vix_chart_df.columns:
        st.plotly_chart(_spy_vix_chart(vix_chart_df), width="stretch")

    vix_gaps = get_vix_gap_history(period=yf_vix_period)
    if not vix_gaps.empty:
        render_gap_table(vix_gaps, title="", price_prefix="")


def _spy_vix_chart(df) -> go.Figure:
    """Dual-axis chart: SPY price (left axis) + VIX with MAs (right axis)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    spy_min, spy_max = df["SPY"].min(), df["SPY"].max()
    vix_min, vix_max = df["VIX"].min(), df["VIX"].max()
    spy_pad = (spy_max - spy_min) * 0.05
    vix_pad = (vix_max - vix_min) * 0.12
    spy_range = [spy_min - spy_pad, spy_max + spy_pad]
    vix_range = [max(0, vix_min - vix_pad), vix_max + vix_pad]

    fig.add_trace(go.Scatter(
        x=df.index, y=df["SPY"],
        name="SPY", mode="lines",
        line=dict(color="#3B82F6", width=2),
        hovertemplate="SPY: <b>%{y:,.2f}</b><extra></extra>",
    ), secondary_y=False)

    vix_floor = vix_range[0]
    fig.add_trace(go.Scatter(
        x=df.index, y=[vix_floor] * len(df),
        mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ), secondary_y=True)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["VIX"],
        name="VIX", mode="lines",
        line=dict(color="#F59E0B", width=1.5),
        fill="tonexty", fillcolor="rgba(245,158,11,0.10)",
        hovertemplate="VIX: <b>%{y:.2f}</b><extra></extra>",
    ), secondary_y=True)

    ma_colors = {5: "#A78BFA", 20: "#34D399", 50: "#3B82F6", 100: "#F87171"}
    for period, color in ma_colors.items():
        if len(df) >= period:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["VIX"].rolling(period).mean(),
                name=f"VIX MA{period}", mode="lines",
                line=dict(color=color, width=1.2, dash="dot"),
                hovertemplate=f"MA{period}: <b>%{{y:.2f}}</b><extra></extra>",
            ), secondary_y=True)

    for level, color, label in [
        (15, "#22C55E", "15"), (20, "#F59E0B", "20"), (30, "#EF4444", "30"),
    ]:
        if vix_range[0] <= level <= vix_range[1]:
            fig.add_hline(
                y=level, secondary_y=True,
                line_dash="dot", line_color=color, line_width=1,
                annotation_text=label, annotation_font_size=9,
                annotation_position="top right",
            )

    fig.update_layout(
        template="plotly_dark", height=360,
        margin=dict(l=60, r=80, t=20, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0),
        xaxis=dict(showgrid=False),
    )
    fig.update_yaxes(title_text="SPY", secondary_y=False,
                     gridcolor="#1E293B", range=spy_range)
    fig.update_yaxes(title_text="VIX", secondary_y=True,
                     gridcolor="rgba(0,0,0,0)", showgrid=False, range=vix_range)
    return fig


def _spy_chart(
    df,
    ma_periods: list,
    prev_close: float | None = None,
    show_rsi: bool = False,
    vwap: pd.Series | None = None,
    max_pain: float | None = None,
    call_wall: float | None = None,
    put_wall: float | None = None,
) -> go.Figure:
    """Candlestick + volume + optional RSI + VWAP + options levels."""
    if show_rsi:
        rows, row_heights = 3, [0.55, 0.2, 0.25]
        vol_row, rsi_row  = 2, 3
    else:
        rows, row_heights = 2, [0.75, 0.25]
        vol_row, rsi_row  = 2, None

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        row_heights=row_heights, vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing_line_color="#22C55E", decreasing_line_color="#EF4444",
        name="SPY", showlegend=False,
    ), row=1, col=1)

    ma_colors = {20: "#F59E0B", 50: "#3B82F6", 200: "#EF4444"}
    for p in ma_periods:
        if len(df) >= p:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"].rolling(p).mean(),
                mode="lines", line=dict(color=ma_colors[p], width=1.5),
                name=f"MA{p}",
            ), row=1, col=1)

    if vwap is not None:
        fig.add_trace(go.Scatter(
            x=df.index, y=vwap,
            name="VWAP", mode="lines",
            line=dict(color="#E879F9", width=1.5, dash="dash"),
            hovertemplate="VWAP: <b>%{y:,.2f}</b><extra></extra>",
        ), row=1, col=1)

    if prev_close is not None:
        fig.add_hline(y=prev_close, row=1, col=1,
                      line_dash="dot", line_color="#64748B", line_width=1,
                      annotation_text=f"Prev {prev_close:,.2f}",
                      annotation_font_size=9, annotation_position="top right")

    if max_pain is not None:
        fig.add_hline(y=max_pain, row=1, col=1,
                      line_dash="dot", line_color="#F59E0B", line_width=1.2,
                      annotation_text=f"Max Pain {max_pain:,.0f}",
                      annotation_font_size=9, annotation_position="top left")

    if call_wall is not None:
        fig.add_hline(y=call_wall, row=1, col=1,
                      line_dash="dash", line_color="#22C55E", line_width=1,
                      annotation_text=f"Call Wall {call_wall:,.0f}",
                      annotation_font_size=9, annotation_position="top right")

    if put_wall is not None:
        fig.add_hline(y=put_wall, row=1, col=1,
                      line_dash="dash", line_color="#EF4444", line_width=1,
                      annotation_text=f"Put Wall {put_wall:,.0f}",
                      annotation_font_size=9, annotation_position="bottom right")

    if "Volume" in df.columns:
        bar_colors = ["#22C55E" if c >= o else "#EF4444"
                      for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=bar_colors, opacity=0.5,
            name="Volume", showlegend=False,
        ), row=vol_row, col=1)

    if show_rsi and rsi_row and "RSI" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI"], name="RSI (14)",
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


def _render_options_section(current_price: float) -> None:
    """Options Intelligence: P/C ratio · Max Pain · OI butterfly."""
    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;'
        'letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">'
        'Options Intelligence — Max Pain · Open Interest · Put/Call</div>',
        unsafe_allow_html=True,
    )

    _scope_opts  = ["Daily", "7 Days", "14 Days", "21 Days", "Monthly"]
    _scope_keys  = {
        "Daily":   "daily",
        "7 Days":  "7d",
        "14 Days": "14d",
        "21 Days": "21d",
        "Monthly": "monthly",
    }
    _scope_notes = {
        "Daily":   "Today's option volume · 4 nearest expirations · resets each trading day",
        "7 Days":  "Open interest · expirations within 7 days",
        "14 Days": "Open interest · expirations within 14 days",
        "21 Days": "Open interest · expirations within 21 days",
        "Monthly": "Open interest · expirations ≤ 30 days out",
    }
    _, pc_scope_col = st.columns([2, 1])
    with pc_scope_col:
        pc_scope = st.radio("P/C Scope", _scope_opts, horizontal=True, key="pc_scope", index=0)
    pc = get_put_call_ratio(scope=_scope_keys[pc_scope])

    # Seed call — nearest expiration + full list
    seed = get_spy_options_analysis(expiration="", current_price=current_price)
    if not seed:
        st.info(
            "⚠️ Options data unavailable. Yahoo Finance blocks options chain requests "
            "from cloud/server IPs. This section works when running the app locally.",
            icon=None,
        )
        return

    exp_map = dict(zip(seed["exp_labels"], seed["expirations"]))
    exp_col, _ = st.columns([2, 3])
    with exp_col:
        selected_label = st.selectbox(
            "Expiration",
            options=list(exp_map.keys()),
            index=0,
            key="options_exp",
        )
    selected_iso = exp_map[selected_label]

    data = get_spy_options_analysis(expiration=selected_iso, current_price=current_price)
    if not data:
        st.caption("Options data unavailable for this expiration.")
        return

    max_pain = data["max_pain"]
    oi_df    = data["oi_df"]
    dist_pct = (current_price - max_pain) / max_pain * 100 if max_pain else 0

    if abs(dist_pct) <= 0.5:
        mp_color, mp_signal = "#22C55E", "Pinned near max pain — low movement expected"
    elif abs(dist_pct) <= 2.0:
        mp_color, mp_signal = "#86EFAC", "Close to max pain — mild gravitational pull"
    elif abs(dist_pct) <= 4.0:
        mp_color, mp_signal = "#F59E0B", "Drifting from max pain — watch for reversion"
    else:
        mp_color, mp_signal = "#EF4444", "Far from max pain — strong directional move"

    dist_arrow = "▲" if dist_pct >= 0 else "▼"

    # ── Cards row: P/C | Max Pain | OI chart ─────────────────────────────────
    pc_col, mp_col, chart_col = st.columns([1, 1, 3])

    with pc_col:
        if pc:
            exp_range = (
                f"{pc['exp_nearest']} → {pc['exp_farthest']}"
                if pc["exp_nearest"] != pc["exp_farthest"]
                else pc["exp_nearest"]
            )
            st.markdown(
                f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;height:100%;box-sizing:border-box">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
    <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
                text-transform:uppercase">Put / Call</div>
    <div style="font-size:10px;font-weight:700;color:#1E293B;background:{pc['color']};
                border-radius:4px;padding:1px 6px;line-height:1.6">
      {pc['scope_label']}
    </div>
  </div>
  <div style="font-size:38px;font-weight:900;color:{pc['color']};line-height:1;
              margin:4px 0">{pc['ratio']:.3f}</div>
  <div style="font-size:12px;font-weight:700;color:{pc['color']};margin-bottom:6px">
    {pc['signal']}
  </div>
  <div style="font-size:10px;color:#64748B;line-height:1.7">
    {pc['puts']:,} puts &nbsp;·&nbsp; {pc['calls']:,} calls<br>
    {pc['exp_count']} exp &nbsp;·&nbsp; {exp_range}
  </div>
  <div style="font-size:9px;color:#334155;margin-top:6px;line-height:1.5">
    {_scope_notes[pc_scope]}
  </div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="padding:16px;font-size:11px;color:#64748B;line-height:1.6">'
                'P/C ratio unavailable.<br>Yahoo Finance options data is blocked on cloud servers.'
                '</div>',
                unsafe_allow_html=True,
            )

    with mp_col:
        st.markdown(
            f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;height:100%;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:4px">Max Pain · {selected_label}</div>
  <div style="font-size:36px;font-weight:900;color:{mp_color};line-height:1;
              margin:4px 0">${max_pain:,.0f}</div>
  <div style="font-size:11px;color:#64748B;margin-top:6px;line-height:1.6">
    Current&nbsp;<b style="color:#F1F5F9">${current_price:,.2f}</b><br>
    {dist_arrow}&nbsp;<b style="color:{mp_color}">{abs(dist_pct):.1f}%</b> from max pain
  </div>
  <div style="font-size:10px;color:{mp_color};margin-top:8px;line-height:1.5">
    {mp_signal}
  </div>
  <div style="font-size:9px;color:#334155;margin-top:8px;line-height:1.5">
    Strike where all open contracts expire with maximum loss.
    Price tends to gravitate toward it into expiry.
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    with chart_col:
        if not oi_df.empty:
            st.plotly_chart(
                _oi_butterfly_chart(oi_df, current_price, max_pain),
                width="stretch",
            )
        else:
            st.caption("No OI data for this expiration.")


def _oi_butterfly_chart(
    oi_df: pd.DataFrame,
    current_price: float,
    max_pain: float,
) -> go.Figure:
    """Horizontal butterfly: put OI left (red), call OI right (green)."""
    strikes = oi_df["strike"].values
    call_oi = oi_df["call_oi"].values.astype(float)
    put_oi  = oi_df["put_oi"].values.astype(float)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=strikes, x=-put_oi, orientation="h",
        name="Put OI", marker_color="rgba(239,68,68,0.75)",
        hovertemplate="Strike %{y}<br>Put OI: %{customdata:,}<extra></extra>",
        customdata=put_oi,
    ))
    fig.add_trace(go.Bar(
        y=strikes, x=call_oi, orientation="h",
        name="Call OI", marker_color="rgba(34,197,94,0.75)",
        hovertemplate="Strike %{y}<br>Call OI: %{x:,}<extra></extra>",
    ))

    y_min, y_max = float(strikes.min()), float(strikes.max())

    fig.add_shape(
        type="line", xref="paper", yref="y",
        x0=0, x1=1, y0=current_price, y1=current_price,
        line=dict(color="#3B82F6", width=1.5, dash="solid"),
    )
    fig.add_annotation(
        xref="paper", yref="y", x=1.01, y=current_price,
        text=f"<b>${current_price:,.0f}</b>", showarrow=False,
        font=dict(color="#3B82F6", size=10), xanchor="left",
    )

    if y_min <= max_pain <= y_max:
        fig.add_shape(
            type="line", xref="paper", yref="y",
            x0=0, x1=1, y0=max_pain, y1=max_pain,
            line=dict(color="#F59E0B", width=1.5, dash="dot"),
        )
        fig.add_annotation(
            xref="paper", yref="y", x=1.01, y=max_pain,
            text=f"Pain ${max_pain:,.0f}", showarrow=False,
            font=dict(color="#F59E0B", size=10), xanchor="left",
        )

    x_max     = max(call_oi.max(), put_oi.max()) * 1.1 if len(call_oi) else 1
    tick_step = max(1, int(x_max / 5))

    fig.update_layout(
        template="plotly_dark", height=420, barmode="overlay",
        margin=dict(l=60, r=100, t=10, b=40),
        xaxis=dict(
            range=[-x_max, x_max],
            tickvals=[-4*tick_step, -2*tick_step, 0, 2*tick_step, 4*tick_step],
            ticktext=[f"{4*tick_step:,}", f"{2*tick_step:,}", "0",
                      f"{2*tick_step:,}", f"{4*tick_step:,}"],
            title="Open Interest",
            gridcolor="#1E293B",
        ),
        yaxis=dict(title="Strike", gridcolor="#1E293B", dtick=5),
        legend=dict(orientation="h", y=1.04, x=0),
        hovermode="y unified",
    )
    return fig


render_spy_dashboard_tab()
