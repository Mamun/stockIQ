import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from stockiq.backend.services.market_service import (
    get_market_overview,
    get_vix_chart_df,
    get_vix_gap_history,
)
from stockiq.frontend.views.components.gap_table import render_gap_table

_VIX_ZONE_COLORS = {
    "Calm":         ("#22C55E", "rgba(34,197,94,0.10)"),
    "Normal":       ("#86EFAC", "rgba(134,239,172,0.10)"),
    "Elevated":     ("#F59E0B", "rgba(245,158,11,0.10)"),
    "Extreme Fear": ("#EF4444", "rgba(239,68,68,0.10)"),
}

_VIX_PERIODS     = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
_VIX_PERIOD_MAP  = {"1M": "1mo", "3M": "3mo", "6M": "6mo",
                    "1Y": "1y",  "2Y": "2y",  "5Y": "5y"}


def render_volatility_page() -> None:
    overview = get_market_overview()
    vix      = overview.get("vix")
    if not vix:
        st.error("VIX data unavailable.")
        return

    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;'
        'letter-spacing:.08em;text-transform:uppercase;margin-bottom:16px">'
        'Fear Gauge — VIX · CBOE Volatility Index</div>',
        unsafe_allow_html=True,
    )

    _render_vix_snapshot(vix)
    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
    _render_vix_explained()
    st.divider()
    _render_vix_chart_section(vix)


# ── Private helpers ────────────────────────────────────────────────────────────

def _render_vix_snapshot(vix: dict) -> None:
    vix_now  = vix["current"]
    vix_chg  = vix["change"]
    vix_52hi = vix["high_52w"]
    vix_52lo = vix["low_52w"]
    vix_avg  = vix["avg"]
    zone     = vix["zone"]
    zone_clr, zone_bg = _VIX_ZONE_COLORS.get(zone, ("#94A3B8", "rgba(148,163,184,0.10)"))
    chg_arrow = "▲" if vix_chg >= 0 else "▼"
    chg_color = "#EF4444" if vix_chg >= 0 else "#22C55E"

    col_badge, col_stats = st.columns([1, 2])

    with col_badge:
        st.markdown(
            f"""
<div style="background:{zone_bg};border:1px solid {zone_clr}55;border-radius:12px;
            padding:24px;height:100%;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase">VIX · CBOE</div>
  <div style="font-size:52px;font-weight:900;color:#F1F5F9;line-height:1;margin:8px 0 6px">
    {vix_now:.2f}
  </div>
  <div style="font-size:15px;font-weight:700;color:{zone_clr};margin-bottom:10px">
    {zone}
  </div>
  <div style="font-size:12px;color:{chg_color}">
    {chg_arrow}&nbsp;{abs(vix_chg):.2f} vs prev close
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    with col_stats:
        r1, r2 = st.columns(2)
        r1.metric("1Y High",   f"{vix_52hi:.2f}", help="Highest VIX close in the past year")
        r1.metric("1Y Avg",    f"{vix_avg:.2f}",  help="Average VIX close over the past year")
        r2.metric("1Y Low",    f"{vix_52lo:.2f}", help="Lowest VIX close in the past year")
        r2.metric("vs 1Y Avg", f"{vix_now - vix_avg:+.2f}",
                  delta_color="inverse",
                  help="Positive = more fearful than average")
        st.markdown(
            '<div style="font-size:10px;color:#475569;margin-top:10px;line-height:1.8">'
            '&lt;15 😌 <b style="color:#22C55E">Calm</b>'
            '&nbsp;·&nbsp; 15–20 😐 <b style="color:#86EFAC">Normal</b>'
            '&nbsp;·&nbsp; 20–30 😨 <b style="color:#F59E0B">Elevated</b>'
            '&nbsp;·&nbsp; &gt;30 🔥 <b style="color:#EF4444">Extreme Fear</b>'
            '</div>',
            unsafe_allow_html=True,
        )


def _render_vix_explained() -> None:
    with st.expander("What is VIX?", expanded=False):
        st.markdown(
            """
**VIX** (CBOE Volatility Index) measures the market's expectation of 30-day volatility in the
S&P 500, derived from real-time options prices. It is often called the **"fear gauge"**.

- **Rising VIX** → markets expect turbulence; traders are buying protection (puts).
- **Falling VIX** → calm expected; complacency risk can build.
- VIX and SPY prices are historically **negatively correlated** — when SPY drops sharply, VIX spikes.
- VIX above **30** has historically coincided with major market dislocations (corrections, crashes).
            """
        )


def _render_vix_chart_section(vix: dict) -> None:
    _qp = st.query_params.get("vix_period", "1Y")
    default_idx = _VIX_PERIODS.index(_qp) if _qp in _VIX_PERIODS else 3

    vix_choice = st.radio("Period", _VIX_PERIODS, horizontal=True,
                          key="vix_period", index=default_idx)
    st.query_params["vix_period"] = vix_choice
    yf_period = _VIX_PERIOD_MAP[vix_choice]

    vix_chart_df = get_vix_chart_df(period=yf_period)
    if not vix_chart_df.empty and "VIX" in vix_chart_df.columns:
        st.plotly_chart(_vix_spy_chart(vix_chart_df), width="stretch")

    vix_gaps = get_vix_gap_history(period=yf_period)
    if not vix_gaps.empty:
        render_gap_table(vix_gaps, title="VIX Gap History", price_prefix="")


def _vix_spy_chart(df: pd.DataFrame) -> go.Figure:
    """Dual-axis: SPY price (left) + VIX with MAs and zone bands (right)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    spy_min, spy_max = df["SPY"].min(), df["SPY"].max()
    vix_min, vix_max = df["VIX"].min(), df["VIX"].max()
    spy_range = [spy_min - (spy_max - spy_min) * 0.05,
                 spy_max + (spy_max - spy_min) * 0.05]
    vix_range = [max(0, vix_min - (vix_max - vix_min) * 0.12),
                 vix_max + (vix_max - vix_min) * 0.12]

    fig.add_trace(go.Scatter(
        x=df.index, y=df["SPY"],
        name="SPY", mode="lines",
        line=dict(color="#3B82F6", width=2),
        hovertemplate="SPY: <b>%{y:,.2f}</b><extra></extra>",
    ), secondary_y=False)

    # VIX fill-under
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
        (15, "#22C55E", "15 Calm"), (20, "#F59E0B", "20 Elevated"), (30, "#EF4444", "30 Fear"),
    ]:
        if vix_range[0] <= level <= vix_range[1]:
            fig.add_hline(
                y=level, secondary_y=True,
                line_dash="dot", line_color=color, line_width=1,
                annotation_text=label, annotation_font_size=9,
                annotation_position="top right",
            )

    fig.update_layout(
        template="plotly_dark", height=380,
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


render_volatility_page()
