"""
Options-specific Plotly figure builders: OI butterfly, GEX, OI heatmap.

These functions are pure data-in / figure-out — no Streamlit calls — so they
can be tested independently and reused across panels without coupling to any
particular page.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


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


def oi_gex_combined_chart(
    oi_df: pd.DataFrame,
    gex_df: pd.DataFrame,
    current_price: float,
    max_pain: float,
    n_strikes: int = 40,
    call_gex_df: pd.DataFrame | None = None,
    put_gex_df: pd.DataFrame | None = None,
) -> go.Figure:
    """OI butterfly (left) + GEX (right) sharing a single strike Y-axis.

    Replaces the two separate charts that looked identical at a glance.
    The shared axis makes the OI→GEX relationship immediately readable:
    a strike with massive OI but tiny GEX means low-gamma (deep ITM/OTM) contracts.
    """
    # Clip everything to a dollar window centred on current price.
    dollar_half = n_strikes // 2
    lo, hi = current_price - dollar_half, current_price + dollar_half
    if not gex_df.empty:
        gex_df = gex_df[(gex_df["strike"] >= lo) & (gex_df["strike"] <= hi)].copy()
    if not oi_df.empty:
        oi_df = oi_df[(oi_df["strike"] >= lo) & (oi_df["strike"] <= hi)].copy()

    # Bucket all datasets to $5 strike increments so OI (CBOE $1 increments)
    # and GEX render at the same bar height on the shared Y axis.
    bucket = 5.0
    if not gex_df.empty:
        gex_df["strike"] = (gex_df["strike"] / bucket).round() * bucket
        gex_df = gex_df.groupby("strike", as_index=False)["gex"].sum()
    if not oi_df.empty:
        oi_df = oi_df.copy()
        oi_df["strike"] = (oi_df["strike"] / bucket).round() * bucket
        oi_df = (
            oi_df.groupby("strike", as_index=False)
            .agg({"call_oi": "sum", "put_oi": "sum"})
            .reset_index(drop=True)
        )

    def _clip_bucket(df: pd.DataFrame | None) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["strike", "gex"])
        df = df[(df["strike"] >= current_price - dollar_half) &
                (df["strike"] <= current_price + dollar_half)].copy()
        df["strike"] = (df["strike"] / bucket).round() * bucket
        return df.groupby("strike", as_index=False)["gex"].sum()

    use_split = call_gex_df is not None and not call_gex_df.empty
    if use_split:
        call_gex_df = _clip_bucket(call_gex_df)
        put_gex_df  = _clip_bucket(put_gex_df)

    # Y range: GEX window drives the range; OI bars fill where they have data.
    active_strikes: list[float] = []
    if not gex_df.empty:
        active_strikes.extend(gex_df["strike"].tolist())
    if not oi_df.empty:
        has_oi = (oi_df["call_oi"] > 0) | (oi_df["put_oi"] > 0)
        active_strikes.extend(oi_df.loc[has_oi, "strike"].tolist())

    if active_strikes:
        y_min, y_max = min(active_strikes), max(active_strikes)
    else:
        y_min, y_max = current_price - dollar_half, current_price + dollar_half

    fig = make_subplots(
        rows=1, cols=2,
        shared_yaxes=True,
        column_widths=[0.62, 0.38],
        subplot_titles=["Open Interest by Strike", "Gamma Exposure (GEX)"],
        horizontal_spacing=0.04,
    )

    # ── OI Butterfly (left panel) ────────────────────────────────────────────
    if not oi_df.empty:
        strikes = oi_df["strike"].values
        call_oi = oi_df["call_oi"].values.astype(float)
        put_oi  = oi_df["put_oi"].values.astype(float)

        fig.add_trace(go.Bar(
            y=strikes, x=-put_oi, orientation="h",
            name="Put OI", marker_color="rgba(239,68,68,0.75)",
            showlegend=False,
            hovertemplate="Strike $%{y:,.0f}<br>Put OI: %{customdata:,}<extra></extra>",
            customdata=put_oi,
        ), row=1, col=1)
        fig.add_trace(go.Bar(
            y=strikes, x=call_oi, orientation="h",
            name="Call OI", marker_color="rgba(34,197,94,0.75)",
            showlegend=False,
            hovertemplate="Strike $%{y:,.0f}<br>Call OI: %{x:,}<extra></extra>",
        ), row=1, col=1)

        x_max     = max(float(call_oi.max()), float(put_oi.max())) * 1.1 if len(call_oi) else 1
        tick_step = max(1, int(x_max / 4))
        fig.update_xaxes(
            range=[-x_max, x_max],
            tickvals=[-4*tick_step, -2*tick_step, 0, 2*tick_step, 4*tick_step],
            ticktext=[f"{4*tick_step:,}", f"{2*tick_step:,}", "0",
                      f"{2*tick_step:,}", f"{4*tick_step:,}"],
            title_text="← Puts  ·  Open Interest  ·  Calls →",
            gridcolor="#1E293B",
            row=1, col=1,
        )

    # ── GEX (right panel) ────────────────────────────────────────────────────
    _gex_rendered = False
    if use_split:
        if not call_gex_df.empty:
            fig.add_trace(go.Bar(
                x=call_gex_df["gex"] / 1e6,
                y=call_gex_df["strike"],
                orientation="h",
                marker_color="rgba(34,197,94,0.80)",
                name="Call GEX",
                showlegend=True,
                hovertemplate="Strike: <b>$%{y:,.0f}</b><br>Call GEX: <b>+%{x:,.1f}M</b><extra></extra>",
            ), row=1, col=2)
            _gex_rendered = True
        if not put_gex_df.empty:
            fig.add_trace(go.Bar(
                x=put_gex_df["gex"] / 1e6,
                y=put_gex_df["strike"],
                orientation="h",
                marker_color="rgba(239,68,68,0.80)",
                name="Put GEX",
                showlegend=True,
                hovertemplate="Strike: <b>$%{y:,.0f}</b><br>Put GEX: <b>%{x:,.1f}M</b><extra></extra>",
            ), row=1, col=2)
            _gex_rendered = True
    elif not gex_df.empty:
        # Fallback: net GEX bars (green=stabilising, red=amplifying)
        gex_colors = ["#22C55E" if v >= 0 else "#EF4444" for v in gex_df["gex"]]
        fig.add_trace(go.Bar(
            x=gex_df["gex"] / 1e6,
            y=gex_df["strike"],
            orientation="h",
            marker_color=gex_colors,
            opacity=0.8,
            name="Net GEX",
            showlegend=False,
            hovertemplate="Strike: <b>$%{y:,.0f}</b><br>GEX: <b>%{x:,.1f}M</b><extra></extra>",
        ), row=1, col=2)
        _gex_rendered = True
    if _gex_rendered:
        fig.add_vline(x=0, line_color="#475569", line_width=1, row=1, col=2)
        gex_axis_title = (
            "← Put GEX  ·  GEX ($M)  ·  Call GEX →" if use_split
            else "← Amplifying  ·  GEX ($M)  ·  Stabilising →"
        )
        # Symmetric x-range so the axis title stays centred regardless of
        # whether call or put GEX dominates in absolute terms.
        _gex_vals: list[float] = []
        if use_split:
            if not call_gex_df.empty:
                _gex_vals.append(float(call_gex_df["gex"].abs().max()) / 1e6)
            if not put_gex_df.empty:
                _gex_vals.append(float(put_gex_df["gex"].abs().max()) / 1e6)
        elif not gex_df.empty:
            _gex_vals.append(float(gex_df["gex"].abs().max()) / 1e6)
        _gex_max = max(_gex_vals) * 1.1 if _gex_vals else 1.0
        fig.update_xaxes(
            title_text=gex_axis_title,
            range=[-_gex_max, _gex_max],
            gridcolor="#1E293B",
            row=1, col=2,
        )

    # ── Shared reference lines (span both panels via shared Y) ───────────────
    fig.add_hline(
        y=current_price, line_color="#3B82F6", line_width=2,
        annotation_text=f"<b>${current_price:,.0f}</b>",
        annotation_position="bottom right",
        annotation_font=dict(color="#3B82F6", size=10),
    )
    if y_min <= max_pain <= y_max:
        fig.add_hline(
            y=max_pain, line_color="#F59E0B", line_width=1.5, line_dash="dot",
            annotation_text=f"Pain ${max_pain:,.0f}",
            annotation_position="top left",
            annotation_font=dict(color="#F59E0B", size=10),
        )

    fig.update_yaxes(title_text="Strike ($)", gridcolor="#1E293B", dtick=5,
                     range=[y_min - 2, y_max + 2], row=1, col=1)
    fig.update_layout(
        template="plotly_dark",
        height=460,
        barmode="overlay",
        showlegend=use_split,
        legend=dict(orientation="h", y=-0.12, x=0.62, font=dict(size=11)) if use_split else {},
        margin=dict(l=60, r=10, t=36, b=50 if not use_split else 70),
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
    window: float = 50.0,
    bucket: int = 5,
) -> go.Figure:
    """Diverging heatmap: green = call-heavy strikes, red = put-heavy strikes.

    Only shows strikes within `window` points of current price, bucketed to
    the nearest `bucket` dollars, so zero-OI rows don't bloat the chart.
    """
    net = call_pivot.sub(put_pivot, fill_value=0)

    # 1. Price-window filter — keep only near-the-money strikes
    net = net[(net.index >= current_price - window) & (net.index <= current_price + window)]

    # 2. $5-bucket aggregation — merge adjacent strikes, reduces noise
    net.index = (net.index / bucket).round() * bucket
    net = net.groupby(net.index).sum()

    # 3. Drop rows where every expiration has zero net OI
    net = net[net.abs().sum(axis=1) > 0]

    if net.empty:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", height=200,
                          annotations=[dict(text="No OI data in price window", showarrow=False,
                                           font=dict(color="#94A3B8"))])
        return fig

    exps    = net.columns.tolist()
    abs_max = float(net.abs().max().max()) or 1

    fig = go.Figure(go.Heatmap(
        z=net.values.tolist(), x=exps, y=net.index.tolist(),
        colorscale=[
            [0.00, "#7F1D1D"],  # deep red  — heavy put wall
            [0.30, "#EF4444"],  # vivid red — moderate put concentration
            [0.47, "#1E293B"],  # dark slate — fading toward neutral
            [0.50, "#0F172A"],  # near-black — zero / neutral (blends with bg)
            [0.53, "#1E293B"],  # dark slate — fading toward neutral
            [0.70, "#22C55E"],  # vivid green — moderate call concentration
            [1.00, "#14532D"],  # deep green — heavy call wall
        ],
        zmid=0, zmin=-abs_max, zmax=abs_max,
        colorbar=dict(
            title=dict(text="Net OI<br>(Calls−Puts)", font=dict(size=10, color="#94A3B8")),
            tickfont=dict(size=9, color="#94A3B8"), len=0.85,
            tickvals=[-abs_max, -abs_max * 0.5, 0, abs_max * 0.5, abs_max],
            ticktext=["Put wall", "Put heavy", "Neutral", "Call heavy", "Call wall"],
        ),
        hovertemplate=(
            "Expiry: <b>%{x}</b><br>Strike: <b>$%{y:,.0f}</b><br>"
            "Net OI: <b>%{z:,.0f}</b><br>"
            "<i>+ = call-heavy &nbsp;· &nbsp;− = put-heavy</i><extra></extra>"
        ),
    ))

    fig.add_shape(type="line", xref="paper", yref="y",
                  x0=0, x1=1, y0=current_price, y1=current_price,
                  line=dict(color="#3B82F6", width=2, dash="dot"))
    fig.add_annotation(xref="paper", yref="y", x=1.01, y=current_price,
                       text=f"<b>${current_price:,.0f}</b>",
                       showarrow=False, font=dict(color="#3B82F6", size=10), xanchor="left")
    fig.update_layout(
        template="plotly_dark", height=420,
        margin=dict(l=70, r=130, t=10, b=60),
        xaxis=dict(title="Expiration", tickangle=-30, side="bottom", gridcolor="#1E293B"),
        yaxis=dict(title="Strike ($)", dtick=bucket, gridcolor="#1E293B"),
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
