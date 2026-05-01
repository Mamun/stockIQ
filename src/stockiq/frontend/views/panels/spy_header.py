"""SPY dashboard header: price badge (left) + major-index strip (right)."""

import pandas as pd
import streamlit as st


def render_spy_header(quote: dict, idx_df: pd.DataFrame) -> None:
    price   = quote["price"]
    chg     = quote["change"]
    chg_pct = quote["change_pct"]
    clr     = "#22C55E" if chg >= 0 else "#EF4444"
    arrow   = "▲" if chg >= 0 else "▼"

    ts = quote.get("_ts", 0)
    if ts:
        as_of = (
            pd.Timestamp(ts, unit="s", tz="UTC")
            .tz_convert("America/New_York")
            .strftime("%-I:%M %p ET · %b %-d")
        )
    else:
        as_of = "time unknown"

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
    as of {as_of} · refreshes every 60 s
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    with indices_col:
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
