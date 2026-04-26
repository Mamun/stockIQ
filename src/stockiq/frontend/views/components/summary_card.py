"""
Reusable price + technicals summary card.

Consolidated from two near-identical implementations in analyzer.py and
spy_dashboard.py. Provides:
  - render_stock_summary_card(): for individual stock analysis (with signal score)
  - render_spy_summary_card():   for the SPY live dashboard (uses live quote)
"""

import pandas as pd
import streamlit as st

from stockiq.frontend.theme import BG as _BG
from stockiq.frontend.theme import DN as _DN
from stockiq.frontend.theme import MUT as _MUT
from stockiq.frontend.theme import NEU as _NEU
from stockiq.frontend.theme import SEP as _SEP
from stockiq.frontend.theme import UP as _UP
from stockiq.frontend.theme import VAL as _VAL


def _cell(label: str, value: str, sub: str = "", sub_clr: str | None = None) -> str:
    sub_html = (
        f'<div style="font-size:11px;color:{sub_clr or _MUT};margin-top:2px;white-space:nowrap">{sub}</div>'
        if sub else '<div style="font-size:11px">&nbsp;</div>'
    )
    return (
        f'<div style="padding:10px 18px;border-right:1px solid {_SEP};'
        f'display:flex;flex-direction:column;justify-content:center;flex:1;min-width:80px">'
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
    rsi: float | None = None,
    vix_snapshot: dict | None = None,
    pc_data: dict | None = None,
) -> None:
    """
    SPY technical snapshot — single row.
    Optionally prepends signal cells (RSI, VIX, P/C) when provided.
    """
    ma5 = ma50 = ma100 = ma200 = cross_label = cross_clr = None
    vol_avg_20d = None

    if not daily_df.empty:
        def _ma(p):
            return float(daily_df["Close"].rolling(p).mean().iloc[-1]) if len(daily_df) >= p else None

        ma5   = _ma(5)
        ma50  = _ma(50)
        ma100 = _ma(100)
        ma200 = _ma(200)
        if ma50 and ma200:
            cross_label = "🌟 Golden Cross" if ma50 > ma200 else "💀 Death Cross"
            cross_clr   = _UP if ma50 > ma200 else _DN

        if "Volume" in daily_df.columns and len(daily_df) >= 20:
            vol_avg_20d = float(daily_df["Volume"].rolling(20).mean().iloc[-1])

    w52_hi  = quote.get("w52_high", 0) or 0
    w52_lo  = quote.get("w52_low",  0) or 0
    vol_now = quote.get("volume",   0) or 0

    # ── 52W range gauge (compact inline) ─────────────────────────────────────
    if w52_hi > w52_lo and price:
        pos_pct     = (price - w52_lo) / (w52_hi - w52_lo) * 100
        pct_from_hi = (price / w52_hi - 1) * 100
        bar_filled  = max(2, min(98, round(pos_pct)))
        bar_clr     = _UP if pos_pct >= 50 else _DN
        range_cell  = (
            f'<div style="padding:8px 18px;border-right:1px solid {_SEP};flex:1;min-width:180px">'
            f'<div style="font-size:11px;color:{_MUT};text-transform:uppercase;'
            f'letter-spacing:.05em;margin-bottom:5px">52W Range</div>'
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
            f'  <span style="font-size:10px;color:{_MUT};white-space:nowrap">${w52_lo:,.0f}</span>'
            f'  <div style="width:90px;height:5px;border-radius:3px;background:#1E293B;'
            f'flex-shrink:0;position:relative">'
            f'    <div style="width:{bar_filled}%;height:100%;border-radius:3px;'
            f'background:{bar_clr}"></div>'
            f'    <div style="position:absolute;top:-3px;left:{bar_filled}%;'
            f'transform:translateX(-50%);width:2px;height:11px;background:#F1F5F9;'
            f'border-radius:1px"></div>'
            f'  </div>'
            f'  <span style="font-size:10px;color:{_MUT};white-space:nowrap">${w52_hi:,.0f}</span>'
            f'</div>'
            f'<div style="font-size:14px;font-weight:700;color:{_VAL}">'
            f'  {pos_pct:.1f}%'
            f'  <span style="font-size:11px;color:{_MUT};font-weight:400">'
            f'  &nbsp;within range &nbsp;·&nbsp; {pct_from_hi:+.1f}% vs hi</span>'
            f'</div>'
            f'</div>'
        )
    else:
        range_cell = ""

    # ── Volume vs 20D avg ─────────────────────────────────────────────────────
    if vol_now and vol_avg_20d:
        vol_vs_avg = (vol_now / vol_avg_20d - 1) * 100
        vol_clr    = _UP if vol_vs_avg >= 20 else _DN if vol_vs_avg <= -20 else _MUT
        vol_cell   = _cell("Volume", f"{vol_now/1_000_000:.1f}M",
                           f"{vol_vs_avg:+.0f}% vs 20D avg", vol_clr)
    elif vol_now:
        vol_cell   = _cell("Volume", f"{vol_now/1_000_000:.1f}M")
    else:
        vol_cell   = _cell("Volume", "—")

    # ── MA alignment ──────────────────────────────────────────────────────────
    cross_cell = _cell("MA Trend", cross_label, "MA50 vs MA200", cross_clr) if cross_label else ""

    # ── Optional signal cells (RSI · VIX · P/C) ──────────────────────────────
    signal_cells = ""

    if rsi is not None:
        if rsi < 30:
            rc, rs = _UP,  "Oversold"
        elif rsi < 45:
            rc, rs = "#86EFAC", "Weak"
        elif rsi < 55:
            rc, rs = _MUT, "Neutral"
        elif rsi < 70:
            rc, rs = "#FCD34D", "Strong"
        else:
            rc, rs = _DN,  "Overbought"
        signal_cells += _cell("RSI (14d)", f"{rsi:.1f}", rs, rc)

    if vix_snapshot:
        _VZ_CLR = {"Calm": _UP, "Normal": "#86EFAC",
                   "Elevated": _NEU, "Extreme Fear": _DN}
        vix_now  = vix_snapshot.get("current")
        vix_zone = vix_snapshot.get("zone", "")
        if vix_now and vix_zone:
            vc = _VZ_CLR.get(vix_zone, _MUT)
            signal_cells += _cell("VIX", f"{vix_now:.2f}", vix_zone, vc)

    if pc_data:
        short_sig = pc_data["signal"].split("—")[0].strip() if "—" in pc_data["signal"] else pc_data["signal"]
        signal_cells += _cell("P/C Daily", f"{pc_data['ratio']:.3f}", short_sig, pc_data["color"])

    # ── Single combined row ───────────────────────────────────────────────────
    single_row = "".join([
        signal_cells,
        range_cell,
        vol_cell,
        cross_cell,
        _ma_cell("MA 5",   ma5,   price) if ma5   else "",
        _ma_cell("MA 50",  ma50,  price) if ma50  else "",
        _ma_cell("MA 100", ma100, price) if ma100 else "",
        _ma_cell("MA 200", ma200, price) if ma200 else "",
    ])

    row_style = f"display:flex;flex-wrap:nowrap;background:{_BG};width:100%"
    st.markdown(
        f'<div style="background:{_BG};border:1px solid {_SEP};border-radius:8px;'
        f'overflow:hidden;margin-bottom:4px;width:100%">'
        f'<div style="{row_style}">{single_row}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
