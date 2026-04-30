"""
Options Intelligence panel: P/C ratio, Max Pain, OI butterfly, GEX, heatmap.

All Plotly chart building is delegated to components/spy_charts.py.
All data fetching is delegated to backend services.
This module is responsible only for layout, selectors, and card HTML.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date, datetime as _datetime
import pytz

import pandas as pd
import streamlit as st

from stockiq.backend.services.spy_service import get_spy_options_analysis, get_put_call_ratio
from stockiq.frontend.views.components.spy_charts import (
    oi_gex_combined_chart,
    oi_heatmap_chart,
)


_ET = pytz.timezone("America/New_York")


def render_options_intelligence(current_price: float) -> None:
    seed = get_spy_options_analysis(expiration="", current_price=current_price)
    if not seed:
        st.markdown(
            '<div style="font-size:11px;font-weight:700;color:#64748B;'
            'letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">'
            'Options Intelligence — Max Pain · Open Interest · Put/Call</div>',
            unsafe_allow_html=True,
        )
        st.caption("Options intelligence is currently disabled.")
        return

    exp_map = dict(zip(seed["exp_labels"], seed["expirations"]))

    # Prefer 0DTE data for the expander if today has an expiration in the chain
    today_iso = _date.today().isoformat()
    if today_iso in seed["expirations"] and seed.get("expiration") != today_iso:
        seed_0dte = get_spy_options_analysis(expiration=today_iso, current_price=current_price)
        expander_seed = seed_0dte if seed_0dte else seed
    else:
        expander_seed = seed

    _render_what_is_expander(expander_seed, current_price)

    exp_col, _ = st.columns([2, 3])
    with exp_col:
        selected_label = st.selectbox(
            "Expiration", options=list(exp_map.keys()), index=1, key="options_exp"
        )
    selected_iso = exp_map[selected_label]

    pc_scope_key, pc_scope_note = _derive_pc_scope(selected_iso)
    pc       = get_put_call_ratio(scope=pc_scope_key)
    data     = get_spy_options_analysis(expiration=selected_iso, current_price=current_price)
    fetched_at = _datetime.now(tz=_ET).strftime("%-I:%M %p ET · %b %-d")
    if not data:
        st.caption("Options data unavailable for this expiration.")
        return

    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        f'text-transform:uppercase;margin-bottom:10px">'
        f'Options Intelligence — Max Pain · Open Interest · Put/Call'
        f'<span style="font-weight:400;color:#475569;letter-spacing:0;'
        f'text-transform:none"> &nbsp;·&nbsp; as of {fetched_at}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    max_pain = data["max_pain"]
    oi_df    = data["oi_df"]
    dist_pct = (current_price - max_pain) / max_pain * 100 if max_pain else 0
    mp_color, mp_signal = _max_pain_style(dist_pct)
    dist_arrow = "▲" if dist_pct >= 0 else "▼"

    gex_df = data.get("gex_df", pd.DataFrame())
    em     = data.get("expected_move")

    cards_col, chart_col = st.columns([2, 5])
    with cards_col:
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            _render_pc_card(pc, pc_scope_note)
        with r1c2:
            _render_max_pain_card(max_pain, selected_label, current_price, dist_pct, dist_arrow, mp_color, mp_signal)
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            _render_expected_move_card(em, selected_label)
        with r2c2:
            _render_gex_summary_card(gex_df)
    with chart_col:
        if not oi_df.empty or not gex_df.empty:
            st.plotly_chart(
                oi_gex_combined_chart(oi_df, gex_df, current_price, max_pain),
                width="stretch",
            )
        else:
            st.caption("No options data for this expiration.")

    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;'
        'letter-spacing:.08em;text-transform:uppercase;margin:20px 0 10px">'
        'Heatmap — Open Interest by Strike × Expiration</div>',
        unsafe_allow_html=True,
    )
    with st.spinner("Loading heatmap…"):
        call_pivot, put_pivot = _fetch_multi_exp_oi(
            seed["expirations"], seed["exp_labels"], current_price
        )
    if not call_pivot.empty:
        st.plotly_chart(oi_heatmap_chart(call_pivot, put_pivot, current_price), width="stretch")
    else:
        st.caption("Heatmap data unavailable.")


# ── P/C scope derivation ───────────────────────────────────────────────────────

def _derive_pc_scope(selected_iso: str) -> tuple[str, str]:
    try:
        dte = (_datetime.strptime(selected_iso, "%Y-%m-%d").date() - _date.today()).days
    except Exception:
        dte = 0
    if dte <= 1:
        return "daily",   "Today's option volume · resets each trading day"
    if dte <= 7:
        return "7d",      "Open interest · expirations within 7 days"
    if dte <= 14:
        return "14d",     "Open interest · expirations within 14 days"
    if dte <= 21:
        return "21d",     "Open interest · expirations within 21 days"
    return "monthly", "Open interest · expirations ≤ 30 days out"


# ── Max Pain helpers ───────────────────────────────────────────────────────────

def _max_pain_style(dist_pct: float) -> tuple[str, str]:
    if abs(dist_pct) <= 0.5:
        return "#22C55E", "Pinned near max pain — low movement expected"
    if abs(dist_pct) <= 2.0:
        return "#86EFAC", "Close to max pain — mild gravitational pull"
    if abs(dist_pct) <= 4.0:
        return "#F59E0B", "Drifting from max pain — watch for reversion"
    return "#EF4444", "Far from max pain — strong directional move"


# ── Card renderers ─────────────────────────────────────────────────────────────

def _render_pc_card(pc: dict | None, pc_scope_note: str) -> None:
    if not pc:
        st.markdown(
            '<div style="padding:16px;font-size:11px;color:#64748B;line-height:1.6">'
            'P/C ratio unavailable.<br>Yahoo Finance options data is blocked on cloud servers.'
            '</div>',
            unsafe_allow_html=True,
        )
        return
    exp_range = (
        f"{pc['exp_nearest']} → {pc['exp_farthest']}"
        if pc["exp_nearest"] != pc["exp_farthest"]
        else pc["exp_nearest"]
    )
    st.markdown(
        f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;min-height:175px;box-sizing:border-box">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
    <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
                text-transform:uppercase">Put / Call</div>
    <div style="font-size:10px;font-weight:700;color:#1E293B;background:{pc['color']};
                border-radius:4px;padding:1px 6px;line-height:1.6">{pc['scope_label']}</div>
  </div>
  <div style="font-size:38px;font-weight:900;color:{pc['color']};line-height:1;
              margin:4px 0">{pc['ratio']:.3f}</div>
  <div style="font-size:12px;font-weight:700;color:{pc['color']};margin-bottom:6px">{pc['signal']}</div>
  <div style="font-size:10px;color:#94A3B8;line-height:1.7">
    {pc['puts']:,} puts &nbsp;·&nbsp; {pc['calls']:,} calls<br>{pc['exp_count']} exp &nbsp;·&nbsp; {exp_range}
  </div>
  <div style="font-size:9px;color:#64748B;margin-top:6px;line-height:1.5">{pc_scope_note}</div>
</div>""",
        unsafe_allow_html=True,
    )


def _render_max_pain_card(max_pain, label, current_price, dist_pct, arrow, mp_color, mp_signal):
    st.markdown(
        f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;min-height:175px;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:4px">Max Pain · {label}</div>
  <div style="font-size:36px;font-weight:900;color:{mp_color};line-height:1;margin:4px 0">${max_pain:,.0f}</div>
  <div style="font-size:11px;color:#94A3B8;margin-top:6px;line-height:1.6">
    Current&nbsp;<b style="color:#F1F5F9">${current_price:,.2f}</b><br>
    {arrow}&nbsp;<b style="color:{mp_color}">{abs(dist_pct):.1f}%</b> from max pain
  </div>
  <div style="font-size:10px;color:{mp_color};margin-top:8px;line-height:1.5">{mp_signal}</div>
  <div style="font-size:9px;color:#64748B;margin-top:8px;line-height:1.5">
    Strike where all open contracts expire with maximum loss.
    Price tends to gravitate toward it into expiry.
  </div>
</div>""",
        unsafe_allow_html=True,
    )


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
            padding:16px;min-height:175px;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:4px">Expected Move · {exp_label}</div>
  <div style="font-size:32px;font-weight:900;color:#A78BFA;line-height:1;margin:4px 0">
    ±${em['move']:,.2f}
  </div>
  <div style="font-size:12px;color:#94A3B8;margin-top:4px">±{em['pct']:.1f}% of spot</div>
  <div style="font-size:11px;color:#94A3B8;margin-top:10px;line-height:1.8">
    Range: <b style="color:#F1F5F9">${em['low']:,.2f}</b> – <b style="color:#F1F5F9">${em['high']:,.2f}</b><br>
    ATM strike: <b style="color:#F1F5F9">${em['atm_strike']:,.0f}</b>
  </div>
  <div style="font-size:9px;color:#64748B;margin-top:8px;line-height:1.5">
    {"ATM straddle price" if em.get("method") == "straddle" else "IV-based estimate (no live quotes)"}
    — 68% probability price stays within this range at expiry.
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def _render_gex_summary_card(gex_df: pd.DataFrame) -> None:
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
        gex_gamma  = "Long Gamma"
        gex_sign   = "Positive GEX"
        gex_note   = "Dealers buy dips & sell rips — price tends to stay range-bound"
    else:
        gex_color  = "#EF4444"
        gex_gamma  = "Short Gamma"
        gex_sign   = "Negative GEX"
        gex_note   = "Dealers amplify moves — expect larger intraday swings"
    peak_support = float(gex_df.loc[gex_df["gex"].idxmax(), "strike"])
    peak_resist  = float(gex_df.loc[gex_df["gex"].idxmin(), "strike"])
    st.markdown(
        f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;min-height:175px;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:4px">Gamma Exposure (GEX)</div>
  <div style="font-size:32px;font-weight:900;color:{gex_color};line-height:1;margin:4px 0">
    {total_b:+.1f}B
  </div>
  <div style="font-size:13px;font-weight:800;color:{gex_color};line-height:1.2">{gex_gamma}</div>
  <div style="font-size:10px;color:#64748B;margin-bottom:6px">{gex_sign}</div>
  <div style="font-size:10px;color:#94A3B8;line-height:1.8">
    {gex_note}<br>
    Peak dealer support: <b style="color:#22C55E">${peak_support:,.0f}</b><br>
    Peak dealer flip: <b style="color:#EF4444">${peak_resist:,.0f}</b>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


# ── "What is?" expander ────────────────────────────────────────────────────────

def _render_what_is_expander(seed: dict, current_price: float) -> None:
    """Educational expander using live data from the seed (nearest expiration)."""
    oi_df  = seed.get("oi_df", pd.DataFrame())
    gex_df = seed.get("gex_df", pd.DataFrame())
    em     = seed.get("expected_move")
    mp     = seed["max_pain"]
    dist   = (current_price - mp) / mp * 100 if mp else 0

    # Derive label from the expiration actually used, not blindly from index 0
    exp_used = seed.get("expiration", "")
    try:
        exp_idx = seed["expirations"].index(exp_used)
        lbl = seed["exp_labels"][exp_idx]
    except (ValueError, IndexError):
        lbl = seed["exp_labels"][0] if seed["exp_labels"] else ""
    is_0dte = exp_used == _date.today().isoformat()
    lbl_display = f"{lbl} · 0DTE" if is_0dte else lbl

    mp_sig = (
        "Pinned near max pain — low movement expected"   if abs(dist) <= 0.5 else
        "Close to max pain — mild gravitational pull"    if abs(dist) <= 2.0 else
        "Drifting from max pain — watch for reversion"   if abs(dist) <= 4.0 else
        "Far from max pain — strong directional move"
    )

    pc       = get_put_call_ratio(scope="daily")
    total_gex = gex_df["gex"].sum() if not gex_df.empty else None
    gex_b    = f"{total_gex / 1e9:+.1f}B" if total_gex is not None else "N/A"
    gex_sign = "Long Gamma / Positive GEX" if (total_gex or 0) >= 0 else "Short Gamma / Negative GEX"
    gex_behav = (
        "dealers are **long gamma** — they buy dips and sell rips, keeping SPY range-bound"
        if (total_gex or 0) >= 0
        else "dealers are **short gamma** — their hedging amplifies moves, so drops can accelerate"
    )
    peak_sup = f"${float(gex_df.loc[gex_df['gex'].idxmax(), 'strike']):,.0f}" if not gex_df.empty else "N/A"
    peak_res = f"${float(gex_df.loc[gex_df['gex'].idxmin(), 'strike']):,.0f}" if not gex_df.empty else "N/A"

    call_wall = f"${float(oi_df.loc[oi_df['call_oi'].idxmax(), 'strike']):,.0f}" if not oi_df.empty else "N/A"
    put_wall  = f"${float(oi_df.loc[oi_df['put_oi'].idxmax(), 'strike']):,.0f}"  if not oi_df.empty else "N/A"

    pc_txt = (
        f"P/C ratio is **{pc['ratio']:.3f}** ({pc['signal']}) — "
        f"{pc['puts']:,} puts vs {pc['calls']:,} calls across {pc['exp_count']} expirations. "
        + ("Ratio above 1.0 means more puts than calls — the market is hedging or fearful."
           if pc["ratio"] >= 1.0
           else "Ratio below 1.0 means more calls than puts — the market is leaning bullish or complacent.")
        if pc else "P/C ratio unavailable."
    )
    mp_txt = (
        f"SPY is currently **${current_price:,.2f}**, which is "
        f"**{abs(dist):.1f}% {'above' if dist >= 0 else 'below'}** max pain (**${mp:,.0f}**). {mp_sig}."
    )
    walls_txt = (
        f"Call wall at **{call_wall}** (dealers sell SPY as price approaches there, capping upside). "
        f"Put wall at **{put_wall}** (dealers buy SPY as price drops there, providing a floor). "
        f"SPY is currently at **${current_price:,.2f}**."
        if not oi_df.empty else "Wall data unavailable."
    )
    em_txt = (
        f"±**${em['move']:,.2f}** (±{em['pct']:.1f}%) — "
        f"implied range **${em['low']:,.2f} – ${em['high']:,.2f}** by {lbl_display}."
        if em else "Expected move unavailable for this expiration."
    )

    with st.expander(f"What is Options Intelligence?  ·  showing {lbl_display}", expanded=False):
        st.markdown(
            f"""
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
the put/call ratio intraday and creates the demand that dealers hedge against.

---

**Put/Call Ratio (P/C)**
Compares the total volume or open interest of put contracts (bearish bets) vs call contracts
(bullish bets). A ratio above 1.0 means more puts than calls — often a sign of fear or hedging.
> *Right now: {pc_txt}*

**Max Pain**
The strike price at which the total dollar loss for all open option contracts is greatest.
Prices tend to *gravitate toward max pain* as expiration approaches.
> *Right now: {mp_txt}*

**Call Wall / Put Wall**
The strikes with the highest call or put open interest act as magnetic price levels.
> *Right now: {walls_txt}*

**OI Butterfly Chart**
Shows call OI (green, right) and put OI (red, left) by strike for a chosen expiration.

**OI Heatmap**
Plots net OI (calls minus puts) across all near-term expirations simultaneously.

**Expected Move**
The ATM straddle price — what the options market implies as the ±price range by expiration.
> *Right now: {em_txt}*

**Gamma Exposure (GEX) — Long vs Short Gamma**
Measures how aggressively dealers must hedge as SPY moves.
**Long Gamma (Positive GEX)** = dealers stabilise price — they buy dips and sell rips.
**Short Gamma (Negative GEX)** = dealers amplify moves — drops and rips can accelerate.
> *Right now: GEX is **{gex_b}** ({gex_sign}), meaning {gex_behav}.
> Peak dealer support at **{peak_sup}** · peak amplification risk at **{peak_res}**.*
            """
        )


# ── Multi-expiration OI fetch ──────────────────────────────────────────────────

def _fetch_multi_exp_oi(
    expirations: list[str],
    exp_labels: list[str],
    current_price: float,
    max_exp: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch call/put OI for up to max_exp expirations in parallel."""
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
        for label, call_s, put_s in pool.map(_fetch, zip(exps, labels)):
            if call_s is not None:
                call_frames[label] = call_s
                put_frames[label]  = put_s

    if not call_frames:
        return pd.DataFrame(), pd.DataFrame()

    call_pivot = pd.DataFrame(call_frames).fillna(0).sort_index()
    put_pivot  = pd.DataFrame(put_frames).fillna(0).sort_index()
    ordered    = [lb for lb in labels if lb in call_pivot.columns]
    return call_pivot[ordered], put_pivot[ordered]
