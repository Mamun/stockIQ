"""SPY chart panel: period selector, VWAP + key-level computation, chart render."""

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from stockiq.backend.services.spy_service import get_spy_chart_df, get_spy_options_analysis
from stockiq.frontend.views.components.spy_charts import spy_sparkline

_TV_WIDGET_HTML = """
<div id="tv_chart" style="height:560px;width:100%;background:#0e1117;border-radius:6px;overflow:hidden;">
  <script src="https://s3.tradingview.com/tv.js"></script>
  <script>
  new TradingView.widget({
    autosize:          true,
    symbol:            "AMEX:SPY",
    interval:          "5",
    timezone:          "America/New_York",
    theme:             "dark",
    style:             "1",
    locale:            "en",
    hide_top_toolbar:  false,
    allow_symbol_change: false,
    container_id:      "tv_chart"
  });
  </script>
</div>
"""


def render_spy_chart_section(quote: dict) -> None:
    # Live is TradingView (always-on, real-time).
    # Intraday views are an options-levels map — the unique overlay this app adds.
    # Tuple: (yf_period, interval, show_prev_close, tail_n)
    # tail_n: trim full fetch to last N candles; None = show all.
    # "1H"/"2H" fetch the full day at 1m so VWAP cumulates from open, then slice.
    period_map = {
        "Live":  None,
        "1H":    ("1d",  "1m",  True,  60),
        "2H":    ("1d",  "1m",  True,  120),
        "Today": ("1d",  "5m",  True,  None),
        "5D":    ("5d",  "30m", True,  None),
    }
    _qp    = st.query_params.get("period", "Live")
    _default = _qp if _qp in period_map else "Live"

    choice = st.segmented_control(
        "Chart View", options=list(period_map.keys()),
        default=_default, key="spy_period",
    ) or "Live"
    st.query_params["period"] = choice

    if choice == "Live":
        st.caption("Real-time price action & TA. Switch to an intraday view for the options levels overlay.")
        components.html(_TV_WIDGET_HTML, height=570, scrolling=False)
        return

    st.caption("Options levels map — Max Pain · Call/Put Walls · Expected Move band overlaid on price. Use Live for standard TA.")

    # Toggles: options levels are the differentiator vs TradingView
    ck = st.columns(4)
    show_vwap    = ck[0].checkbox("VWAP",    value=True,  key="spy_show_vwap")
    show_or      = ck[1].checkbox("OR",      value=True,  key="spy_show_or")
    show_levels  = ck[2].checkbox("Levels",  value=True,  key="spy_show_levels")
    show_options = ck[3].checkbox("Options", value=True,  key="spy_show_options")

    yf_period, interval, show_prev, tail_n = period_map[choice]
    full_df = get_spy_chart_df(period=yf_period, interval=interval)
    if full_df.empty:
        st.info("No intraday data — switch to **Live** for a real-time TradingView chart.")
        return

    chart_df = full_df.iloc[-tail_n:] if tail_n and len(full_df) >= tail_n else full_df

    prev_close_line = quote.get("prev_close") if show_prev else None

    vwap = vwap_u1 = vwap_l1 = vwap_u2 = vwap_l2 = None
    _vwap_unavailable = False
    if show_vwap and choice in ("1H", "2H", "Today"):
        if "Volume" in full_df.columns and not full_df["Volume"].isna().all() and full_df["Volume"].sum() > 0:
            vwap_full, u1_full, l1_full, u2_full, l2_full = _compute_vwap_bands(full_df)
            if tail_n:
                vwap    = vwap_full.iloc[-tail_n:]
                vwap_u1 = u1_full.iloc[-tail_n:]
                vwap_l1 = l1_full.iloc[-tail_n:]
                vwap_u2 = u2_full.iloc[-tail_n:]
                vwap_l2 = l2_full.iloc[-tail_n:]
            else:
                vwap, vwap_u1, vwap_l1, vwap_u2, vwap_l2 = vwap_full, u1_full, l1_full, u2_full, l2_full
            if _series_last(vwap) is None:
                _vwap_unavailable = True
        else:
            _vwap_unavailable = True
    elif show_vwap and choice == "5D":
        _vwap_unavailable = True

    pdh = pdl = pivot = r1 = s1 = None
    if show_levels:
        pdh, pdl, pivot, r1, s1 = _compute_pivot_levels()

    or_high = or_low = None
    if show_or and choice in ("1H", "2H") and len(full_df) >= 15:
        _or = full_df.head(15)      # 9:30–9:44 AM at 1m = 15 candles
        or_high = float(_or["High"].max())
        or_low  = float(_or["Low"].min())
    elif show_or and choice == "Today" and len(chart_df) >= 3:
        _or = chart_df.head(3)      # 9:30–9:44 AM at 5m = 3 candles
        or_high = float(_or["High"].max())
        or_low  = float(_or["Low"].min())

    # Options levels — the unique value this chart adds over TradingView
    max_pain = call_wall = put_wall = em_upper = em_lower = None
    try:
        seed = get_spy_options_analysis(expiration="", current_price=quote["price"])
        if seed:
            max_pain = seed["max_pain"]
            oi_df    = seed["oi_df"]
            if not oi_df.empty:
                call_wall = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"])
                put_wall  = float(oi_df.loc[oi_df["put_oi"].idxmax(), "strike"])
            em_s = seed.get("expected_move")
            if em_s and em_s.get("move"):
                em_upper = round(quote["price"] + em_s["move"], 2)
                em_lower = round(quote["price"] - em_s["move"], 2)
    except Exception:
        pass

    st.plotly_chart(spy_sparkline(chart_df, vwap=vwap), use_container_width=True)

    if _vwap_unavailable:
        st.caption("VWAP unavailable — requires live market volume (market hours only).")

    vwap_val    = _series_last(vwap)
    vwap_u1_val = _series_last(vwap_u1)
    vwap_l1_val = _series_last(vwap_l1)
    vwap_u2_val = _series_last(vwap_u2)
    vwap_l2_val = _series_last(vwap_l2)

    _table = _levels_table_html(
        current_price=quote["price"],
        vwap=vwap_val        if show_vwap    else None,
        vwap_u1=vwap_u1_val  if show_vwap    else None,
        vwap_l1=vwap_l1_val  if show_vwap    else None,
        vwap_u2=vwap_u2_val  if show_vwap    else None,
        vwap_l2=vwap_l2_val  if show_vwap    else None,
        or_high=or_high,
        or_low=or_low,
        pdh=pdh              if show_levels   else None,
        pdl=pdl              if show_levels   else None,
        pivot=pivot          if show_levels   else None,
        r1=r1                if show_levels   else None,
        s1=s1                if show_levels   else None,
        prev_close=prev_close_line if show_levels else None,
        max_pain=max_pain    if show_options  else None,
        call_wall=call_wall  if show_options  else None,
        put_wall=put_wall    if show_options  else None,
        em_upper=em_upper    if show_options  else None,
        em_lower=em_lower    if show_options  else None,
    )
    if _table:
        st.html(_table)
    else:
        st.caption("No levels to display — enable at least one overlay above.")


# ── Private helpers ────────────────────────────────────────────────────────────

def _compute_vwap_bands(df: pd.DataFrame):
    tp     = (df["High"] + df["Low"] + df["Close"]) / 3
    cumvol = df["Volume"].cumsum()
    vwap   = (tp * df["Volume"]).cumsum() / cumvol.replace(0, float("nan"))
    tp_dev_sq = ((tp - vwap) ** 2 * df["Volume"]).cumsum()
    vwap_std  = (tp_dev_sq / cumvol.replace(0, float("nan"))).pow(0.5)
    return (
        vwap,
        vwap + vwap_std,     vwap - vwap_std,
        vwap + 2 * vwap_std, vwap - 2 * vwap_std,
    )


def _compute_pivot_levels():
    try:
        daily = get_spy_chart_df(period="5d", interval="1d")
        if len(daily) >= 2:
            pd_row = daily.iloc[-2]
            pdh    = float(pd_row["High"])
            pdl    = float(pd_row["Low"])
            pdc    = float(pd_row["Close"])
            pivot  = (pdh + pdl + pdc) / 3
            return pdh, pdl, pivot, 2 * pivot - pdl, 2 * pivot - pdh
    except Exception:
        pass
    return None, None, None, None, None


def _series_last(s) -> float | None:
    if s is None:
        return None
    try:
        v = s.dropna()
        return float(v.iloc[-1]) if not v.empty else None
    except Exception:
        return None


def _levels_table_html(
    current_price: float,
    vwap=None, vwap_u1=None, vwap_l1=None, vwap_u2=None, vwap_l2=None,
    or_high=None, or_low=None,
    pdh=None, pdl=None, pivot=None, r1=None, s1=None, prev_close=None,
    max_pain=None, call_wall=None, put_wall=None, em_upper=None, em_lower=None,
) -> str:
    # (label, value, dot_color, category_label, category_bg)
    candidates = [
        ("Call Wall",  call_wall,  "#22C55E", "Options",   "#052E16"),
        ("EM +",       em_upper,   "#818CF8", "Options",   "#1E1B4B"),
        ("R1",         r1,         "#86EFAC", "Technical", "#052E16"),
        ("PDH",        pdh,        "#94A3B8", "Technical", "#1E293B"),
        ("OR High",    or_high,    "#FBBF24", "OR",        "#1C1200"),
        ("VWAP +2σ",  vwap_u2,    "#E879F9", "VWAP",      "#2D0A3E"),
        ("VWAP +1σ",  vwap_u1,    "#E879F9", "VWAP",      "#2D0A3E"),
        ("VWAP",       vwap,       "#E879F9", "VWAP",      "#2D0A3E"),
        ("Pivot",      pivot,      "#38BDF8", "Technical", "#082F49"),
        ("Prev Close", prev_close, "#475569", "Technical", "#1E293B"),
        ("VWAP -1σ",  vwap_l1,    "#E879F9", "VWAP",      "#2D0A3E"),
        ("VWAP -2σ",  vwap_l2,    "#E879F9", "VWAP",      "#2D0A3E"),
        ("OR Low",     or_low,     "#FBBF24", "OR",        "#1C1200"),
        ("PDL",        pdl,        "#94A3B8", "Technical", "#1E293B"),
        ("S1",         s1,         "#FDA4AF", "Technical", "#450A0A"),
        ("EM −",       em_lower,   "#818CF8", "Options",   "#1E1B4B"),
        ("Put Wall",   put_wall,   "#EF4444", "Options",   "#450A0A"),
        ("Max Pain",   max_pain,   "#F59E0B", "Options",   "#1C1200"),
    ]
    rows = [(lbl, float(val), dot, cat, cat_bg)
            for lbl, val, dot, cat, cat_bg in candidates if val is not None]
    if not rows:
        return ""

    rows.sort(key=lambda r: r[1], reverse=True)
    insert_idx = next((i for i, r in enumerate(rows) if r[1] < current_price), len(rows))

    def _row(lbl, val, dot, cat, cat_bg):
        dist  = val - current_price
        d_col = "#86EFAC" if dist > 0 else "#FDA4AF"
        arrow = "▲" if dist > 0 else "▼"
        return (
            f'<tr style="border-bottom:1px solid #0F172A;">'
            f'<td style="padding:7px 10px;white-space:nowrap;">'
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            f'background:{dot};margin-right:8px;vertical-align:middle;flex-shrink:0;"></span>'
            f'<span style="color:#E2E8F0;font-size:13px;">{lbl}</span></td>'
            f'<td style="padding:7px 10px;font-size:13px;font-family:monospace;'
            f'color:#F8FAFC;text-align:right;white-space:nowrap;">${val:,.2f}</td>'
            f'<td style="padding:7px 10px;font-size:12px;color:{d_col};'
            f'text-align:right;white-space:nowrap;font-family:monospace;">'
            f'{arrow} ${abs(dist):,.2f}</td>'
            f'<td style="padding:7px 10px;text-align:right;">'
            f'<span style="font-size:10px;padding:2px 7px;border-radius:4px;'
            f'background:{cat_bg};color:#CBD5E1;">{cat}</span></td></tr>'
        )

    _price_sep = (
        f'<tr style="background:#172554;border-top:2px solid #3B82F6;border-bottom:2px solid #3B82F6;">'
        f'<td colspan="4" style="padding:6px 10px;">'
        f'<span style="color:#93C5FD;font-size:11px;font-weight:600;letter-spacing:0.06em;">▶ PRICE NOW</span>'
        f'<span style="color:#60A5FA;font-size:14px;font-weight:700;font-family:monospace;'
        f'margin-left:12px;">${current_price:,.2f}</span>'
        f'</td></tr>'
    )

    html_rows: list[str] = []
    for i, r in enumerate(rows):
        if i == insert_idx:
            html_rows.append(_price_sep)
        html_rows.append(_row(*r))
    if insert_idx == len(rows):
        html_rows.append(_price_sep)

    header = (
        '<tr style="border-bottom:1px solid #1E293B;">'
        '<th style="padding:6px 10px;text-align:left;font-size:10px;color:#64748B;'
        'font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Level</th>'
        '<th style="padding:6px 10px;text-align:right;font-size:10px;color:#64748B;'
        'font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Price</th>'
        '<th style="padding:6px 10px;text-align:right;font-size:10px;color:#64748B;'
        'font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Dist</th>'
        '<th style="padding:6px 10px;text-align:right;font-size:10px;color:#64748B;'
        'font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Type</th>'
        '</tr>'
    )

    return (
        '<div style="background:#0B1120;border:1px solid #1E293B;border-radius:10px;'
        'overflow:hidden;margin-top:6px;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead>{header}</thead>'
        f'<tbody>{"".join(html_rows)}</tbody>'
        '</table></div>'
    )
