import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from stockiq.config import MA_COLORS, MA200W_COLOR, MA_PERIODS, FIB_COLORS, REVERSAL_PATTERNS


def build_chart(
    df: pd.DataFrame,
    fib_levels: dict,
    ticker: str,
    show_vol: bool,
    show_fib: bool,
    show_patterns: bool,
    show_rsi: bool = False,
    golden_dates=(),
    death_dates=(),
) -> go.Figure:
    # Determine subplot layout
    if show_vol and show_rsi:
        rows, row_heights = 3, [0.55, 0.2, 0.25]
        vol_row, rsi_row  = 2, 3
    elif show_vol:
        rows, row_heights = 2, [0.7, 0.3]
        vol_row, rsi_row  = 2, None
    elif show_rsi:
        rows, row_heights = 2, [0.7, 0.3]
        vol_row, rsi_row  = None, 2
    else:
        rows, row_heights = 1, [1.0]
        vol_row, rsi_row  = None, None

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name=ticker,
        increasing_line_color="#22C55E",
        decreasing_line_color="#EF4444",
    ), row=1, col=1)

    # Daily moving averages
    for p in MA_PERIODS:
        col = f"MA{p}"
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                name=f"MA{p}",
                line=dict(color=MA_COLORS[p], width=1.5),
                hovertemplate=f"MA{p}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # 200-week MA (forward-filled to daily)
    if "MA200W" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA200W"],
            name="MA200W",
            line=dict(color=MA200W_COLOR, width=2.5, dash="dash"),
            hovertemplate="MA200W: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    # Golden / Death cross markers
    if len(golden_dates):
        fig.add_trace(go.Scatter(
            x=golden_dates,
            y=df.loc[golden_dates, "MA50"],
            mode="markers+text",
            name="Golden Cross",
            marker=dict(symbol="triangle-up", size=16, color="#FFD700",
                        line=dict(color="#B8860B", width=1)),
            text=["Golden Cross"] * len(golden_dates),
            textposition="top center",
            textfont=dict(color="#FFD700", size=10),
            hovertemplate="Golden Cross<br>%{x|%Y-%m-%d}<br>MA50: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if len(death_dates):
        fig.add_trace(go.Scatter(
            x=death_dates,
            y=df.loc[death_dates, "MA50"],
            mode="markers+text",
            name="Death Cross",
            marker=dict(symbol="triangle-down", size=16, color="#FF4444",
                        line=dict(color="#8B0000", width=1)),
            text=["Death Cross"] * len(death_dates),
            textposition="bottom center",
            textfont=dict(color="#FF4444", size=10),
            hovertemplate="Death Cross<br>%{x|%Y-%m-%d}<br>MA50: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    # Reversal pattern markers
    if show_patterns:
        for col, label, bullish, symbol, color in REVERSAL_PATTERNS:
            if col not in df.columns:
                continue
            mask = df[col].fillna(False)
            if not mask.any():
                continue

            if bullish is True:
                y_values = df.loc[mask, "Low"] * 0.985
            elif bullish is False:
                y_values = df.loc[mask, "High"] * 1.015
            else:
                y_values = df.loc[mask, "Close"]

            fig.add_trace(go.Scatter(
                x=df.index[mask],
                y=y_values,
                mode="markers",
                name=label,
                marker=dict(symbol=symbol, size=14, color=color,
                            line=dict(color="#FFFFFF", width=1)),
                hovertemplate=f"{label}<br>%{{x|%Y-%m-%d}}<br>Close: $%{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # Fibonacci retracement lines
    if show_fib:
        for (label, price), color in zip(fib_levels.items(), FIB_COLORS):
            fig.add_hline(
                y=price, line_dash="dot", line_color=color, line_width=1,
                annotation_text=f"Fib {label}  ${price:.2f}",
                annotation_position="right",
                annotation_font_size=10,
                row=1, col=1,
            )

    # Volume bars
    if show_vol and vol_row:
        colors = ["#22C55E" if c >= o else "#EF4444"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            name="Volume",
            marker_color=colors,
            showlegend=False,
        ), row=vol_row, col=1)

    # RSI subplot
    if show_rsi and rsi_row and "RSI" in df.columns:
        rsi = df["RSI"]
        fig.add_trace(go.Scatter(
            x=df.index, y=rsi,
            name="RSI (14)",
            line=dict(color="#A78BFA", width=1.5),
            hovertemplate="RSI: %{y:.1f}<extra></extra>",
        ), row=rsi_row, col=1)

        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.08)",
                      line_width=0, row=rsi_row, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(34,197,94,0.08)",
                      line_width=0, row=rsi_row, col=1)

        for level, label, color in [(70, "OB 70", "#EF4444"),
                                     (50, "50",    "#64748B"),
                                     (30, "OS 30", "#22C55E")]:
            fig.add_hline(y=level, line_dash="dot", line_color=color,
                          line_width=1, annotation_text=label,
                          annotation_position="right",
                          annotation_font_size=9,
                          row=rsi_row, col=1)

        fig.update_yaxes(title_text="RSI", range=[0, 100],
                         row=rsi_row, col=1)

    height = 700 + (150 if show_rsi else 0)
    fig.update_layout(
        template="plotly_dark",
        height=height,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(l=40, r=120, t=40, b=40),
    )
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    if show_vol and vol_row:
        fig.update_yaxes(title_text="Volume", row=vol_row, col=1)

    return fig
