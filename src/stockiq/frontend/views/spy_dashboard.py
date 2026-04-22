import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from stockiq.backend.services.market_service import get_market_overview
from stockiq.backend.services.spy_service import (
    get_put_call_ratio,
    get_spy_chart_df,
    get_spy_gap_table_data,
    get_spy_options_analysis,
    get_spy_quote,
)
from stockiq.frontend.views.ai_forecast import render_ai_forecast
from stockiq.frontend.views.components.gap_table import render_gap_table
from stockiq.frontend.views.components.summary_card import render_spy_summary_card


# ── Main dashboard tab ─────────────────────────────────────────────────────────

def render_spy_dashboard_tab() -> None:
    quote = get_spy_quote()
    if not quote:
        st.error("Could not load SPY data. Please try again in a moment.")
        return
    overview = get_market_overview()
    gap_data = get_spy_gap_table_data()

    # ── 1. Compact page header + index strip ─────────────────────────────────
    _render_header(quote, overview["indices"])

    # ── 2. SPY snapshot + signal cells (RSI · VIX · P/C · MAs) ─────────────
    _rsi, _pc = None, None
    try:
        _daily = get_spy_chart_df(period="1y", interval="1d")
        if not _daily.empty and "RSI" in _daily.columns:
            _rsi_s = _daily["RSI"].dropna()
            if not _rsi_s.empty:
                _rsi = float(_rsi_s.iloc[-1])
    except Exception:
        pass
    try:
        _pc = get_put_call_ratio(scope="daily")
    except Exception:
        pass

    render_spy_summary_card(
        quote, quote["price"], quote["change"], quote["change_pct"],
        gap_data["daily_df"],
        rsi=_rsi,
        vix_snapshot=overview["vix"],
        pc_data=_pc,
    )

    st.divider()

    # ── 4. SPY chart (VWAP intraday · options levels daily) ──────────────────
    _render_spy_chart_section(quote)

    st.divider()

    # ── 5. Options Intelligence — Max Pain · OI · P/C (moved up) ─────────────
    _render_options_section(quote["price"])

    st.divider()

    # ── 6. AI Forecast slot ───────────────────────────────────────────────────
    ai_slot = st.empty()

    st.divider()

    # ── 7. SPY gap table ──────────────────────────────────────────────────────
    _render_spy_gap_table(gap_data)

    # ── Fill AI slot last ─────────────────────────────────────────────────────
    try:
        with ai_slot.container():
            render_ai_forecast(gap_data["gaps_df"], gap_data["quote"])
    except Exception:
        pass


# ── Private helpers ────────────────────────────────────────────────────────────

def _render_header(quote: dict, idx_df: pd.DataFrame) -> None:
    """Compact page header: SPY price badge left, index strip right."""
    price   = quote["price"]
    chg     = quote["change"]
    chg_pct = quote["change_pct"]
    clr     = "#22C55E" if chg >= 0 else "#EF4444"
    arrow   = "▲" if chg >= 0 else "▼"

    ts = quote.get("_ts", 0)
    if ts:
        import pytz
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


def _render_spy_chart_section(quote: dict) -> None:
    """SPY candlestick: VWAP on Today view, options levels (max pain + walls) on daily views."""
    period_map = {
        "Today": ("1d",  "5m",  [],            True),
        "5D":    ("5d",  "30m", [],            True),
        "1M":    ("1mo", "1d",  [20],          False),
        "3M":    ("3mo", "1d",  [20, 50],      False),
        "6M":    ("6mo", "1d",  [20, 50, 200], False),
        "1Y":    ("1y",  "1d",  [20, 50, 200], False),
    }
    spy_period_keys = list(period_map)
    _spy_qp = st.query_params.get("period", "1Y")
    spy_default_idx = spy_period_keys.index(_spy_qp) if _spy_qp in spy_period_keys else 5

    period_col, rsi_col = st.columns([6, 1])
    with period_col:
        choice = st.radio("Period", spy_period_keys, horizontal=True,
                          key="spy_period", index=spy_default_idx)
    show_rsi = rsi_col.checkbox("RSI", value=True)
    st.query_params["period"] = choice

    yf_period, interval, mas, show_prev = period_map[choice]
    chart_df = get_spy_chart_df(period=yf_period, interval=interval)
    if chart_df.empty:
        st.info("Chart data unavailable — the market may be closed or data is delayed.")
        return

    prev = quote["prev_close"] if show_prev else None

    # VWAP for Today intraday view only
    vwap = None
    if choice == "Today" and "Volume" in chart_df.columns and not chart_df["Volume"].isna().all():
        tp   = (chart_df["High"] + chart_df["Low"] + chart_df["Close"]) / 3
        cumvol = chart_df["Volume"].cumsum()
        vwap   = (tp * chart_df["Volume"]).cumsum() / cumvol.replace(0, float("nan"))

    # Max pain + call/put walls for daily+ views (cached options fetch)
    max_pain = call_wall = put_wall = None
    if not show_prev:
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
        _spy_chart(chart_df, mas, prev, show_rsi=show_rsi,
                   vwap=vwap, max_pain=max_pain,
                   call_wall=call_wall, put_wall=put_wall),
        width="stretch",
    )


def _render_spy_gap_table(gap_data: dict) -> None:
    gaps_df = gap_data["gaps_df"]
    try:
        parsed    = urllib.parse.urlparse(st.context.url)
        share_url = f"{parsed.scheme}://{parsed.netloc}/spy-gaps"
    except Exception:
        share_url = "/spy-gaps"

    render_gap_table(gaps_df, title="Daily Gaps (Last 30 Days)",
                     show_rsi=True, show_next_day=True, share_url=share_url)



def _spy_chart(
    df,
    ma_periods: list,
    prev_close: float | None = None,
    show_rsi: bool = False,
    vwap: pd.Series | None = None,
    max_pain: float | None = None,
    call_wall: float | None = None,
    put_wall: float | None = None,
) -> go.Figure:
    """Candlestick + volume + optional RSI + VWAP + options levels."""
    if show_rsi:
        rows, row_heights = 3, [0.55, 0.2, 0.25]
        vol_row, rsi_row  = 2, 3
    else:
        rows, row_heights = 2, [0.75, 0.25]
        vol_row, rsi_row  = 2, None

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        row_heights=row_heights, vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing_line_color="#22C55E", decreasing_line_color="#EF4444",
        name="SPY", showlegend=False,
    ), row=1, col=1)

    ma_colors = {20: "#F59E0B", 50: "#3B82F6", 200: "#EF4444"}
    for p in ma_periods:
        if len(df) >= p:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"].rolling(p).mean(),
                mode="lines", line=dict(color=ma_colors[p], width=1.5),
                name=f"MA{p}",
            ), row=1, col=1)

    if vwap is not None:
        fig.add_trace(go.Scatter(
            x=df.index, y=vwap,
            name="VWAP", mode="lines",
            line=dict(color="#E879F9", width=1.5, dash="dash"),
            hovertemplate="VWAP: <b>%{y:,.2f}</b><extra></extra>",
        ), row=1, col=1)

    if prev_close is not None:
        fig.add_hline(y=prev_close, row=1, col=1,
                      line_dash="dot", line_color="#64748B", line_width=1,
                      annotation_text=f"Prev {prev_close:,.2f}",
                      annotation_font_size=9, annotation_position="top right")

    if max_pain is not None:
        fig.add_hline(y=max_pain, row=1, col=1,
                      line_dash="dot", line_color="#F59E0B", line_width=1.2,
                      annotation_text=f"Max Pain {max_pain:,.0f}",
                      annotation_font_size=9, annotation_position="top left")

    if call_wall is not None:
        fig.add_hline(y=call_wall, row=1, col=1,
                      line_dash="dash", line_color="#22C55E", line_width=1,
                      annotation_text=f"Call Wall {call_wall:,.0f}",
                      annotation_font_size=9, annotation_position="top right")

    if put_wall is not None:
        fig.add_hline(y=put_wall, row=1, col=1,
                      line_dash="dash", line_color="#EF4444", line_width=1,
                      annotation_text=f"Put Wall {put_wall:,.0f}",
                      annotation_font_size=9, annotation_position="bottom right")

    if "Volume" in df.columns:
        bar_colors = ["#22C55E" if c >= o else "#EF4444"
                      for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=bar_colors, opacity=0.5,
            name="Volume", showlegend=False,
        ), row=vol_row, col=1)

    if show_rsi and rsi_row and "RSI" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI"], name="RSI (14)",
            line=dict(color="#A78BFA", width=1.5),
            hovertemplate="RSI: %{y:.1f}<extra></extra>",
        ), row=rsi_row, col=1)

        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.08)",
                      line_width=0, row=rsi_row, col=1)
        fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(34,197,94,0.08)",
                      line_width=0, row=rsi_row, col=1)

        for level, label, color in [(70, "OB 70", "#EF4444"),
                                     (50, "50",    "#64748B"),
                                     (30, "OS 30", "#22C55E")]:
            fig.add_hline(y=level, line_dash="dot", line_color=color, line_width=1,
                          annotation_text=label, annotation_position="right",
                          annotation_font_size=9, row=rsi_row, col=1)

        fig.update_yaxes(title_text="RSI", range=[0, 100], row=rsi_row, col=1)

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


def _render_options_section(current_price: float) -> None:
    """Options Intelligence: P/C ratio · Max Pain · OI butterfly."""
    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;'
        'letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">'
        'Options Intelligence — Max Pain · Open Interest · Put/Call</div>',
        unsafe_allow_html=True,
    )

    with st.expander("What is Options Intelligence?", expanded=False):
        st.markdown(
            """
**Options Intelligence** uses the SPY options chain to reveal where large market participants
are positioned, giving clues about likely price ranges and directional pressure.

---
**Who are the players?**

🏦 **Dealers (Market Makers)**
Banks and firms like Citadel Securities or Susquehanna that *sell* options to everyone else.
They don't take directional bets — they delta-hedge constantly to stay neutral. This hedging
activity is what moves the stock price in predictable ways. When you see GEX, max pain, or
call/put walls, you're reading what dealers are *forced* to do as price moves.

🛡️ **Hedgers (Institutional)**
Pension funds, asset managers, and hedge funds that buy puts to protect large stock portfolios,
or buy calls to get upside exposure without holding shares. Their positions show up as large OI
at key strikes — especially deep OTM puts bought months out as portfolio insurance. They drive
high put/call ratios without necessarily being "bearish" — they're just managing risk.

🧑‍💻 **Retail Investors**
Individual traders buying short-dated calls or puts, often chasing momentum or news.
Retail tends to buy OTM options close to expiry (especially 0DTE). Their activity spikes
the put/call ratio intraday and creates the demand that dealers hedge against. High retail
call buying into a rally is often a contrarian warning sign.

---

**Put/Call Ratio (P/C)**
Compares the total volume or open interest of put contracts (bearish bets) vs call contracts
(bullish bets). A ratio above 1.0 means more puts than calls — often a sign of fear or
hedging. A low ratio signals complacency or bullish sentiment.

**Max Pain**
The strike price at which the total dollar loss for all open option contracts is greatest —
meaning dealers and market makers profit most if price expires there. Prices tend to
*gravitate toward max pain* as expiration approaches, especially in the final days.
> *Example: SPY is trading at $560 but max pain is $550. As Friday expiry nears,
> selling pressure may push SPY closer to $550 — where the most option buyers lose.*

**Call Wall / Put Wall**
The strikes with the highest call or put open interest act as magnetic price levels.
A heavy **call wall** above price can cap upside (dealers sell as price rises there).
A heavy **put wall** below can provide a floor (dealers buy as price falls there).

**OI Butterfly Chart**
Shows call OI (green, right) and put OI (red, left) by strike for a chosen expiration.
Wide bars = heavy positioning. The blue line is the current SPY price; the orange dotted
line is max pain.

**OI Heatmap**
Plots net OI (calls minus puts) across all near-term expirations simultaneously.
Green cells = call-heavy strikes; red cells = put-heavy strikes. Useful for spotting
which strikes are consistently defended across multiple expiration dates.

**Expected Move**
The ATM straddle price (nearest call + nearest put) tells you what the options market implies
as the ±price range by expiration. This is a 1-sigma move — roughly a 68% probability that
SPY stays within that range.
> *Example: ±$9.40 with SPY at $560 means options imply a range of $550.60 – $569.40 by expiry.*

**Gamma Exposure (GEX)**
Measures how aggressively dealers must hedge as SPY moves. When GEX is positive, dealers buy
on dips and sell on rips — the market self-stabilises and stays range-bound. When GEX turns
negative, dealer hedging amplifies moves — small drops can become sharp sell-offs.
The GEX chart shows which individual strikes carry the most stabilising or amplifying force.
> *Example: Large positive GEX at $555 means dealers will buy heavily if SPY falls to $555,
> acting as a floor. Large negative GEX at $545 means a break below $545 may accelerate.*
            """
        )

    _scope_opts  = ["Daily", "7 Days", "14 Days", "21 Days", "Monthly"]
    _scope_keys  = {
        "Daily":   "daily",
        "7 Days":  "7d",
        "14 Days": "14d",
        "21 Days": "21d",
        "Monthly": "monthly",
    }
    _scope_notes = {
        "Daily":   "Today's option volume · 4 nearest expirations · resets each trading day",
        "7 Days":  "Open interest · expirations within 7 days",
        "14 Days": "Open interest · expirations within 14 days",
        "21 Days": "Open interest · expirations within 21 days",
        "Monthly": "Open interest · expirations ≤ 30 days out",
    }
    # Seed call — nearest expiration + full list
    seed = get_spy_options_analysis(expiration="", current_price=current_price)
    if not seed:
        st.caption("Options intelligence is currently disabled.")
        return

    exp_map = dict(zip(seed["exp_labels"], seed["expirations"]))

    scope_col, exp_col, _ = st.columns([1, 1, 3])
    with scope_col:
        pc_scope = st.radio("P/C Scope", _scope_opts, horizontal=True, key="pc_scope", index=0)
    with exp_col:
        selected_label = st.selectbox(
            "Expiration",
            options=list(exp_map.keys()),
            index=0,
            key="options_exp",
        )

    selected_iso = exp_map[selected_label]
    pc = get_put_call_ratio(scope=_scope_keys[pc_scope])

    data = get_spy_options_analysis(expiration=selected_iso, current_price=current_price)
    if not data:
        st.caption("Options data unavailable for this expiration.")
        return

    max_pain = data["max_pain"]
    oi_df    = data["oi_df"]
    dist_pct = (current_price - max_pain) / max_pain * 100 if max_pain else 0

    if abs(dist_pct) <= 0.5:
        mp_color, mp_signal = "#22C55E", "Pinned near max pain — low movement expected"
    elif abs(dist_pct) <= 2.0:
        mp_color, mp_signal = "#86EFAC", "Close to max pain — mild gravitational pull"
    elif abs(dist_pct) <= 4.0:
        mp_color, mp_signal = "#F59E0B", "Drifting from max pain — watch for reversion"
    else:
        mp_color, mp_signal = "#EF4444", "Far from max pain — strong directional move"

    dist_arrow = "▲" if dist_pct >= 0 else "▼"

    # ── Cards row: P/C | Max Pain | OI chart ─────────────────────────────────
    pc_col, mp_col, chart_col = st.columns([1, 1, 3])

    with pc_col:
        if pc:
            exp_range = (
                f"{pc['exp_nearest']} → {pc['exp_farthest']}"
                if pc["exp_nearest"] != pc["exp_farthest"]
                else pc["exp_nearest"]
            )
            st.markdown(
                f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;height:100%;box-sizing:border-box">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
    <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
                text-transform:uppercase">Put / Call</div>
    <div style="font-size:10px;font-weight:700;color:#1E293B;background:{pc['color']};
                border-radius:4px;padding:1px 6px;line-height:1.6">
      {pc['scope_label']}
    </div>
  </div>
  <div style="font-size:38px;font-weight:900;color:{pc['color']};line-height:1;
              margin:4px 0">{pc['ratio']:.3f}</div>
  <div style="font-size:12px;font-weight:700;color:{pc['color']};margin-bottom:6px">
    {pc['signal']}
  </div>
  <div style="font-size:10px;color:#64748B;line-height:1.7">
    {pc['puts']:,} puts &nbsp;·&nbsp; {pc['calls']:,} calls<br>
    {pc['exp_count']} exp &nbsp;·&nbsp; {exp_range}
  </div>
  <div style="font-size:9px;color:#334155;margin-top:6px;line-height:1.5">
    {_scope_notes[pc_scope]}
  </div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="padding:16px;font-size:11px;color:#64748B;line-height:1.6">'
                'P/C ratio unavailable.<br>Yahoo Finance options data is blocked on cloud servers.'
                '</div>',
                unsafe_allow_html=True,
            )

    with mp_col:
        st.markdown(
            f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;height:100%;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:4px">Max Pain · {selected_label}</div>
  <div style="font-size:36px;font-weight:900;color:{mp_color};line-height:1;
              margin:4px 0">${max_pain:,.0f}</div>
  <div style="font-size:11px;color:#64748B;margin-top:6px;line-height:1.6">
    Current&nbsp;<b style="color:#F1F5F9">${current_price:,.2f}</b><br>
    {dist_arrow}&nbsp;<b style="color:{mp_color}">{abs(dist_pct):.1f}%</b> from max pain
  </div>
  <div style="font-size:10px;color:{mp_color};margin-top:8px;line-height:1.5">
    {mp_signal}
  </div>
  <div style="font-size:9px;color:#334155;margin-top:8px;line-height:1.5">
    Strike where all open contracts expire with maximum loss.
    Price tends to gravitate toward it into expiry.
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    with chart_col:
        if not oi_df.empty:
            st.plotly_chart(
                _oi_butterfly_chart(oi_df, current_price, max_pain),
                width="stretch",
            )
        else:
            st.caption("No OI data for this expiration.")

    # ── Row 2: Expected Move · GEX summary · GEX chart ───────────────────────
    gex_df = data.get("gex_df", pd.DataFrame())
    em     = data.get("expected_move")

    em_col, gex_col, gex_chart_col = st.columns([1, 1, 3])
    with em_col:
        _render_expected_move_card(em, selected_label)
    with gex_col:
        _render_gex_summary_card(gex_df)
    with gex_chart_col:
        if not gex_df.empty:
            st.plotly_chart(_gex_chart(gex_df, current_price), width="stretch")
        else:
            st.caption("GEX chart unavailable.")

    # ── Heatmap: Strike × Expiration ─────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;'
        'letter-spacing:.08em;text-transform:uppercase;margin:20px 0 10px">'
        'Heatmap — Open Interest by Strike × Expiration</div>',
        unsafe_allow_html=True,
    )
    with st.spinner("Loading heatmap…"):
        call_pivot, put_pivot = _fetch_multi_exp_oi(
            seed["expirations"], seed["exp_labels"], current_price,
        )
    if not call_pivot.empty:
        st.plotly_chart(
            _oi_heatmap_chart(call_pivot, put_pivot, current_price),
            width="stretch",
        )
    else:
        st.caption("Heatmap data unavailable.")


def _fetch_multi_exp_oi(
    expirations: list[str],
    exp_labels: list[str],
    current_price: float,
    max_exp: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch call/put OI for up to max_exp expirations in parallel.
    Returns (call_pivot, put_pivot) indexed by strike, columns = exp_labels."""
    exps   = expirations[:max_exp]
    labels = exp_labels[:max_exp]

    def _fetch(pair):
        exp, label = pair
        try:
            d = get_spy_options_analysis(expiration=exp, current_price=current_price)
            if d and not d["oi_df"].empty:
                df = d["oi_df"].set_index("strike")
                return label, df["call_oi"], df["put_oi"]
        except Exception:
            pass
        return label, None, None

    call_frames: dict = {}
    put_frames:  dict = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch, pair): pair for pair in zip(exps, labels)}
        for future in as_completed(futures):
            label, call_s, put_s = future.result()
            if call_s is not None:
                call_frames[label] = call_s
                put_frames[label]  = put_s

    if not call_frames:
        return pd.DataFrame(), pd.DataFrame()

    call_pivot = pd.DataFrame(call_frames).fillna(0).sort_index()
    put_pivot  = pd.DataFrame(put_frames).fillna(0).sort_index()
    ordered    = [lb for lb in labels if lb in call_pivot.columns]
    return call_pivot[ordered], put_pivot[ordered]


def _oi_heatmap_chart(
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
        z=net.values.tolist(),
        x=exps,
        y=strikes,
        colorscale=[
            [0.00, "#7F1D1D"],
            [0.25, "#DC2626"],
            [0.45, "#6B7280"],
            [0.50, "#9CA3AF"],
            [0.55, "#6B7280"],
            [0.75, "#16A34A"],
            [1.00, "#14532D"],
        ],
        zmid=0, zmin=-abs_max, zmax=abs_max,
        colorbar=dict(
            title=dict(text="Net OI<br>(Calls−Puts)", font=dict(size=10, color="#94A3B8")),
            tickfont=dict(size=9, color="#94A3B8"),
            len=0.85,
        ),
        hovertemplate=(
            "Expiry: <b>%{x}</b><br>"
            "Strike: <b>$%{y:,.0f}</b><br>"
            "Net OI: <b>%{z:,.0f}</b><br>"
            "<i>+ = call-heavy &nbsp;· &nbsp;− = put-heavy</i>"
            "<extra></extra>"
        ),
    ))

    fig.add_shape(
        type="line", xref="paper", yref="y",
        x0=0, x1=1, y0=current_price, y1=current_price,
        line=dict(color="#3B82F6", width=2),
    )
    fig.add_annotation(
        xref="paper", yref="y", x=1.01, y=current_price,
        text=f"<b>${current_price:,.0f}</b>",
        showarrow=False, font=dict(color="#3B82F6", size=10), xanchor="left",
    )

    fig.update_layout(
        template="plotly_dark",
        height=480,
        margin=dict(l=70, r=130, t=10, b=60),
        xaxis=dict(title="Expiration", tickangle=-30, side="bottom", gridcolor="#1E293B"),
        yaxis=dict(title="Strike ($)", dtick=5, gridcolor="#1E293B"),
        hovermode="closest",
    )
    return fig


def _render_expected_move_card(em: dict | None, exp_label: str) -> None:
    if not em:
        st.markdown(
            '<div style="padding:16px;font-size:11px;color:#64748B">Expected move unavailable.</div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;height:100%;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:4px">Expected Move · {exp_label}</div>
  <div style="font-size:32px;font-weight:900;color:#A78BFA;line-height:1;margin:4px 0">
    ±${em['move']:,.2f}
  </div>
  <div style="font-size:12px;color:#64748B;margin-top:4px">±{em['pct']:.1f}% of spot</div>
  <div style="font-size:11px;color:#475569;margin-top:10px;line-height:1.8">
    Range: <b style="color:#F1F5F9">${em['low']:,.2f}</b> – <b style="color:#F1F5F9">${em['high']:,.2f}</b><br>
    ATM strike: <b style="color:#F1F5F9">${em['atm_strike']:,.0f}</b>
  </div>
  <div style="font-size:9px;color:#334155;margin-top:8px;line-height:1.5">
    ATM straddle price — 68% probability price stays within this range at expiry.
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def _render_gex_summary_card(gex_df: "pd.DataFrame") -> None:
    if gex_df.empty:
        st.markdown(
            '<div style="padding:16px;font-size:11px;color:#64748B">GEX unavailable.</div>',
            unsafe_allow_html=True,
        )
        return
    total_gex = gex_df["gex"].sum()
    total_b   = total_gex / 1e9
    if total_gex >= 0:
        gex_color  = "#22C55E"
        gex_signal = "Positive GEX"
        gex_note   = "Dealers buy dips & sell rips — price tends to stay range-bound"
    else:
        gex_color  = "#EF4444"
        gex_signal = "Negative GEX"
        gex_note   = "Dealers amplify moves — expect larger intraday swings"
    peak_support = float(gex_df.loc[gex_df["gex"].idxmax(), "strike"])
    peak_resist  = float(gex_df.loc[gex_df["gex"].idxmin(), "strike"])
    st.markdown(
        f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;height:100%;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:4px">Gamma Exposure (GEX)</div>
  <div style="font-size:32px;font-weight:900;color:{gex_color};line-height:1;margin:4px 0">
    {total_b:+.1f}B
  </div>
  <div style="font-size:12px;font-weight:700;color:{gex_color};margin-bottom:8px">
    {gex_signal}
  </div>
  <div style="font-size:10px;color:#64748B;line-height:1.8">
    {gex_note}<br>
    Peak dealer support: <b style="color:#22C55E">${peak_support:,.0f}</b><br>
    Peak dealer flip: <b style="color:#EF4444">${peak_resist:,.0f}</b>
  </div>
  <div style="font-size:9px;color:#334155;margin-top:8px;line-height:1.5">
    Positive = stabilising · Negative = moves may accelerate through key levels.
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def _gex_chart(gex_df: "pd.DataFrame", current_price: float, n_strikes: int = 30) -> go.Figure:
    """Horizontal bar chart of GEX by strike — green = stabilising, red = amplifying."""
    import numpy as np
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
    fig.add_shape(
        type="line", xref="paper", yref="y",
        x0=0, x1=1, y0=current_price, y1=current_price,
        line=dict(color="#3B82F6", width=2),
    )
    fig.add_annotation(
        xref="paper", yref="y", x=1.01, y=current_price,
        text=f"<b>${current_price:,.0f}</b>",
        showarrow=False, font=dict(color="#3B82F6", size=10), xanchor="left",
    )
    fig.add_vline(x=0, line_color="#475569", line_width=1)
    fig.update_layout(
        template="plotly_dark", height=420,
        margin=dict(l=60, r=100, t=10, b=40),
        xaxis=dict(title="Gamma Exposure ($M)", gridcolor="#1E293B"),
        yaxis=dict(title="Strike", gridcolor="#1E293B", dtick=5),
        hovermode="y unified",
    )
    return fig


def _oi_butterfly_chart(
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

    fig.add_shape(
        type="line", xref="paper", yref="y",
        x0=0, x1=1, y0=current_price, y1=current_price,
        line=dict(color="#3B82F6", width=1.5, dash="solid"),
    )
    fig.add_annotation(
        xref="paper", yref="y", x=1.01, y=current_price,
        text=f"<b>${current_price:,.0f}</b>", showarrow=False,
        font=dict(color="#3B82F6", size=10), xanchor="left",
    )

    if y_min <= max_pain <= y_max:
        fig.add_shape(
            type="line", xref="paper", yref="y",
            x0=0, x1=1, y0=max_pain, y1=max_pain,
            line=dict(color="#F59E0B", width=1.5, dash="dot"),
        )
        fig.add_annotation(
            xref="paper", yref="y", x=1.01, y=max_pain,
            text=f"Pain ${max_pain:,.0f}", showarrow=False,
            font=dict(color="#F59E0B", size=10), xanchor="left",
        )

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
            title="Open Interest",
            gridcolor="#1E293B",
        ),
        yaxis=dict(title="Strike", gridcolor="#1E293B", dtick=5),
        legend=dict(orientation="h", y=1.04, x=0),
        hovermode="y unified",
    )
    return fig


render_spy_dashboard_tab()
