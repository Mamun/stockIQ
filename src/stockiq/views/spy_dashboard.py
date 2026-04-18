import urllib.parse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from stockiq.data import fetch_index_snapshot, fetch_put_call_ratio, fetch_spx_intraday, fetch_spx_quote, fetch_vix_history, fetch_vix_ohlc
from stockiq.data.gap_cache import apply_gap_cache, save_confirmed_gaps
from stockiq.data.ohlc_cache import enrich_with_cache
from stockiq.models.indicators import compute_daily_gaps, compute_rsi, patch_today_gap
from stockiq.views.ai_forecast import render_ai_forecast
from stockiq.views.components.gap_table import render_gap_table
from stockiq.views.components.summary_card import render_spy_summary_card


# ── Main dashboard tab ─────────────────────────────────────────────────────────

def render_spy_dashboard_tab() -> None:
    quote = fetch_spx_quote()
    if not quote:
        st.error("Could not load SPY data. Please try again in a moment.")
        return

    # ── 1. Compact page header + index strip ─────────────────────────────────
    _render_header(quote)

    # ── 2. SPY technical snapshot (single row) ────────────────────────────────
    daily_df = enrich_with_cache(fetch_spx_intraday(period="1y", interval="1d"), "SPY")
    render_spy_summary_card(quote, quote["price"], quote["change"], quote["change_pct"], daily_df)

    st.divider()

    # ── 3. SPY chart ──────────────────────────────────────────────────────────
    _render_spy_chart_section(quote)

    st.divider()

    # ── 4. AI Forecast slot ───────────────────────────────────────────────────
    ai_slot = st.empty()

    st.divider()

    # ── 5. SPY gap table ──────────────────────────────────────────────────────
    if not daily_df.empty:
        _render_spy_gap_table(daily_df, quote)

    st.divider()

    # ── 6. VIX + Fear gauges ──────────────────────────────────────────────────
    _render_vix_section()

    # ── Fill AI slot last ─────────────────────────────────────────────────────
    if not daily_df.empty:
        try:
            gaps_df_for_ai = apply_gap_cache(patch_today_gap(compute_daily_gaps(daily_df), quote))
            rsi_dedup = compute_rsi(daily_df)[~daily_df.index.duplicated(keep="last")]
            gaps_df_for_ai["RSI"] = rsi_dedup.reindex(gaps_df_for_ai.index)
            with ai_slot.container():
                render_ai_forecast(gaps_df_for_ai)
        except Exception:
            pass


# ── Private helpers ────────────────────────────────────────────────────────────

def _render_header(quote: dict) -> None:
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
        idx_df = fetch_index_snapshot()
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
    """SPY candlestick chart with period + RSI toggle."""
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
    chart_df = fetch_spx_intraday(period=yf_period, interval=interval)
    if chart_df.empty:
        st.info("Chart data unavailable — the market may be closed or data is delayed.")
    else:
        prev = quote["prev_close"] if show_prev else None
        st.plotly_chart(_spy_chart(chart_df, mas, prev, show_rsi=show_rsi), width="stretch")


def _render_vix_section() -> None:
    """Compact VIX + P/C fear gauge row, then VIX chart, then gap table."""
    vix_periods    = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
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
        zone, zone_clr, zone_bg = "Complacent",  "#22C55E", "rgba(34,197,94,0.10)"
    elif vix_now < 20:
        zone, zone_clr, zone_bg = "Normal",       "#86EFAC", "rgba(134,239,172,0.10)"
    elif vix_now < 30:
        zone, zone_clr, zone_bg = "Elevated",     "#F59E0B", "rgba(245,158,11,0.10)"
    else:
        zone, zone_clr, zone_bg = "Extreme Fear", "#EF4444", "rgba(239,68,68,0.10)"

    # ── Section label ──────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;'
        'letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">'
        'Fear Gauges — VIX &amp; Put/Call Ratio</div>',
        unsafe_allow_html=True,
    )

    # ── Scope selector for P/C ratio ──────────────────────────────────────────
    _scope_opts  = ["Daily", "Monthly", "Quarterly"]
    _scope_keys  = {"Daily": "daily", "Monthly": "monthly", "Quarterly": "quarterly"}
    _scope_notes = {
        "Daily":     "Today's option volume · 4 nearest expirations · resets each trading day",
        "Monthly":   "Open interest · all expirations within 30 days · reflects near-term hedging",
        "Quarterly": "Open interest · all expirations within 90 days · structural positioning",
    }
    _, pc_scope_col = st.columns([2, 1])
    with pc_scope_col:
        pc_scope = st.radio("P/C Scope", _scope_opts, horizontal=True, key="pc_scope", index=0)
    pc = fetch_put_call_ratio(scope=_scope_keys[pc_scope])

    # ── Gauge row: VIX card | P/C card | VIX stats ────────────────────────────
    col_vix, col_pc, col_stats = st.columns([1, 1, 2])

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

    with col_pc:
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
                text-transform:uppercase">Put / Call Ratio</div>
    <div style="font-size:10px;font-weight:700;color:#1E293B;background:{pc['color']};
                border-radius:4px;padding:1px 6px;line-height:1.6">
      {pc['scope_label']}
    </div>
  </div>
  <div style="font-size:38px;font-weight:900;color:{pc['color']};line-height:1;
              margin:4px 0">{pc['ratio']:.3f}</div>
  <div style="font-size:13px;font-weight:700;color:{pc['color']};margin-bottom:6px">
    {pc['signal']}
  </div>
  <div style="font-size:10px;color:#64748B;line-height:1.7">
    {pc['puts']:,} puts &nbsp;·&nbsp; {pc['calls']:,} calls<br>
    {pc['exp_count']} expiration{"s" if pc['exp_count'] != 1 else ""} &nbsp;·&nbsp; {exp_range}
  </div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            st.caption("P/C ratio unavailable")

    with col_stats:
        s1, s2 = st.columns(2)
        s1.metric("1Y High",   f"{vix_52hi:.2f}", help="Highest VIX close in the past year")
        s1.metric("1Y Avg",    f"{vix_avg:.2f}",  help="Average VIX close over the past year")
        s2.metric("1Y Low",    f"{vix_52lo:.2f}", help="Lowest VIX close in the past year")
        s2.metric("vs 1Y Avg", f"{vix_now - vix_avg:+.2f}",
                  delta_color="inverse",
                  help="Positive = more fearful than average")

        # Compact zone legend — single line
        st.markdown(
            '<div style="font-size:10px;color:#475569;margin-top:6px;line-height:1.6">'
            '&lt;15 😌 Calm &nbsp;·&nbsp; 15–20 😐 Normal &nbsp;·&nbsp;'
            '20–30 😨 Elevated &nbsp;·&nbsp; &gt;30 🔥 Extreme Fear'
            '</div>',
            unsafe_allow_html=True,
        )
        if pc:
            st.markdown(
                f'<div style="font-size:10px;color:#475569;line-height:1.6">'
                f'P/C &gt;1.2 contrarian bull &nbsp;·&nbsp; 0.8–1.0 neutral &nbsp;·&nbsp; &lt;0.7 contrarian bear'
                f'<br><span style="color:#334155">{_scope_notes[pc_scope]}</span></div>',
                unsafe_allow_html=True,
            )

    # ── VIX chart with period selector ────────────────────────────────────────
    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)

    _vix_qp = st.query_params.get("vix_period", "1Y")
    vix_default_idx = vix_periods.index(_vix_qp) if _vix_qp in vix_periods else 3

    vix_choice = st.radio("Period ", vix_periods, horizontal=True,
                          key="vix_period", index=vix_default_idx)
    st.query_params["vix_period"] = vix_choice
    yf_vix_period = vix_period_map[vix_choice]
    vix_chart_df  = fetch_vix_history(period=yf_vix_period)

    if not vix_chart_df.empty and "VIX" in vix_chart_df.columns:
        st.plotly_chart(_spy_vix_chart(vix_chart_df), width="stretch")

    # ── VIX gap table in expander ─────────────────────────────────────────────
    vix_ohlc = fetch_vix_ohlc(period=yf_vix_period)
    if not vix_ohlc.empty:
        with st.expander("VIX Daily Gap History", expanded=False):
            vix_gaps = compute_daily_gaps(vix_ohlc)
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


def _render_spy_gap_table(daily_df: pd.DataFrame, quote: dict) -> None:
    gaps_df = apply_gap_cache(patch_today_gap(compute_daily_gaps(daily_df), quote))
    save_confirmed_gaps(gaps_df)

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

    render_gap_table(gaps_df, title="Daily Gaps (Last 30 Days)",
                     show_rsi=True, show_next_day=True, share_url=share_url)


def _spy_chart(df, ma_periods: list, prev_close: float | None = None,
               show_rsi: bool = False) -> go.Figure:
    """Candlestick + volume + optional RSI chart."""
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

    if prev_close is not None:
        fig.add_hline(y=prev_close, row=1, col=1,
                      line_dash="dot", line_color="#64748B", line_width=1,
                      annotation_text=f"Prev {prev_close:,.2f}",
                      annotation_font_size=9, annotation_position="top right")

    if "Volume" in df.columns:
        bar_colors = ["#22C55E" if c >= o else "#EF4444"
                      for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=bar_colors, opacity=0.5,
            name="Volume", showlegend=False,
        ), row=vol_row, col=1)

    if show_rsi and rsi_row:
        rsi = compute_rsi(df)
        fig.add_trace(go.Scatter(
            x=df.index, y=rsi, name="RSI (14)",
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
