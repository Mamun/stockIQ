"""SPY chart panel: period selector, VWAP + key-level computation, chart render."""

import pandas as pd
import streamlit as st

from stockiq.backend.services.spy_service import get_spy_chart_df, get_spy_options_analysis
from stockiq.frontend.views.components.spy_charts import spy_candle_chart


def render_spy_chart_section(quote: dict) -> None:
    # Tuple: (yf_period, interval, MA_periods, show_prev_close, tail_n)
    # tail_n: trim the full fetch to the last N candles; None = show all.
    # "1H"/"2H" fetch a full day of 1m bars so VWAP cumulates correctly from open,
    # then slice to the last 60/120 candles for display.
    period_map = {
        "1H":    ("1d",  "1m",  [],            True,  60),
        "2H":    ("1d",  "1m",  [],            True,  120),
        "Today": ("1d",  "5m",  [],            True,  None),
        "5D":    ("5d",  "30m", [],            True,  None),
        "1M":    ("1mo", "1d",  [20],          False, None),
        "3M":    ("3mo", "1d",  [20, 50],      False, None),
        "6M":    ("6mo", "1d",  [20, 50, 200], False, None),
        "1Y":    ("1y",  "1d",  [20, 50, 200], False, None),
    }
    keys = list(period_map)
    _qp  = st.query_params.get("period", "1Y")
    default_idx = keys.index(_qp) if _qp in keys else keys.index("1Y")

    choice = st.radio("Period", keys, horizontal=True, key="spy_period", index=default_idx)
    st.query_params["period"] = choice

    ck = st.columns(5)
    show_rsi     = ck[0].checkbox("RSI",     value=True, key="spy_show_rsi")
    show_vwap    = ck[1].checkbox("VWAP",    value=True, key="spy_show_vwap")
    show_or      = ck[2].checkbox("OR",      value=True, key="spy_show_or")
    show_levels  = ck[3].checkbox("Levels",  value=True, key="spy_show_levels")
    show_options = ck[4].checkbox("Options", value=True, key="spy_show_options")

    yf_period, interval, mas, show_prev, tail_n = period_map[choice]
    full_df = get_spy_chart_df(period=yf_period, interval=interval)
    if full_df.empty:
        st.info("Chart data unavailable — the market may be closed or data is delayed.")
        return

    chart_df = full_df.iloc[-tail_n:] if tail_n and len(full_df) >= tail_n else full_df

    prev_close_line = quote["prev_close"] if show_prev else None

    vwap = vwap_u1 = vwap_l1 = vwap_u2 = vwap_l2 = None
    if show_vwap and choice in ("1H", "2H", "Today") and "Volume" in full_df.columns and not full_df["Volume"].isna().all():
        vwap_full, u1_full, l1_full, u2_full, l2_full = _compute_vwap_bands(full_df)
        if tail_n:
            vwap    = vwap_full.iloc[-tail_n:]
            vwap_u1 = u1_full.iloc[-tail_n:]
            vwap_l1 = l1_full.iloc[-tail_n:]
            vwap_u2 = u2_full.iloc[-tail_n:]
            vwap_l2 = l2_full.iloc[-tail_n:]
        else:
            vwap, vwap_u1, vwap_l1, vwap_u2, vwap_l2 = vwap_full, u1_full, l1_full, u2_full, l2_full

    pdh = pdl = pivot = r1 = s1 = None
    if show_levels and choice in ("1H", "2H", "Today", "5D"):
        pdh, pdl, pivot, r1, s1 = _compute_pivot_levels()

    or_high = or_low = None
    if show_or and choice in ("1H", "2H") and len(full_df) >= 15:
        _or = full_df.head(15)          # 9:30–9:44 AM at 1m = 15 candles
        or_high = float(_or["High"].max())
        or_low  = float(_or["Low"].min())
    elif show_or and choice == "Today" and len(chart_df) >= 3:
        _or = chart_df.head(3)          # 9:30–9:44 AM at 5m = 3 candles
        or_high = float(_or["High"].max())
        or_low  = float(_or["Low"].min())

    max_pain = call_wall = put_wall = None
    if show_options:
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
        spy_candle_chart(
            chart_df, mas, prev_close_line, show_rsi=show_rsi,
            vwap=vwap, max_pain=max_pain,
            call_wall=call_wall, put_wall=put_wall,
            or_high=or_high, or_low=or_low,
            pdh=pdh, pdl=pdl, pivot=pivot, r1=r1, s1=s1,
            vwap_u1=vwap_u1, vwap_l1=vwap_l1,
            vwap_u2=vwap_u2, vwap_l2=vwap_l2,
        ),
        width="stretch",
    )


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
