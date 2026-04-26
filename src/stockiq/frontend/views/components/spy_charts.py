"""
SPY-specific Plotly figure builders.

These functions are pure data-in / figure-out — no Streamlit calls — so they
can be tested independently and reused across panels without coupling to any
particular page.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def spy_candle_chart(
    df: pd.DataFrame,
    ma_periods: list[int],
    prev_close: float | None = None,
    show_rsi: bool = False,
    vwap: pd.Series | None = None,
    max_pain: float | None = None,
    call_wall: float | None = None,
    put_wall: float | None = None,
    or_high: float | None = None,
    or_low: float | None = None,
    pdh: float | None = None,
    pdl: float | None = None,
    pivot: float | None = None,
    r1: float | None = None,
    s1: float | None = None,
    vwap_u1: pd.Series | None = None,
    vwap_l1: pd.Series | None = None,
    vwap_u2: pd.Series | None = None,
    vwap_l2: pd.Series | None = None,
) -> go.Figure:
    """Candlestick + volume + optional RSI + VWAP bands + key price levels."""
    if show_rsi:
        rows, row_heights = 3, [0.55, 0.2, 0.25]
        vol_row, rsi_row  = 2, 3
    else:
        rows, row_heights = 2, [0.75, 0.25]
        vol_row, rsi_row  = 2, None

    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        row_heights=row_heights, vertical_spacing=0.03,
    )

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing_line_color="#22C55E", decreasing_line_color="#EF4444",
        name="SPY", showlegend=False,
    ), row=1, col=1)

    _MA_COLORS = {20: "#F59E0B", 50: "#3B82F6", 200: "#EF4444"}
    for p in ma_periods:
        if len(df) >= p:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"].rolling(p).mean(),
                mode="lines", line=dict(color=_MA_COLORS[p], width=1.5),
                name=f"MA{p}",
            ), row=1, col=1)

    if vwap is not None:
        _add_vwap_bands(fig, df, vwap, vwap_u1, vwap_l1, vwap_u2, vwap_l2)

    _add_hlines(fig, or_high, or_low, pdh, pdl, pivot, r1, s1, prev_close, max_pain, call_wall, put_wall)

    if "Volume" in df.columns:
        bar_colors = ["#22C55E" if c >= o else "#EF4444"
                      for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=bar_colors, opacity=0.5,
            name="Volume", showlegend=False,
        ), row=vol_row, col=1)

    if show_rsi and rsi_row and "RSI" in df.columns:
        _add_rsi_subplot(fig, df, rsi_row)

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


def oi_butterfly_chart(
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
    _add_price_line(fig, current_price)
    if y_min <= max_pain <= y_max:
        fig.add_shape(type="line", xref="paper", yref="y",
                      x0=0, x1=1, y0=max_pain, y1=max_pain,
                      line=dict(color="#F59E0B", width=1.5, dash="dot"))
        fig.add_annotation(xref="paper", yref="y", x=1.01, y=max_pain,
                           text=f"Pain ${max_pain:,.0f}", showarrow=False,
                           font=dict(color="#F59E0B", size=10), xanchor="left")

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
            title="Open Interest", gridcolor="#1E293B",
        ),
        yaxis=dict(title="Strike", gridcolor="#1E293B", dtick=5),
        legend=dict(orientation="h", y=1.04, x=0),
        hovermode="y unified",
    )
    return fig


def gex_chart(gex_df: pd.DataFrame, current_price: float, n_strikes: int = 30) -> go.Figure:
    """Horizontal bar chart of GEX by strike — green = stabilising, red = amplifying."""
    strikes = gex_df["strike"].values
    idx  = int(np.searchsorted(strikes, current_price))
    half = n_strikes // 2
    lo   = max(0, idx - half)
    hi   = min(len(gex_df), lo + n_strikes)
    lo   = max(0, hi - n_strikes)
    gex_df = gex_df.iloc[lo:hi]

    colors = ["#22C55E" if v >= 0 else "#EF4444" for v in gex_df["gex"]]
    fig = go.Figure(go.Bar(
        x=gex_df["gex"] / 1e6,
        y=gex_df["strike"],
        orientation="h",
        marker_color=colors,
        opacity=0.8,
        hovertemplate="Strike: <b>$%{y:,.0f}</b><br>GEX: <b>%{x:,.1f}M</b><extra></extra>",
    ))
    _add_price_line(fig, current_price)
    fig.add_vline(x=0, line_color="#475569", line_width=1)
    fig.update_layout(
        template="plotly_dark", height=420,
        margin=dict(l=60, r=100, t=10, b=40),
        xaxis=dict(title="Gamma Exposure ($M)", gridcolor="#1E293B"),
        yaxis=dict(title="Strike", gridcolor="#1E293B", dtick=5),
        hovermode="y unified",
    )
    return fig


def oi_heatmap_chart(
    call_pivot: pd.DataFrame,
    put_pivot: pd.DataFrame,
    current_price: float,
) -> go.Figure:
    """Diverging heatmap: green = call-heavy strikes, red = put-heavy strikes."""
    net     = call_pivot.sub(put_pivot, fill_value=0)
    strikes = net.index.tolist()
    exps    = net.columns.tolist()
    abs_max = float(net.abs().max().max()) or 1

    fig = go.Figure(go.Heatmap(
        z=net.values.tolist(), x=exps, y=strikes,
        colorscale=[
            [0.00, "#7F1D1D"], [0.25, "#DC2626"], [0.45, "#6B7280"],
            [0.50, "#9CA3AF"], [0.55, "#6B7280"], [0.75, "#16A34A"],
            [1.00, "#14532D"],
        ],
        zmid=0, zmin=-abs_max, zmax=abs_max,
        colorbar=dict(
            title=dict(text="Net OI<br>(Calls−Puts)", font=dict(size=10, color="#94A3B8")),
            tickfont=dict(size=9, color="#94A3B8"), len=0.85,
        ),
        hovertemplate=(
            "Expiry: <b>%{x}</b><br>Strike: <b>$%{y:,.0f}</b><br>"
            "Net OI: <b>%{z:,.0f}</b><br>"
            "<i>+ = call-heavy &nbsp;· &nbsp;− = put-heavy</i><extra></extra>"
        ),
    ))

    fig.add_shape(type="line", xref="paper", yref="y",
                  x0=0, x1=1, y0=current_price, y1=current_price,
                  line=dict(color="#3B82F6", width=2))
    fig.add_annotation(xref="paper", yref="y", x=1.01, y=current_price,
                       text=f"<b>${current_price:,.0f}</b>",
                       showarrow=False, font=dict(color="#3B82F6", size=10), xanchor="left")
    fig.update_layout(
        template="plotly_dark", height=480,
        margin=dict(l=70, r=130, t=10, b=60),
        xaxis=dict(title="Expiration", tickangle=-30, side="bottom", gridcolor="#1E293B"),
        yaxis=dict(title="Strike ($)", dtick=5, gridcolor="#1E293B"),
        hovermode="closest",
    )
    return fig


# ── Private helpers ────────────────────────────────────────────────────────────

def _add_price_line(fig: go.Figure, price: float) -> None:
    fig.add_shape(type="line", xref="paper", yref="y",
                  x0=0, x1=1, y0=price, y1=price,
                  line=dict(color="#3B82F6", width=2))
    fig.add_annotation(xref="paper", yref="y", x=1.01, y=price,
                       text=f"<b>${price:,.0f}</b>",
                       showarrow=False, font=dict(color="#3B82F6", size=10), xanchor="left")


def _add_vwap_bands(
    fig: go.Figure,
    df: pd.DataFrame,
    vwap: pd.Series,
    u1: pd.Series | None,
    l1: pd.Series | None,
    u2: pd.Series | None,
    l2: pd.Series | None,
) -> None:
    if u2 is not None:
        fig.add_trace(go.Scatter(x=df.index, y=u2, name="VWAP+2σ", mode="lines",
                                 line=dict(color="#E879F9", width=0.8, dash="dot"), opacity=0.4,
                                 hovertemplate="VWAP+2σ: <b>%{y:,.2f}</b><extra></extra>"), row=1, col=1)
    if l2 is not None:
        fig.add_trace(go.Scatter(x=df.index, y=l2, name="VWAP-2σ", mode="lines",
                                 line=dict(color="#E879F9", width=0.8, dash="dot"), opacity=0.4,
                                 fill="tonexty", fillcolor="rgba(232,121,249,0.03)",
                                 hovertemplate="VWAP-2σ: <b>%{y:,.2f}</b><extra></extra>"), row=1, col=1)
    if u1 is not None:
        fig.add_trace(go.Scatter(x=df.index, y=u1, name="VWAP+1σ", mode="lines",
                                 line=dict(color="#E879F9", width=1, dash="dot"), opacity=0.6,
                                 hovertemplate="VWAP+1σ: <b>%{y:,.2f}</b><extra></extra>"), row=1, col=1)
    if l1 is not None:
        fig.add_trace(go.Scatter(x=df.index, y=l1, name="VWAP-1σ", mode="lines",
                                 line=dict(color="#E879F9", width=1, dash="dot"), opacity=0.6,
                                 fill="tonexty", fillcolor="rgba(232,121,249,0.05)",
                                 hovertemplate="VWAP-1σ: <b>%{y:,.2f}</b><extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=vwap, name="VWAP", mode="lines",
                             line=dict(color="#E879F9", width=1.5, dash="dash"),
                             hovertemplate="VWAP: <b>%{y:,.2f}</b><extra></extra>"), row=1, col=1)


def _add_hlines(
    fig: go.Figure,
    or_high, or_low, pdh, pdl, pivot, r1, s1, prev_close, max_pain, call_wall, put_wall,
) -> None:
    _hl = fig.add_hline
    if or_high is not None:
        _hl(y=or_high, row=1, col=1, line_dash="solid", line_color="#FBBF24", line_width=1.2,
            annotation_text=f"OR H {or_high:,.2f}", annotation_font_size=9,
            annotation_font_color="#FBBF24", annotation_position="top left")
    if or_low is not None:
        _hl(y=or_low, row=1, col=1, line_dash="solid", line_color="#FBBF24", line_width=1.2,
            annotation_text=f"OR L {or_low:,.2f}", annotation_font_size=9,
            annotation_font_color="#FBBF24", annotation_position="bottom left")
    if pdh is not None:
        _hl(y=pdh, row=1, col=1, line_dash="dash", line_color="#94A3B8", line_width=1,
            annotation_text=f"PDH {pdh:,.2f}", annotation_font_size=9,
            annotation_font_color="#94A3B8", annotation_position="top right")
    if pdl is not None:
        _hl(y=pdl, row=1, col=1, line_dash="dash", line_color="#94A3B8", line_width=1,
            annotation_text=f"PDL {pdl:,.2f}", annotation_font_size=9,
            annotation_font_color="#94A3B8", annotation_position="bottom right")
    if pivot is not None:
        _hl(y=pivot, row=1, col=1, line_dash="dot", line_color="#38BDF8", line_width=1,
            annotation_text=f"P {pivot:,.2f}", annotation_font_size=9,
            annotation_font_color="#38BDF8", annotation_position="top left")
    if r1 is not None:
        _hl(y=r1, row=1, col=1, line_dash="dot", line_color="#86EFAC", line_width=1,
            annotation_text=f"R1 {r1:,.2f}", annotation_font_size=9,
            annotation_font_color="#86EFAC", annotation_position="top left")
    if s1 is not None:
        _hl(y=s1, row=1, col=1, line_dash="dot", line_color="#FDA4AF", line_width=1,
            annotation_text=f"S1 {s1:,.2f}", annotation_font_size=9,
            annotation_font_color="#FDA4AF", annotation_position="bottom left")
    if prev_close is not None:
        _hl(y=prev_close, row=1, col=1, line_dash="dot", line_color="#64748B", line_width=1,
            annotation_text=f"Prev {prev_close:,.2f}", annotation_font_size=9,
            annotation_position="top right")
    if max_pain is not None:
        _hl(y=max_pain, row=1, col=1, line_dash="dot", line_color="#F59E0B", line_width=1.2,
            annotation_text=f"Max Pain {max_pain:,.0f}", annotation_font_size=9,
            annotation_position="top left")
    if call_wall is not None:
        _hl(y=call_wall, row=1, col=1, line_dash="dash", line_color="#22C55E", line_width=1,
            annotation_text=f"Call Wall {call_wall:,.0f}", annotation_font_size=9,
            annotation_position="top right")
    if put_wall is not None:
        _hl(y=put_wall, row=1, col=1, line_dash="dash", line_color="#EF4444", line_width=1,
            annotation_text=f"Put Wall {put_wall:,.0f}", annotation_font_size=9,
            annotation_position="bottom right")


def _add_rsi_subplot(fig: go.Figure, df: pd.DataFrame, rsi_row: int) -> None:
    fig.add_trace(go.Scatter(
        x=df.index, y=df["RSI"], name="RSI (14)",
        line=dict(color="#A78BFA", width=1.5),
        hovertemplate="RSI: %{y:.1f}<extra></extra>",
    ), row=rsi_row, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.08)", line_width=0, row=rsi_row, col=1)
    fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(34,197,94,0.08)",  line_width=0, row=rsi_row, col=1)
    for level, label, color in [(70, "OB 70", "#EF4444"), (50, "50", "#64748B"), (30, "OS 30", "#22C55E")]:
        fig.add_hline(y=level, line_dash="dot", line_color=color, line_width=1,
                      annotation_text=label, annotation_position="right",
                      annotation_font_size=9, row=rsi_row, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=rsi_row, col=1)
