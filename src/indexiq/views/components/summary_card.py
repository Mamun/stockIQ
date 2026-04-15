"""
Reusable price + technicals summary card.

Consolidated from two near-identical implementations in analyzer.py and
spy_dashboard.py. Provides:
  - render_stock_summary_card(): for individual stock analysis (with signal score)
  - render_spy_summary_card():   for the SPY live dashboard (uses live quote)
"""

import pandas as pd
import streamlit as st

# ── Shared colour palette ──────────────────────────────────────────────────────
_UP  = "#22C55E"
_DN  = "#EF4444"
_NEU = "#F59E0B"
_MUT = "#64748B"
_VAL = "#F1F5F9"
_BG  = "#0F172A"
_SEP = "#1E293B"


def _cell(label: str, value: str, sub: str = "", sub_clr: str | None = None) -> str:
    sub_html = (
        f'<div style="font-size:11px;color:{sub_clr or _MUT};margin-top:2px;white-space:nowrap">{sub}</div>'
        if sub else '<div style="font-size:11px">&nbsp;</div>'
    )
    return (
        f'<div style="padding:10px 18px;border-right:1px solid {_SEP};'
        f'display:flex;flex-direction:column;justify-content:center">'
        f'<div style="font-size:11px;color:{_MUT};text-transform:uppercase;'
        f'letter-spacing:.05em;white-space:nowrap">{label}</div>'
        f'<div style="font-size:17px;font-weight:700;color:{_VAL};white-space:nowrap">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def _ma_cell(label: str, val: float | None, price: float) -> str:
    if not val:
        return ""
    diff = (price - val) / val * 100
    clr  = _UP if diff >= 0 else _DN
    return _cell(label, f"${val:,.2f}", f"{diff:+.2f}% vs price", clr)


def _render_card(price_row: str, tech_row: str) -> None:
    row_style = f"display:flex;flex-wrap:wrap;background:{_BG};border-bottom:1px solid {_SEP}"
    st.markdown(
        f'<div style="background:{_BG};border:1px solid {_SEP};border-radius:8px;'
        f'overflow:hidden;margin-bottom:8px">'
        f'<div style="{row_style}">{price_row}</div>'
        f'<div style="{row_style};border-bottom:none">{tech_row}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_stock_summary_card(
    latest: pd.Series,
    prev: pd.Series,
    df: pd.DataFrame,
    signal_label: str,
    signal_color: str,
    score: int,
) -> None:
    """Two-row overview card for the Stock Analyzer page."""
    price      = float(latest["Close"])
    prev_close = float(prev["Close"])
    chg        = price - prev_close
    chg_pct    = chg / prev_close * 100
    high       = float(latest.get("High",   0) or 0)
    low        = float(latest.get("Low",    0) or 0)
    vol        = float(latest.get("Volume", 0) or 0)

    last_252 = df.tail(252)
    w52_high = float(last_252["High"].max())
    w52_low  = float(last_252["Low"].min())

    rsi_val = float(latest.get("RSI",    0) or 0)
    ma5     = float(latest.get("MA5",    0) or 0)
    ma50    = float(latest.get("MA50",   0) or 0)
    ma200   = float(latest.get("MA200",  0) or 0)
    ma200w  = float(latest.get("MA200W", 0) or 0)

    cross_label = cross_clr = None
    if ma50 and ma200:
        cross_label = "🌟 Golden Cross" if ma50 > ma200 else "💀 Death Cross"
        cross_clr   = _UP if ma50 > ma200 else _DN

    # Row 1 — price data
    chg_clr   = _UP if chg >= 0 else _DN
    arrow     = "▲" if chg >= 0 else "▼"
    price_row = "".join([
        _cell("Last Close", f"${price:,.2f}", f"{arrow} {abs(chg):.2f} ({chg_pct:+.2f}%)", chg_clr),
        _cell("Prev Close", f"${prev_close:,.2f}"),
        _cell("Day High",   f"${high:,.2f}"    if high    else "—"),
        _cell("Day Low",    f"${low:,.2f}"     if low     else "—"),
        _cell("52W High",   f"${w52_high:,.2f}" if w52_high else "—"),
        _cell("52W Low",    f"${w52_low:,.2f}"  if w52_low  else "—"),
        _cell("Volume",     f"{vol/1_000_000:.1f}M" if vol else "—"),
    ])

    # Row 2 — technicals
    sig_cell   = _cell("Signal", signal_label, f"Score {score:+d}", signal_color)
    rsi_clr    = _DN if rsi_val >= 70 else _UP if rsi_val <= 30 else _NEU
    rsi_sub    = "Overbought" if rsi_val >= 70 else "Oversold" if rsi_val <= 30 else "Neutral"
    rsi_cell   = _cell("RSI (14)", f"{rsi_val:.1f}", rsi_sub, rsi_clr) if rsi_val else ""
    cross_cell = _cell("MA Trend", cross_label, "MA50 vs MA200", cross_clr) if cross_label else ""

    tech_row = "".join([
        sig_cell,
        rsi_cell,
        cross_cell,
        _ma_cell("MA 5",    ma5,    price),
        _ma_cell("MA 50",   ma50,   price),
        _ma_cell("MA 200",  ma200,  price),
        _ma_cell("MA 200W", ma200w, price),
    ])

    _render_card(price_row, tech_row)


def render_spy_summary_card(
    quote: dict,
    price: float,
    chg: float,
    chg_pct: float,
    daily_df: pd.DataFrame,
) -> None:
    """Two-row overview card for the SPY Live Dashboard."""
    rsi_val = ma5 = ma50 = ma100 = ma200 = cross_label = cross_clr = None
    if not daily_df.empty:
        from indexiq.models.indicators import compute_rsi
        rsi_val = float(compute_rsi(daily_df).iloc[-1])

        def _ma(p):
            return float(daily_df["Close"].rolling(p).mean().iloc[-1]) if len(daily_df) >= p else None

        ma5   = _ma(5)
        ma50  = _ma(50)
        ma100 = _ma(100)
        ma200 = _ma(200)
        if ma50 and ma200:
            cross_label = "🌟 Golden Cross" if ma50 > ma200 else "💀 Death Cross"
            cross_clr   = _UP if ma50 > ma200 else _DN

    # Row 1 — price data
    chg_clr    = _UP if chg >= 0 else _DN
    arrow      = "▲" if chg >= 0 else "▼"
    vol        = quote.get("volume", 0)
    prev_close = quote.get("prev_close", 0)

    price_row = "".join([
        _cell("SPY Price",  f"{price:,.2f}", f"{arrow} {abs(chg):.2f} ({chg_pct:+.2f}%)", chg_clr),
        _cell("Prev Close", f"{prev_close:,.2f}" if prev_close else "—"),
        _cell("Day High",   f"{quote['day_high']:,.2f}" if quote["day_high"] else "—"),
        _cell("Day Low",    f"{quote['day_low']:,.2f}"  if quote["day_low"]  else "—"),
        _cell("52W High",   f"{quote['w52_high']:,.2f}" if quote["w52_high"] else "—"),
        _cell("52W Low",    f"{quote['w52_low']:,.2f}"  if quote["w52_low"]  else "—"),
        _cell("Volume",     f"{vol/1_000_000:.1f}M"     if vol else "—"),
    ])

    # Row 2 — technicals
    if rsi_val is not None:
        rsi_clr  = _DN if rsi_val >= 70 else _UP if rsi_val <= 30 else _NEU
        rsi_sub  = "Overbought" if rsi_val >= 70 else "Oversold" if rsi_val <= 30 else "Neutral"
        rsi_cell = _cell("RSI (14)", f"{rsi_val:.1f}", rsi_sub, rsi_clr)
    else:
        rsi_cell = ""

    cross_cell = _cell("MA Trend", cross_label, "MA50 vs MA200", cross_clr) if cross_label else ""

    tech_row = "".join([
        rsi_cell,
        cross_cell,
        _ma_cell("MA 5",   ma5,   price) if ma5   else "",
        _ma_cell("MA 50",  ma50,  price) if ma50  else "",
        _ma_cell("MA 100", ma100, price) if ma100 else "",
        _ma_cell("MA 200", ma200, price) if ma200 else "",
    ])

    _render_card(price_row, tech_row)
