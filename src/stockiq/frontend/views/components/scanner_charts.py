"""
Pure Plotly figure builders for all scanner pages.
Zero Streamlit calls — every function returns go.Figure and is independently testable.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from stockiq.frontend.theme import DN, MUT, NEU, UP

# ── Extended scanner palette (beyond the 7-color core theme) ─────────────────
_YEL = "#FACC15"   # yellow  — top-tier / ⭐ strong signal
_ORG = "#F97316"   # orange  — warning / mid-tier
_LGN = "#86EFAC"   # light green — mild bullish
_LRD = "#FCA5A5"   # light red   — mild bearish
_BLU = "#3B82F6"   # blue        — neutral / informational bars


# ── Analyst consensus — Buy ───────────────────────────────────────────────────

def analyst_upside_bar(df) -> go.Figure:
    """Horizontal bar: analyst price-target upside % per ticker."""
    sdf = df.sort_values("Upside %", ascending=False)
    colors = [UP if u >= 20 else _LGN if u >= 10 else MUT for u in sdf["Upside %"]]
    fig = go.Figure(go.Bar(
        x=sdf["Ticker"],
        y=sdf["Upside %"],
        marker_color=colors,
        text=sdf["Upside %"].apply(lambda v: f"+{v:.1f}%"),
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Current: $%{customdata[0]:.2f}<br>"
            "Target:  $%{customdata[1]:.2f}<br>"
            "Upside:  +%{y:.1f}%<extra></extra>"
        ),
        customdata=sdf[["Price", "Target"]].values,
    ))
    fig.add_hline(y=20, line_dash="dot", line_color=UP,
                  annotation_text="≥20% upside", annotation_font_size=9)
    fig.add_hline(y=10, line_dash="dot", line_color=_LGN,
                  annotation_text="≥10% upside", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=20, r=80, t=10, b=40),
        yaxis=dict(title="Upside %", ticksuffix="%"),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def analyst_buy_scatter(df) -> go.Figure:
    """Bubble scatter: analyst rating (x) vs upside % (y), bubble = analyst count."""
    bubble_size = (df["Analysts"] / df["Analysts"].max() * 35 + 10).tolist()
    colors = [_YEL if r <= 1.5 else UP if r <= 2.0 else NEU for r in df["Rating"]]
    fig = go.Figure(go.Scatter(
        x=df["Rating"],
        y=df["Upside %"],
        mode="markers+text",
        text=df["Ticker"],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(size=bubble_size, color=colors, opacity=0.85,
                    line=dict(color="#FFFFFF", width=0.5)),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Rating: %{x:.2f}<br>"
            "Upside: +%{y:.1f}%<extra></extra>"
        ),
    ))
    fig.add_vline(x=1.5, line_dash="dot", line_color=_YEL,
                  annotation_text="Strong Buy", annotation_font_size=9)
    fig.add_vline(x=2.0, line_dash="dot", line_color=UP,
                  annotation_text="Buy", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=40, r=40, t=20, b=40),
        xaxis=dict(title="Analyst Rating (lower = more bullish)", autorange="reversed"),
        yaxis=dict(title="Upside %", ticksuffix="%"),
        showlegend=False,
    )
    return fig


# ── Analyst consensus — Sell ──────────────────────────────────────────────────

def analyst_downside_bar(df) -> go.Figure:
    """Bar: analyst price-target downside % per ticker (negative values)."""
    sdf = df.sort_values("Downside %")
    colors = [DN if d <= -20 else _ORG if d <= -10 else MUT for d in sdf["Downside %"]]
    fig = go.Figure(go.Bar(
        x=sdf["Ticker"],
        y=sdf["Downside %"],
        marker_color=colors,
        text=sdf["Downside %"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Current: $%{customdata[0]:.2f}<br>"
            "Target:  $%{customdata[1]:.2f}<br>"
            "Downside: %{y:.1f}%<extra></extra>"
        ),
        customdata=sdf[["Price", "Target"]].values,
    ))
    fig.add_hline(y=-20, line_dash="dot", line_color=DN,
                  annotation_text="≥20% downside", annotation_font_size=9)
    fig.add_hline(y=-10, line_dash="dot", line_color=_ORG,
                  annotation_text="≥10% downside", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=20, r=80, t=10, b=40),
        yaxis=dict(title="Downside %", ticksuffix="%"),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def analyst_sell_scatter(df) -> go.Figure:
    """Bubble scatter: analyst rating (x) vs downside % (y), bubble = analyst count."""
    bubble_size = (df["Analysts"] / df["Analysts"].max() * 35 + 10).tolist()
    colors = [DN if r >= 4.5 else _ORG if r >= 4.0 else _YEL for r in df["Rating"]]
    fig = go.Figure(go.Scatter(
        x=df["Rating"],
        y=df["Downside %"],
        mode="markers+text",
        text=df["Ticker"],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(size=bubble_size, color=colors, opacity=0.85,
                    line=dict(color="#FFFFFF", width=0.5)),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Rating: %{x:.2f}<br>"
            "Downside: %{y:.1f}%<extra></extra>"
        ),
    ))
    fig.add_vline(x=4.5, line_dash="dot", line_color=DN,
                  annotation_text="Strong Sell", annotation_font_size=9)
    fig.add_vline(x=4.0, line_dash="dot", line_color=_ORG,
                  annotation_text="Sell", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=40, r=40, t=20, b=40),
        xaxis=dict(title="Analyst Rating (higher = more bearish)"),
        yaxis=dict(title="Downside %", ticksuffix="%"),
        showlegend=False,
    )
    return fig


def analyst_sector_bar(
    df,
    score_col: str,
    side_col: str,
    side_label: str,
    bar_color: str,
    x_title: str,
) -> go.Figure:
    """Horizontal bar: avg score per sector with secondary metric annotation.

    Used for both the Buy (score_col='SB Score') and Sell (score_col='SS Score') pages.
    side_col / side_label describe the annotation value (e.g. 'Upside %', 'upside').
    """
    sector_df = df.groupby("Sector").agg(
        Count=("Ticker", "count"),
        Avg_Score=(score_col, "mean"),
        Avg_Side=(side_col, "mean"),
    ).reset_index().sort_values("Avg_Score", ascending=True)

    fig = go.Figure(go.Bar(
        x=sector_df["Avg_Score"],
        y=sector_df["Sector"],
        orientation="h",
        marker_color=bar_color,
        text=sector_df.apply(
            lambda r: f"{int(r['Count'])} stocks · avg {r['Avg_Side']:+.1f}% {side_label}",
            axis=1,
        ),
        textposition="inside",
        hovertemplate=f"<b>%{{y}}</b><br>Avg {x_title}: %{{x:.1f}}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark",
        height=max(200, len(sector_df) * 40),
        margin=dict(l=20, r=40, t=10, b=40),
        xaxis=dict(title=x_title),
        yaxis=dict(title=""),
        showlegend=False,
    )
    return fig


# ── ETF Scanner ───────────────────────────────────────────────────────────────

def etf_return_bar(df, col: str, title: str) -> go.Figure:
    """Bar chart: return % for a given period column."""
    plot_df = df.dropna(subset=[col]).sort_values(col, ascending=False)
    colors = [UP if v >= 3 else _LGN if v >= 0 else _LRD if v >= -3 else DN for v in plot_df[col]]
    fig = go.Figure(go.Bar(
        x=plot_df["Ticker"],
        y=plot_df[col],
        marker_color=colors,
        text=plot_df[col].apply(lambda v: f"{v:+.1f}%"),
        textposition="outside",
        hovertemplate=(
            f"<b>%{{x}}</b> — %{{customdata}}<br>{title}: %{{y:+.1f}}%<extra></extra>"
        ),
        customdata=plot_df["Name"],
    ))
    fig.add_hline(y=0, line_color="#475569", line_width=1)
    fig.update_layout(
        template="plotly_dark", height=340,
        margin=dict(l=20, r=60, t=10, b=40),
        yaxis=dict(title=title, ticksuffix="%"),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def etf_score_bar(df) -> go.Figure:
    """Horizontal bar: ETF Score ranking (top 20)."""
    plot_df = df.sort_values("ETF Score", ascending=True).tail(20)
    colors = [
        _YEL if s >= 65 else UP if s >= 55 else "#94A3B8" if s >= 45 else DN
        for s in plot_df["ETF Score"]
    ]
    fig = go.Figure(go.Bar(
        x=plot_df["ETF Score"],
        y=plot_df["Ticker"],
        orientation="h",
        marker_color=colors,
        text=plot_df["ETF Score"].apply(lambda v: f"{v:.1f}"),
        textposition="inside",
        hovertemplate=(
            "<b>%{y}</b> — %{customdata}<br>ETF Score: %{x:.1f}<extra></extra>"
        ),
        customdata=plot_df["Name"],
    ))
    fig.add_vline(x=65, line_dash="dot", line_color=_YEL,
                  annotation_text="Strong", annotation_font_size=9)
    fig.add_vline(x=35, line_dash="dot", line_color=DN,
                  annotation_text="Weak", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark",
        height=max(280, len(plot_df) * 28),
        margin=dict(l=20, r=40, t=10, b=40),
        xaxis=dict(title="ETF Score"),
        yaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def etf_category_heatmap(df) -> go.Figure:
    """Bar: avg 1M return per ETF category."""
    cat_df = (
        df.dropna(subset=["1M %"])
          .groupby("Category")
          .agg(Avg_1M=("1M %", "mean"), Avg_Score=("ETF Score", "mean"), Count=("Ticker", "count"))
          .reset_index()
          .sort_values("Avg_1M", ascending=False)
    )
    colors = [UP if v >= 2 else _LGN if v >= 0 else _LRD if v >= -2 else DN for v in cat_df["Avg_1M"]]
    fig = go.Figure(go.Bar(
        x=cat_df["Category"],
        y=cat_df["Avg_1M"],
        marker_color=colors,
        text=cat_df.apply(lambda r: f"{r['Count']} ETFs · score {r['Avg_Score']:.0f}", axis=1),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Avg 1M Return: %{y:+.1f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#475569", line_width=1)
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=20, r=60, t=10, b=60),
        yaxis=dict(title="Avg 1M Return %", ticksuffix="%"),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


# ── Bounce Radar ──────────────────────────────────────────────────────────────

def rsi_bar(df) -> go.Figure:
    """Bar: RSI values per ticker with oversold/overbought reference lines."""
    colors = [UP if r <= 30 else DN if r >= 70 else MUT for r in df["RSI"]]
    fig = go.Figure(go.Bar(
        x=df["Ticker"],
        y=df["RSI"],
        marker_color=colors,
        text=df["RSI"].apply(lambda v: f"{v:.1f}"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>RSI: %{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=70, line_dash="dot", line_color=DN,
                  annotation_text="Overbought 70", annotation_position="right",
                  annotation_font_size=10)
    fig.add_hline(y=30, line_dash="dot", line_color=UP,
                  annotation_text="Oversold 30", annotation_position="right",
                  annotation_font_size=10)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(100,116,139,0.07)", line_width=0)
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=20, r=100, t=20, b=40),
        yaxis=dict(title="RSI", range=[0, 105]),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


# ── Squeeze Scanner ───────────────────────────────────────────────────────────

def squeeze_scatter(df) -> go.Figure:
    """Bubble: Short Float % (x) vs RSI (y), bubble size = Squeeze Score."""
    bubble_size = (df["Squeeze Score"] / df["Squeeze Score"].max() * 40 + 10).tolist()
    colors = [DN if r >= 80 else _ORG if r >= 70 else _YEL for r in df["RSI"]]
    fig = go.Figure(go.Scatter(
        x=df["Short % Float"],
        y=df["RSI"],
        mode="markers+text",
        text=df["Ticker"],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(size=bubble_size, color=colors, opacity=0.85,
                    line=dict(color="#FFFFFF", width=0.5)),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Short Float: %{x:.1f}%<br>"
            "RSI: %{y:.1f}<extra></extra>"
        ),
    ))
    fig.add_hline(y=80, line_dash="dot", line_color=DN,
                  annotation_text="Extreme OB 80", annotation_font_size=9)
    fig.add_hline(y=70, line_dash="dot", line_color=_ORG,
                  annotation_text="Overbought 70", annotation_font_size=9)
    fig.add_annotation(
        x=df["Short % Float"].max() * 0.8, y=85,
        text="⚡ High-risk zone", showarrow=False,
        font=dict(color=DN, size=11),
    )
    fig.update_layout(
        template="plotly_dark", height=380,
        margin=dict(l=40, r=120, t=20, b=40),
        xaxis=dict(title="Short % of Float"),
        yaxis=dict(title="RSI (14)", range=[55, 100]),
    )
    return fig


def days_to_cover_bar(df) -> go.Figure:
    """Bar: days-to-cover per ticker, sorted descending."""
    sdf = df.sort_values("Days to Cover", ascending=False)
    colors = [DN if d >= 10 else _ORG if d >= 5 else MUT for d in sdf["Days to Cover"]]
    fig = go.Figure(go.Bar(
        x=sdf["Ticker"],
        y=sdf["Days to Cover"],
        marker_color=colors,
        text=sdf["Days to Cover"].apply(lambda v: f"{v:.1f}d"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Days to Cover: %{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=10, line_dash="dot", line_color=DN,
                  annotation_text="≥10 days (high pressure)", annotation_font_size=9)
    fig.add_hline(y=5, line_dash="dot", line_color=_ORG,
                  annotation_text="≥5 days", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark", height=300,
        margin=dict(l=20, r=120, t=10, b=40),
        yaxis=dict(title="Days to Cover"),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


# ── Munger Watchlist ──────────────────────────────────────────────────────────

def munger_scatter(df) -> go.Figure:
    """Bubble: distance from MA200W (x) vs quality score (y), bubble = Munger Score."""
    bubble_size = (df["Munger Score"] / df["Munger Score"].max() * 40 + 10).tolist()
    colors = [UP if d < 0 else NEU for d in df["Distance %"]]
    fig = go.Figure(go.Scatter(
        x=df["Distance %"],
        y=df["Quality Score"],
        mode="markers+text",
        text=df["Ticker"],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(size=bubble_size, color=colors, opacity=0.85,
                    line=dict(color="#FFFFFF", width=0.5)),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Distance from MA200W: %{x:+.2f}%<br>"
            "Quality Score: %{y:.1f}<extra></extra>"
        ),
    ))
    fig.add_vline(x=0, line_dash="dot", line_color=MUT,
                  annotation_text="At MA 200W", annotation_font_size=9)
    fig.add_annotation(
        x=-12, y=df["Quality Score"].max() * 0.95,
        text="🟢 Sweet spot", showarrow=False,
        font=dict(color=UP, size=11),
    )
    fig.update_layout(
        template="plotly_dark", height=380,
        margin=dict(l=40, r=80, t=20, b=40),
        xaxis=dict(title="Distance from 200-Week MA (%)"),
        yaxis=dict(title="Quality Score"),
    )
    return fig


def quality_bar(df) -> go.Figure:
    """Bar: quality score per company, sorted descending."""
    sdf = df.sort_values("Quality Score", ascending=False)
    colors = [UP if q >= 60 else NEU if q >= 40 else MUT for q in sdf["Quality Score"]]
    fig = go.Figure(go.Bar(
        x=sdf["Ticker"],
        y=sdf["Quality Score"],
        marker_color=colors,
        text=sdf["Quality Score"].apply(lambda v: f"{v:.0f}"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Quality Score: %{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=60, line_dash="dot", line_color=UP,
                  annotation_text="≥60 excellent", annotation_font_size=9)
    fig.add_hline(y=40, line_dash="dot", line_color=NEU,
                  annotation_text="≥40 good", annotation_font_size=9)
    fig.update_layout(
        template="plotly_dark", height=300,
        margin=dict(l=20, r=120, t=10, b=40),
        yaxis=dict(title="Quality Score", range=[0, 100]),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


# ── Forward P/E ───────────────────────────────────────────────────────────────

def forward_pe_bar(df) -> go.Figure:
    """Combined bar+scatter: stock Fwd P/E bars with sector median markers."""
    top = df.head(20).sort_values("Fwd P/E")
    colors = [
        UP if (r["Sector Med P/E"] and r["Fwd P/E"] < r["Sector Med P/E"] * 0.8)
        else _LGN if (r["Sector Med P/E"] and r["Fwd P/E"] < r["Sector Med P/E"])
        else NEU
        for _, r in top.iterrows()
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top["Ticker"], y=top["Fwd P/E"],
        marker_color=colors, name="Stock Fwd P/E",
        hovertemplate="<b>%{x}</b><br>Fwd P/E: %{y:.1f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=top["Ticker"], y=top["Sector Med P/E"],
        mode="markers",
        marker=dict(symbol="line-ew", size=14, color=NEU, line=dict(color=NEU, width=2)),
        name="Sector Median",
        hovertemplate="<b>%{x}</b><br>Sector Median: %{y:.1f}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=20, r=20, t=10, b=40),
        yaxis=dict(title="Forward P/E"),
        xaxis=dict(title=""),
        legend=dict(orientation="h", y=1.1),
        showlegend=True,
    )
    return fig


def forward_pe_scatter(df) -> go.Figure:
    """Bubble: Fwd P/E (x) vs EPS Growth % (y), bubble = VG Score, colour = PEG tier."""
    plot = df[df["EPS Gr %"].notna()].head(40)
    colors = [
        _YEL if (r["PEG"] and r["PEG"] < 1)
        else UP if (r["PEG"] and r["PEG"] < 2)
        else MUT
        for _, r in plot.iterrows()
    ]
    fig = go.Figure(go.Scatter(
        x=plot["Fwd P/E"],
        y=plot["EPS Gr %"],
        mode="markers+text",
        text=plot["Ticker"],
        textposition="top center",
        textfont=dict(size=8),
        marker=dict(
            size=(plot["VG Score"] / plot["VG Score"].max() * 20 + 8).tolist(),
            color=colors, opacity=0.85,
            line=dict(color="#FFFFFF", width=0.5),
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Fwd P/E: %{x:.1f}<br>"
            "EPS Growth: %{y:.1f}%<extra></extra>"
        ),
    ))
    fig.update_layout(
        template="plotly_dark", height=320,
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(title="Forward P/E (lower = cheaper)"),
        yaxis=dict(title="EPS Growth % (higher = faster)", ticksuffix="%"),
        showlegend=False,
    )
    return fig


def forward_pe_sector_bar(df) -> go.Figure:
    """Horizontal bar: avg VG Score per sector with avg P/E annotation."""
    sector_df = (
        df.groupby("Sector")
        .agg(Count=("Ticker", "count"), Avg_Score=("VG Score", "mean"), Avg_PE=("Fwd P/E", "mean"))
        .reset_index()
        .sort_values("Avg_Score", ascending=True)
    )
    fig = go.Figure(go.Bar(
        x=sector_df["Avg_Score"],
        y=sector_df["Sector"],
        orientation="h",
        marker_color=_BLU,
        text=sector_df.apply(
            lambda r: f"{int(r['Count'])} stocks · avg P/E {r['Avg_PE']:.1f}", axis=1
        ),
        textposition="inside",
        hovertemplate="<b>%{y}</b><br>Avg VG Score: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark",
        height=max(200, len(sector_df) * 40),
        margin=dict(l=20, r=40, t=10, b=40),
        xaxis=dict(title="Avg Value Growth Score"),
        yaxis=dict(title=""),
        showlegend=False,
    )
    return fig


# ── Candle Momentum Screener ──────────────────────────────────────────────────

# Signal tiers share colours with the screener page; defined here so the chart
# function is self-contained (screener keeps its own copy for UI labels).
_CANDLE_TIER_COLORS = {
    "🟢 Strong Buy": UP,
    "🟢 Buy":        _LGN,
    "🟡 Accumulate": _YEL,
    "🟠 Caution":    _ORG,
    "🔴 Sell":       DN,
}
_CANDLE_SIGNAL_TIERS = list(_CANDLE_TIER_COLORS.keys())


def candle_momentum_sector_chart(df) -> go.Figure:
    """Stacked bar: signal distribution per sector."""
    sector_signal = (
        df[df["Sector"] != "—"]
        .groupby(["Sector", "Signal"])
        .size()
        .reset_index(name="Count")
    )
    fig = go.Figure()
    for signal in reversed(_CANDLE_SIGNAL_TIERS):
        sub = sector_signal[sector_signal["Signal"] == signal]
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            name=signal,
            x=sub["Sector"],
            y=sub["Count"],
            marker_color=_CANDLE_TIER_COLORS[signal],
            hovertemplate=f"<b>%{{x}}</b><br>{signal}: %{{y}}<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack",
        template="plotly_dark", height=360,
        margin=dict(l=20, r=20, t=20, b=80),
        legend=dict(orientation="h", y=1.08, x=0),
        xaxis=dict(title="", tickangle=-30),
        yaxis=dict(title="# Stocks"),
    )
    return fig


# ── VIX / Volatility ─────────────────────────────────────────────────────────

def vix_spy_chart(df) -> go.Figure:
    """Dual-axis: SPY price (left) + VIX line with MAs and zone bands (right)."""
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
        line=dict(color=_BLU, width=2),
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
        line=dict(color=NEU, width=1.5),
        fill="tonexty", fillcolor="rgba(245,158,11,0.10)",
        hovertemplate="VIX: <b>%{y:.2f}</b><extra></extra>",
    ), secondary_y=True)

    ma_colors = {5: "#A78BFA", 20: "#34D399", 50: _BLU, 100: "#F87171"}
    for period, color in ma_colors.items():
        if len(df) >= period:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["VIX"].rolling(period).mean(),
                name=f"VIX MA{period}", mode="lines",
                line=dict(color=color, width=1.2, dash="dot"),
                hovertemplate=f"MA{period}: <b>%{{y:.2f}}</b><extra></extra>",
            ), secondary_y=True)

    for level, color, label in [
        (15, UP,  "15 Calm"),
        (20, NEU, "20 Elevated"),
        (30, DN,  "30 Fear"),
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
