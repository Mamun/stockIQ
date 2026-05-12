"""
Options Intelligence expander and volatility regime bar.

Public API:
  render_options_expander(seed, current_price, vol, pc, suggestion)
  render_vol_regime_bar(vol)
"""

from __future__ import annotations

from datetime import date as _date

import pandas as pd
import streamlit as st


# ── Expander live-text helpers (private) ──────────────────────────────────────

def _expander_signal_block(suggestion: dict | None, lbl: str) -> str:
    if not suggestion:
        return ""
    direction  = suggestion["direction"]
    confidence = suggestion["confidence"]
    rationale  = suggestion.get("rationale", [])
    bullets    = "\n".join(f"> ◆ {r}" for r in rationale) if rationale else ""
    dir_emoji  = "🟢" if direction == "Bullish" else "🔴" if direction == "Bearish" else "🟡"
    return (
        f"\n> *Right now ({lbl}):*\n"
        f"{bullets}\n"
        f"> → {dir_emoji} **{direction}** direction · **{confidence}** confidence\n"
    )


def _expander_vol_block(vol: dict | None) -> str:
    if not vol:
        return ""
    rank      = vol["iv_rank"]
    bias      = vol["strategy_bias"]
    color_lbl = "High IV" if rank >= 50 else "Mid IV" if rank >= 30 else "Low IV"
    hv30      = vol.get("hv30")
    ratio     = vol.get("iv_hv_ratio")
    ratio_str = f" · IV/HV **{ratio:.2f}×**" if ratio else ""
    hv_str    = f" · HV30 **{hv30:.1f}%**" if hv30 else ""
    return f"> *Right now: IV Rank **{rank:.0f}%** ({color_lbl}){hv_str}{ratio_str} → **{bias}***\n"


# ── Public renderers ──────────────────────────────────────────────────────────

def render_options_expander(
    seed: dict,
    current_price: float,
    vol: dict | None = None,
    pc: dict | None = None,
    suggestion: dict | None = None,
) -> None:
    """Educational expander using live data from the seed (nearest/0DTE expiration)."""
    oi_df  = seed.get("oi_df", pd.DataFrame())
    gex_df = seed.get("gex_df", pd.DataFrame())
    em     = seed.get("expected_move")
    mp     = seed["max_pain"]
    dist   = (current_price - mp) / mp * 100 if mp else 0

    exp_used = seed.get("expiration", "")
    try:
        exp_idx = seed["expirations"].index(exp_used)
        lbl = seed["exp_labels"][exp_idx]
    except (ValueError, IndexError):
        lbl = seed["exp_labels"][0] if seed["exp_labels"] else ""
    is_0dte     = exp_used == _date.today().isoformat()
    lbl_display = f"{lbl} · 0DTE" if is_0dte else lbl

    mp_sig = (
        "Pinned near max pain — low movement expected"   if abs(dist) <= 0.5 else
        "Close to max pain — mild gravitational pull"    if abs(dist) <= 2.0 else
        "Drifting from max pain — watch for reversion"   if abs(dist) <= 4.0 else
        "Far from max pain — strong directional move"
    )

    total_gex = gex_df["gex"].sum() if not gex_df.empty else None
    gex_b     = f"{total_gex / 1e9:+.1f}B" if total_gex is not None else "N/A"
    gex_sign  = "Long Gamma / Positive GEX" if (total_gex or 0) >= 0 else "Short Gamma / Negative GEX"
    gex_behav = (
        "dealers are **long gamma** — they buy dips and sell rips, keeping SPY range-bound"
        if (total_gex or 0) >= 0
        else "dealers are **short gamma** — their hedging amplifies moves, so drops can accelerate"
    )
    peak_sup = f"${float(gex_df.loc[gex_df['gex'].idxmax(), 'strike']):,.0f}" if not gex_df.empty else "N/A"
    peak_res = f"${float(gex_df.loc[gex_df['gex'].idxmin(), 'strike']):,.0f}" if not gex_df.empty else "N/A"
    call_wall = f"${float(oi_df.loc[oi_df['call_oi'].idxmax(), 'strike']):,.0f}" if not oi_df.empty else "N/A"
    put_wall  = f"${float(oi_df.loc[oi_df['put_oi'].idxmax(),  'strike']):,.0f}" if not oi_df.empty else "N/A"

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

    if vol:
        rank     = vol["iv_rank"]
        hv30     = vol.get("hv30")
        iv30     = vol["iv30"]
        ratio    = vol.get("iv_hv_ratio")
        rank_lbl = "High IV" if rank >= 50 else "Mid IV" if rank >= 30 else "Low IV"
        vol_txt  = (
            f'IV Rank **{rank:.0f}%** ({rank_lbl}) · HV30 (realized) **{hv30:.1f}%** · '
            f'IV30 (VIX) **{iv30:.1f}%** · IV/HV **{ratio:.2f}×** — '
            f'**{vol["strategy_bias"]}**: {vol["strategy_note"]}.'
            if hv30 and ratio else
            f'IV Rank **{rank:.0f}%** ({rank_lbl}) · VIX **{iv30:.1f}%** · **{vol["strategy_bias"]}**.'
        )
    else:
        vol_txt = "Volatility regime data unavailable."

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

---

**Volatility Regime — IV Rank · HV30 · IV30**
Before choosing a strategy, check whether options are currently cheap or expensive.
- **IV Rank** (0–100%): where today's VIX sits in its 52-week range. High = options expensive; Low = options cheap.
- **HV30** (Historical Volatility): what SPY has *actually* moved over the past 30 days, annualised.
- **IV30** (VIX): what options are *pricing in* for the next 30 days, annualised.
- **IV/HV Ratio > 1.1** → options overpriced vs realised moves → favour selling premium (credit spreads, iron condors).
- **IV/HV Ratio < 0.9** → options cheap → favour buying premium (debit spreads, long straddles).
> *Right now: {vol_txt}*

**Setup Card — How the Strategy Is Chosen**

The setup card synthesises three steps: direction vote → volatility regime → reference levels.

---

**Step 1 · Direction Vote (4 signals, majority wins)**

| Signal | Bullish when | Bearish when | Neutral when |
|---|---|---|---|
| **P/C Ratio** | P/C < 0.80 — calls dominate | P/C > 1.20 — puts dominate | 0.80 – 1.20 |
| **Max Pain** | Max pain > 0.5% above spot | Max pain > 0.5% below spot | Within ±0.5% |
| **GEX Regime** | Positive total GEX (dealers stabilise) | Negative near-ATM GEX (dealers amplify) | Negative but not near-ATM |
| **OI Walls** | Put wall < 1.5% below (floor) | Call wall < 1.5% above (ceiling) | Both walls far away |

Confidence: **HIGH** = 3+ signals agree · **MODERATE** = 2 agree · **LOW** = split vote.
{_expander_signal_block(suggestion, lbl_display)}

---

**Step 2 · IV Rank decides Buy vs Sell premium**

IV Rank (0–100%) shows where today's VIX sits relative to its 52-week range.
High IV Rank → options are *historically expensive* → better to sell premium and collect the inflated price.
Low IV Rank → options are *historically cheap* → better to buy premium before vol expands.

| IV Rank | Options pricing | Strategy bias | Examples |
|---|---|---|---|
| ≥ 50% | Expensive vs history | **Sell premium** | Bull Put Spread, Bear Call Spread, Iron Condor |
| 30–50% | Mixed / neutral | **Neutral** — reduce size, wait for cleaner setup | All types, smaller position |
| < 30% | Cheap vs history | **Buy premium** | Bull Call Spread, Bear Put Spread, Long Straddle |

> *IV/HV Ratio > 1.1 also triggers Sell Premium — options pricing more vol than SPY is actually delivering.*

{_expander_vol_block(vol)}

---

**Step 3 · Reference Levels (price magnets, not guaranteed exits)**

- **Target**: the nearest meaningful level in the trade direction. Priority order: unfilled gap fill → OI wall → expected move boundary → max pain. When two levels cluster together it's a stronger signal.
- **Unfilled gap fills**: when SPY gaps up or down and never revisits the open edge of that gap, the level becomes a price magnet — the market tends to return to fill it. A gap fill target near an OI wall is especially strong.
- **Stop / Invalidation**: the level that disproves the trade thesis. If price crosses it, the logic behind the trade is no longer valid. Set from the opposing OI wall or the EM boundary.
- **Hold condition**: if GEX is positive (dealers long gamma), small dips get absorbed — stay patient. If GEX is negative (short gamma), moves can run fast and reverse hard — exit near the target rather than holding for more.

> *See the Setup card above the option chain selector for the current target, stop, and hold note — tied to your selected expiration.*

---

**Flow Sweeps — Volume / OI Spike Detector**
Flags OTM strikes where today's volume is ≥ 3× the existing open interest.
High vol/OI means someone is *opening* a large new position aggressively — the hallmark
of an institutional sweep — rather than closing or rolling existing contracts.
- **CALL sweeps**: bullish positioning for the selected expiry.
- **PUT sweeps**: bearish positioning or large protective buying.
- Ratio colour: Yellow = 10×+ · Purple = 5–10× · Grey = 3–5×.
Data is sourced from Yahoo Finance (15-min delay). Sweeps update with the expiration selector.

*Not financial advice — all levels are reference points, not trade orders.*
            """
        )


def render_vol_regime_bar(vol: dict | None) -> None:
    if not vol:
        return

    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        'text-transform:uppercase;margin-bottom:10px">'
        'Volatility Regime — IV Rank · HV30 vs IV30 · Strategy Bias</div>',
        unsafe_allow_html=True,
    )

    rank  = vol["iv_rank"]
    hv30  = vol.get("hv30")
    iv30  = vol["iv30"]
    ratio = vol.get("iv_hv_ratio")

    rank_clr  = "#22C55E" if rank >= 50 else "#F59E0B" if rank >= 30 else "#A78BFA"
    rank_lbl  = "High IV" if rank >= 50 else "Mid IV" if rank >= 30 else "Low IV"
    hv_clr    = "#EF4444" if hv30 and hv30 > 25 else "#F59E0B" if hv30 and hv30 > 15 else "#22C55E"
    iv_clr    = "#EF4444" if iv30 > 25 else "#F59E0B" if iv30 > 15 else "#22C55E"
    ratio_clr = "#22C55E" if ratio and ratio >= 1.1 else "#A78BFA" if ratio and ratio < 0.9 else "#F59E0B"
    hv30_str  = f"{hv30:.1f}%" if hv30 else "—"
    ratio_str = f"{ratio:.2f}×" if ratio else "—"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:10px;padding:14px 16px;min-height:140px;box-sizing:border-box">'
            f'<div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;'
            f'text-transform:uppercase;margin-bottom:4px">IV Rank (1Y)</div>'
            f'<div style="font-size:36px;font-weight:900;color:{rank_clr};line-height:1;margin-bottom:6px">'
            f'{rank:.0f}<span style="font-size:16px">%</span></div>'
            f'<div style="background:linear-gradient(to right,{rank_clr} {min(rank,100):.0f}%,#1E293B {min(rank,100):.0f}%);'
            f'border-radius:3px;height:4px;margin-bottom:6px"></div>'
            f'<div style="font-size:11px;font-weight:700;color:{rank_clr}">{rank_lbl}</div>'
            f'<div style="font-size:9px;color:#64748B;margin-top:4px">52w: {vol["vix_52lo"]:.1f} – {vol["vix_52hi"]:.1f}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:10px;padding:14px 16px;min-height:140px;box-sizing:border-box">'
            f'<div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;'
            f'text-transform:uppercase;margin-bottom:4px">HV30 · Realized</div>'
            f'<div style="font-size:36px;font-weight:900;color:{hv_clr};line-height:1;margin-bottom:4px">{hv30_str}</div>'
            f'<div style="font-size:10px;color:#94A3B8;margin-top:10px;line-height:1.6">30-day annualized<br>realized volatility</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:10px;padding:14px 16px;min-height:140px;box-sizing:border-box">'
            f'<div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;'
            f'text-transform:uppercase;margin-bottom:4px">IV30 · VIX</div>'
            f'<div style="font-size:36px;font-weight:900;color:{iv_clr};line-height:1;margin-bottom:4px">'
            f'{iv30:.1f}<span style="font-size:16px">%</span></div>'
            f'<div style="font-size:10px;color:#94A3B8;margin-top:10px;line-height:1.6">30-day implied vol<br>annualized · CBOE VIX</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:10px;padding:14px 16px;min-height:140px;box-sizing:border-box">'
            f'<div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;'
            f'text-transform:uppercase;margin-bottom:4px">IV / HV Ratio</div>'
            f'<div style="font-size:36px;font-weight:900;color:{ratio_clr};line-height:1;margin-bottom:6px">{ratio_str}</div>'
            f'<div style="display:inline-block;background:{vol["strategy_color"]}33;color:{vol["strategy_color"]};'
            f'font-size:0.7rem;font-weight:700;padding:2px 8px;border-radius:4px;letter-spacing:.05em">{vol["strategy_bias"]}</div>'
            f'<div style="font-size:9px;color:#64748B;margin-top:6px;line-height:1.5">{vol["strategy_note"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
