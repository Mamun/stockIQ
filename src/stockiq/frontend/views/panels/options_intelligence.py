"""
Options Intelligence panel: P/C ratio, Max Pain, OI butterfly, GEX, heatmap.

All Plotly chart building is delegated to components/spy_charts.py.
All data fetching is delegated to backend services.
This module is responsible only for layout, selectors, and card HTML.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date as _date, datetime as _datetime
import pytz

import pandas as pd
import streamlit as st

from stockiq.backend.services.spy_service import get_spy_options_analysis, get_vol_regime, get_spy_gaps_df
from stockiq.backend.models.options import compute_strategy_suggestion
from stockiq.frontend.views.components.spy_charts import (
    oi_gex_combined_chart,
    oi_heatmap_chart,
)


_ET = pytz.timezone("America/New_York")


def _share_url(path: str, exp_iso: str = "") -> str:
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(st.context.url)
        url = f"{parsed.scheme}://{parsed.netloc}{path}"
        if exp_iso:
            url += f"?exp={exp_iso}"
        return url
    except Exception:
        suffix = f"?exp={exp_iso}" if exp_iso else ""
        return path + suffix


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

    vol     = get_vol_regime()
    gaps_df = get_spy_gaps_df()
    expander_suggestion = compute_strategy_suggestion(
        current_price,
        expander_seed.get("expected_move"),
        expander_seed.get("pc"),
        expander_seed.get("gex_df", pd.DataFrame()),
        expander_seed.get("oi_df", pd.DataFrame()),
        expander_seed["max_pain"],
        vol,
        gaps_df=gaps_df,
    )
    _render_what_is_expander(
        expander_seed, current_price, vol,
        pc=expander_seed.get("pc"),
        suggestion=expander_suggestion,
    )

    expirations = seed["expirations"]
    default_idx = expirations.index(today_iso) if today_iso in expirations else 0

    # ── Top row: expiration selector (left) + strategy card (right) ──────────
    exp_col, strat_col = st.columns([1, 3])
    with exp_col:
        selected_label = st.selectbox(
            "Option Chain", options=list(exp_map.keys()), index=default_idx, key="options_exp"
        )
    selected_iso = exp_map[selected_label]

    data       = get_spy_options_analysis(expiration=selected_iso, current_price=current_price)
    fetched_at = _datetime.now(tz=_ET).strftime("%-I:%M %p ET · %b %-d")
    if not data:
        st.caption("Options data unavailable for this expiration.")
        return

    pc            = data.get("pc")
    pc_scope_note = pc.get("scope_note", "") if pc else ""

    max_pain   = data["max_pain"]
    oi_df      = data["oi_df"]
    gex_df     = data.get("gex_df", pd.DataFrame())
    em         = data.get("expected_move")
    dist_pct   = (current_price - max_pain) / max_pain * 100 if max_pain else 0
    mp_color, mp_signal = _max_pain_style(dist_pct)
    dist_arrow = "▲" if dist_pct >= 0 else "▼"

    suggestion = compute_strategy_suggestion(current_price, em, pc, gex_df, oi_df, max_pain, vol, gaps_df=gaps_df)
    with strat_col:
        _render_strategy_card(suggestion, selected_label, selected_iso)

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    # ── Volatility Regime bar ─────────────────────────────────────────────────
    _render_vol_regime_bar(vol)
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    # ── Section header ────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        f'text-transform:uppercase;margin-bottom:10px">'
        f'Options Intelligence — Max Pain · Open Interest · Put/Call'
        f'<span style="font-weight:400;color:#475569;letter-spacing:0;'
        f'text-transform:none"> &nbsp;·&nbsp; as of {fetched_at}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

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
                use_container_width=True,
            )
        else:
            st.caption("No options data for this expiration.")

    sig_col, squeeze_col = st.columns([1, 1], gap="large")
    with sig_col:
        _render_signals_panel(_compute_signals(gex_df, oi_df, current_price, max_pain, selected_label))
    with squeeze_col:
        _render_gamma_squeeze_panel(_compute_gamma_squeeze(gex_df, oi_df, pc, current_price))

    sweep_df = data.get("sweep_signals", pd.DataFrame())
    _render_sweep_panel(sweep_df, selected_label, fetched_at)

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
        st.plotly_chart(oi_heatmap_chart(call_pivot, put_pivot, current_price), use_container_width=True)
    else:
        st.caption("Heatmap data unavailable.")


# ── Signals computation ────────────────────────────────────────────────────────

def _compute_signals(
    gex_df: pd.DataFrame,
    oi_df: pd.DataFrame,
    current_price: float,
    max_pain: float,
    exp_label: str = "",
) -> list[dict]:
    signals: list[dict] = []
    gex_threshold = gex_df["gex"].abs().quantile(0.75) if not gex_df.empty else 0

    if not gex_df.empty:
        # Peak GEX strike — strongest dealer support / damping zone
        peak_row    = gex_df.loc[gex_df["gex"].idxmax()]
        peak_strike = float(peak_row["strike"])
        peak_gex    = float(peak_row["gex"])
        peak_str    = "STRONG" if abs(peak_gex) >= gex_threshold else "MODERATE"
        signals.append({
            "type": "GEX Support", "icon": "◆",
            "desc": "Highest dealer hedging pressure — strongest price-damping zone, good for selling volatility",
            "price": peak_strike,
            "dist": (peak_strike - current_price) / current_price * 100,
            "strength": peak_str, "color": "#22C55E",
        })
        # GEX flip strike — most negative GEX = dealer amplification risk
        flip_row    = gex_df.loc[gex_df["gex"].idxmin()]
        flip_strike = float(flip_row["strike"])
        flip_gex    = float(flip_row["gex"])
        if flip_gex < 0:
            flip_str = "STRONG" if abs(flip_gex) >= gex_threshold else "MODERATE"
            signals.append({
                "type": "GEX Flip", "icon": "⚠",
                "desc": "Negative GEX zone — dealer hedging amplifies moves if price crosses here",
                "price": flip_strike,
                "dist": (flip_strike - current_price) / current_price * 100,
                "strength": flip_str, "color": "#F59E0B",
            })

    if not oi_df.empty:
        call_strike = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"])
        put_strike  = float(oi_df.loc[oi_df["put_oi"].idxmax(),  "strike"])
        signals.append({"type": "Call Wall", "icon": "◎",
                         "desc": "Highest call OI strike — dealers sell as price approaches, capping upside",
                         "price": call_strike,
                         "dist": (call_strike - current_price) / current_price * 100,
                         "strength": "STRONG", "color": "#A78BFA"})
        signals.append({"type": "Put Wall", "icon": "▣",
                         "desc": "Highest put OI strike — dealers buy as price drops here, providing a floor",
                         "price": put_strike,
                         "dist": (put_strike - current_price) / current_price * 100,
                         "strength": "MODERATE", "color": "#22C55E"})

    if max_pain:
        dist = (max_pain - current_price) / current_price * 100
        exp_note = f" · expires {exp_label}" if exp_label else ""
        signals.append({"type": "Max Pain", "icon": "◎",
                         "desc": f"Strike where all open contracts expire worthless — price gravitates here{exp_note}",
                         "price": max_pain,
                         "dist": dist,
                         "strength": "STRONG", "color": "#A78BFA"})

    signals.sort(key=lambda x: abs(x["dist"]))
    return signals[:5]


def _render_signals_panel(signals: list[dict]) -> None:
    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        'text-transform:uppercase;margin:20px 0 10px">⚡ Dealer Levels</div>',
        unsafe_allow_html=True,
    )
    if not signals:
        st.caption("Insufficient options data for signals.")
        return
    for sig in signals:
        dist_clr = "#22C55E" if sig["dist"] >= 0 else "#EF4444"
        badge_clr = "#F59E0B" if sig["strength"] == "STRONG" else "#64748B"
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:8px;padding:10px 14px;margin-bottom:6px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'margin-bottom:3px">'
            f'<span style="font-weight:700;color:#F1F5F9;font-size:0.88rem">'
            f'{sig["icon"]} {sig["type"]}</span>'
            f'<span style="background:{badge_clr}33;color:{badge_clr};font-size:0.7rem;'
            f'font-weight:700;padding:1px 7px;border-radius:4px;letter-spacing:.05em">'
            f'{sig["strength"]}</span>'
            f'</div>'
            f'<div style="font-size:0.78rem;color:#94A3B8;margin-bottom:3px">{sig["desc"]}</div>'
            f'<div style="font-size:0.75rem;color:#64748B">'
            f'@ ${sig["price"]:,.2f} &nbsp;'
            f'<span style="color:{dist_clr}">{sig["dist"]:+.2f}%</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Gamma Squeeze computation ──────────────────────────────────────────────────

def _compute_gamma_squeeze(
    gex_df: pd.DataFrame,
    oi_df: pd.DataFrame,
    pc: dict | None,
    current_price: float,
) -> dict:
    factors: dict[str, int] = {}

    # 1. Gamma Regime (0-30): negative GEX = dealers amplify = squeeze fuel
    gamma_score = 0
    if not gex_df.empty:
        total_gex = float(gex_df["gex"].sum())
        if total_gex < 0:
            gamma_score = min(30, int(abs(total_gex) / 1e8))
    factors["Gamma Regime"] = gamma_score

    # 2. Call Wall Proximity (0-25): price approaching call wall from below
    call_score = 0
    if not oi_df.empty:
        call_wall = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"])
        dist = (call_wall - current_price) / current_price * 100
        if 0 < dist <= 0.5:
            call_score = 25
        elif 0 < dist <= 1.0:
            call_score = 20
        elif 0 < dist <= 2.0:
            call_score = 15
        elif 0 < dist <= 3.0:
            call_score = 10
    factors["Call Wall Proximity"] = call_score

    # 3. Flow Alignment (0-20): low P/C = call-heavy flow = bullish squeeze
    flow_score = 0
    if pc:
        r = pc["ratio"]
        flow_score = 20 if r < 0.6 else 15 if r < 0.8 else 10 if r < 1.0 else 5 if r < 1.2 else 0
    factors["Flow Alignment"] = flow_score

    # 4. Volume Confirm (0-15): call OI dominance in the chain
    vol_score = 0
    if not oi_df.empty:
        total_c = float(oi_df["call_oi"].sum())
        total_p = float(oi_df["put_oi"].sum())
        if total_c + total_p > 0:
            call_share = total_c / (total_c + total_p)
            vol_score = 15 if call_share > 0.65 else 10 if call_share > 0.55 else 5 if call_share > 0.45 else 0
    factors["Volume Confirm"] = vol_score

    # 5. DEX Bias (0-10): net near-ATM GEX direction
    dex_score = 0
    if not gex_df.empty:
        near = gex_df[(gex_df["strike"] >= current_price * 0.98) &
                      (gex_df["strike"] <= current_price * 1.02)]
        near_gex = float(near["gex"].sum()) if not near.empty else 0
        dex_score = 10 if near_gex > 0 else 5 if near_gex > -1e8 else 0
    factors["DEX Bias"] = dex_score

    total = sum(factors.values())
    if total >= 75:
        label, badge_color = "Imminent", "#EF4444"
    elif total >= 50:
        label, badge_color = "Likely",   "#F59E0B"
    elif total >= 25:
        label, badge_color = "Possible", "#A78BFA"
    else:
        label, badge_color = "Unlikely", "#475569"

    pc_ratio = pc["ratio"] if pc else 1.0
    direction = "Bullish Squeeze" if pc_ratio < 1.0 else "Bearish Squeeze"
    bias_label = "BULLISH BIAS" if pc_ratio < 1.0 else "BEARISH BIAS"
    bias_color = "#22C55E" if pc_ratio < 1.0 else "#EF4444"

    return {"score": total, "label": label, "badge_color": badge_color,
            "factors": factors, "direction": direction,
            "bias_label": bias_label, "bias_color": bias_color}


def _render_gamma_squeeze_panel(squeeze: dict) -> None:
    score       = squeeze["score"]
    badge_color = squeeze["badge_color"]
    factors     = squeeze["factors"]
    _MAX = {"Gamma Regime": 30, "Call Wall Proximity": 25,
            "Flow Alignment": 20, "Volume Confirm": 15, "DEX Bias": 10}

    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        'text-transform:uppercase;margin:20px 0 10px">Gamma Squeeze Screener</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
        f'border-radius:10px;padding:16px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<span style="background:{squeeze["bias_color"]}33;color:{squeeze["bias_color"]};'
        f'font-size:0.7rem;font-weight:700;padding:1px 8px;border-radius:4px;'
        f'letter-spacing:.06em">{squeeze["bias_label"]}</span>'
        f'</div>'
        f'<span style="font-weight:700;color:#F1F5F9">{squeeze["direction"]}</span>'
        f'<span style="background:{badge_color}33;color:{badge_color};font-size:0.72rem;'
        f'font-weight:700;padding:2px 10px;border-radius:4px;letter-spacing:.05em">'
        f'{squeeze["label"].upper()}</span>'
        f'</div>'
        f'<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;'
        f'letter-spacing:.06em;margin-bottom:2px">PROBABILITY SCORE</div>'
        f'<div style="font-size:2.2rem;font-weight:900;color:#F1F5F9;line-height:1;'
        f'margin-bottom:10px">{score}'
        f'<span style="font-size:0.9rem;color:#64748B">/100</span></div>'
        f'<div style="background:#1E293B;border-radius:4px;height:6px;margin-bottom:4px">'
        f'<div style="width:{score}%;height:100%;background:{badge_color};border-radius:4px">'
        f'</div></div>'
        f'<div style="display:flex;justify-content:space-between;font-size:0.65rem;'
        f'color:#475569;margin-bottom:14px">'
        f'<span>Unlikely</span><span>Possible</span><span>Likely</span><span>Imminent</span>'
        f'</div>'
        f'<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;'
        f'letter-spacing:.06em;margin-bottom:8px">FACTOR BREAKDOWN</div>',
        unsafe_allow_html=True,
    )
    for factor, val in factors.items():
        max_val = _MAX.get(factor, 10)
        bar_w   = val / max_val * 100 if max_val else 0
        bar_clr = "#22C55E" if bar_w > 60 else "#F59E0B" if bar_w > 30 else "#475569"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">'
            f'<span style="font-size:0.8rem;color:#94A3B8;width:150px;white-space:nowrap">'
            f'{factor}</span>'
            f'<div style="flex:1;background:#1E293B;border-radius:3px;height:5px">'
            f'<div style="width:{bar_w:.0f}%;height:100%;background:{bar_clr};border-radius:3px">'
            f'</div></div>'
            f'<span style="font-size:0.82rem;color:#F1F5F9;width:22px;text-align:right">'
            f'{val}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


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


# ── Expander live-text helpers ────────────────────────────────────────────────

def _expander_signal_block(suggestion: dict | None, lbl: str) -> str:
    """Returns a markdown string with live direction-vote rationale."""
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


def _expander_vol_block(suggestion: dict | None, vol: dict | None) -> str:
    """Returns a markdown string showing the IV Rank → strategy decision chain."""
    if not vol:
        return ""
    rank  = vol["iv_rank"]
    bias  = vol["strategy_bias"]
    color_lbl = "High IV" if rank >= 50 else "Mid IV" if rank >= 30 else "Low IV"
    if not suggestion:
        return f"> *Right now: IV Rank **{rank:.0f}%** ({color_lbl}) → **{bias}***\n"
    direction = suggestion["direction"]
    strategy  = suggestion["strategy"]
    hv30      = vol.get("hv30")
    ratio     = vol.get("iv_hv_ratio")
    ratio_str = f" · IV/HV **{ratio:.2f}×**" if ratio else ""
    hv_str    = f" · HV30 **{hv30:.1f}%**" if hv30 else ""
    return (
        f"> *Right now: IV Rank **{rank:.0f}%** ({color_lbl}){hv_str}{ratio_str} → **{bias}***\n"
        f"> Combined with **{direction}** direction → suggested strategy: **{strategy}**\n"
    )


def _expander_levels_block(suggestion: dict | None) -> str:
    """Returns a markdown string with the live reference target, stop, and hold note."""
    if not suggestion:
        return ""
    ref     = suggestion.get("ref_target")
    ref_src = suggestion.get("ref_source", "")
    ref_pct = suggestion.get("ref_pct")
    stop    = suggestion.get("stop_level")
    stp_src = suggestion.get("stop_source", "")
    stp_pct = suggestion.get("stop_pct")
    gap      = suggestion.get("gap_fill")
    gap_pct  = suggestion.get("gap_fill_pct")
    gap_dt   = suggestion.get("gap_fill_date", "")
    gap_type = suggestion.get("gap_fill_type", "")
    hold     = suggestion.get("hold_note", "")
    mp_warn  = suggestion.get("mp_headwind", False)

    def _fmt(price, pct, src):
        if price is None:
            return "N/A"
        sign = "+" if (pct or 0) >= 0 else ""
        return f"**${price:,.2f}** ({sign}{pct:.1f}% · {src})" if pct is not None else f"**${price:,.2f}** ({src})"

    lines = ["> *Right now:*"]
    lines.append(f"> · Target: {_fmt(ref, ref_pct, ref_src)}")
    lines.append(f"> · Stop: {_fmt(stop, stp_pct, stp_src)}")
    if gap is not None and (ref is None or abs(gap - ref) > 0.50):
        gap_parts = [p for p in [gap_type, gap_dt] if p and p != "—"]
        gap_label = "Gap fill" + (" · " + " · ".join(gap_parts) if gap_parts else "")
        lines.append(f"> · Nearest gap fill: {_fmt(gap, gap_pct, gap_label)}")
    if mp_warn:
        lines.append("> · ⚠ Max pain sits between current price and target — may slow progress")
    if hold:
        lines.append(f"> · Hold: {hold}")
    return "\n".join(lines) + "\n"


# ── "What is?" expander ────────────────────────────────────────────────────────

def _render_what_is_expander(
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

    # ── Vol regime live text ──────────────────────────────────────────────────
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
            f'IV Rank **{rank:.0f}%** ({rank_lbl}) · VIX **{iv30:.1f}%** · '
            f'**{vol["strategy_bias"]}**.'
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

{_expander_vol_block(suggestion, vol)}

---

**Step 3 · Reference Levels (price magnets, not guaranteed exits)**

- **Target**: the nearest meaningful level in the trade direction. Priority order: unfilled gap fill → OI wall → expected move boundary → max pain. When two levels cluster together it's a stronger signal.
- **Unfilled gap fills**: when SPY gaps up or down and never revisits the open edge of that gap, the level becomes a price magnet — the market tends to return to fill it. A gap fill target near an OI wall is especially strong.
- **Stop / Invalidation**: the level that disproves the trade thesis. If price crosses it, the logic behind the trade is no longer valid. Set from the opposing OI wall or the EM boundary.
- **Hold condition**: if GEX is positive (dealers long gamma), small dips get absorbed — stay patient. If GEX is negative (short gamma), moves can run fast and reverse hard — exit near the target rather than holding for more.

{_expander_levels_block(suggestion)}

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


# ── Strategy Suggester card ────────────────────────────────────────────────────

def _render_strategy_card(suggestion: dict | None, exp_label: str = "", exp_iso: str = "") -> None:
    if not suggestion:
        return

    strat_clr  = suggestion["strat_color"]
    dir_clr    = suggestion["dir_color"]
    conf_clr   = suggestion["conf_color"]
    vb_clr     = suggestion["vb_color"]
    em_range   = (f'${suggestion["em_low"]:,.2f} – ${suggestion["em_high"]:,.2f}'
                  if suggestion["em_low"] and suggestion["em_high"] else "—")
    strike_str = suggestion["strike_label"] or "—"

    # Derive a context-aware title from the expiration label
    if exp_label:
        dte_part = exp_label.split("(")[-1].rstrip(")").strip() if "(" in exp_label else ""
        try:
            dte_num = int(dte_part.rstrip("d"))
        except (ValueError, AttributeError):
            dte_num = 7
        if dte_num == 0:
            setup_title = f"Today's Setup · {exp_label}"
        elif dte_num <= 2:
            setup_title = f"Near-Term Setup · {exp_label}"
        elif dte_num <= 9:
            setup_title = f"This Week's Setup · {exp_label}"
        elif dte_num <= 35:
            setup_title = f"This Month's Setup · {exp_label}"
        else:
            setup_title = f"Longer-Term Setup · {exp_label}"
    else:
        setup_title = "This Week's Setup"

    rationale_html = "".join(
        f'<div style="font-size:0.77rem;color:#94A3B8;margin-bottom:3px">◆ {r}</div>'
        for r in suggestion["rationale"]
    )

    # ── Reference levels rendering helpers ───────────────────────────────────
    ref_target  = suggestion.get("ref_target")
    ref_source  = suggestion.get("ref_source", "—")
    ref_pct     = suggestion.get("ref_pct")
    stop_level  = suggestion.get("stop_level")
    stop_source = suggestion.get("stop_source", "—")
    stop_pct    = suggestion.get("stop_pct")
    gap_fill      = suggestion.get("gap_fill")
    gap_fill_pct  = suggestion.get("gap_fill_pct")
    gap_fill_date = suggestion.get("gap_fill_date")
    gap_fill_type = suggestion.get("gap_fill_type", "")
    mp_headwind   = suggestion.get("mp_headwind", False)
    hold_note   = suggestion.get("hold_note", "")
    direction   = suggestion["direction"]

    tgt_clr  = "#22C55E" if direction == "Bullish" else "#EF4444" if direction == "Bearish" else "#A78BFA"
    stop_clr = "#EF4444" if direction == "Bullish" else "#22C55E" if direction == "Bearish" else "#F59E0B"

    def _level_html(price: float | None, pct: float | None, source: str, color: str, extra: str = "") -> str:
        if price is None:
            return f'<span style="font-size:0.82rem;font-weight:700;color:#475569">—</span>'
        sign  = "+" if (pct or 0) >= 0 else ""
        pct_s = f"{sign}{pct:.1f}%" if pct is not None else ""
        ex    = f" · {extra}" if extra else ""
        return (
            f'<span style="font-size:0.85rem;font-weight:700;color:{color}">${price:,.2f}</span>'
            f'<span style="font-size:0.7rem;color:#64748B;margin-left:4px">{pct_s} · {source}{ex}</span>'
        )

    ref_html  = _level_html(ref_target,  ref_pct,       ref_source,  tgt_clr)
    stop_html = _level_html(stop_level,  stop_pct,      stop_source, stop_clr)
    # Show gap fill row only if it differs from the primary reference target
    show_gap  = (gap_fill is not None
                 and (ref_target is None or abs(gap_fill - ref_target) > 0.50))
    _gap_type_parts = [p for p in [gap_fill_type, gap_fill_date] if p and p != "—"]
    _gap_src  = "Gap fill" + (" · " + " · ".join(_gap_type_parts) if _gap_type_parts else "")
    gap_html  = (_level_html(gap_fill, gap_fill_pct, _gap_src, "#F59E0B")
                 if show_gap else "")

    mp_warn = (
        f'<div style="font-size:0.72rem;color:#F59E0B;margin-top:5px">'
        f'⚠ Max pain may act as friction before target</div>'
        if mp_headwind else ""
    )
    hold_html = (
        f'<div style="font-size:0.72rem;color:#94A3B8;margin-top:5px">⟳ {hold_note}</div>'
        if hold_note else ""
    )
    gap_row = (
        f'<div style="margin-top:6px">'
        f'<span style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.06em">Gap Fill &nbsp;</span>'
        f'{gap_html}</div>'
        if show_gap else ""
    )

    ref_levels_html = (
        f'<div style="margin-top:12px;padding-top:10px;border-top:1px solid #1E293B">'
        f'<div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">'
        f'Reference Levels</div>'
        f'<div style="display:flex;gap:32px;flex-wrap:wrap;align-items:flex-start">'
        f'<div><div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px">Target</div>'
        f'<div>{ref_html}</div></div>'
        f'<div><div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px">Stop / Invalidation</div>'
        f'<div>{stop_html}</div></div>'
        f'</div>'
        f'{gap_row}'
        f'{mp_warn}'
        f'{hold_html}'
        f'</div>'
    )

    _sc1, _sc2 = st.columns([12, 1])
    with _sc2:
        with st.popover("🔗", use_container_width=True, help="Share this strategy card"):
            st.code(_share_url("/spy-trade-idea", exp_iso), language=None)
            st.caption("Copy the link above to share this strategy card.")

    c_main, c_why = st.columns([3, 2])
    with c_main:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-left:4px solid {strat_clr};border-radius:10px;padding:16px 20px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
            f'<span style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
            f'text-transform:uppercase">{setup_title}</span>'
            f'<span style="background:{conf_clr}22;color:{conf_clr};font-size:0.68rem;font-weight:700;'
            f'padding:2px 8px;border-radius:4px;letter-spacing:.06em">'
            f'{suggestion["confidence"]} CONFIDENCE</span>'
            f'</div>'
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
            f'<span style="font-size:28px;font-weight:900;color:{strat_clr};line-height:1">'
            f'{suggestion["strategy"]}</span>'
            f'<span style="background:{dir_clr}22;color:{dir_clr};font-size:0.7rem;font-weight:700;'
            f'padding:2px 8px;border-radius:4px;letter-spacing:.05em">'
            f'{suggestion["direction"].upper()}</span>'
            f'<span style="background:{vb_clr}22;color:{vb_clr};font-size:0.7rem;font-weight:700;'
            f'padding:2px 8px;border-radius:4px;letter-spacing:.05em">'
            f'{suggestion["vol_bias"]}</span>'
            f'</div>'
            f'<div style="font-size:0.8rem;color:#94A3B8;margin-bottom:12px">'
            f'{suggestion["strat_note"]}</div>'
            f'<div style="display:flex;gap:28px;flex-wrap:wrap">'
            f'<div><div style="font-size:9px;color:#64748B;text-transform:uppercase;'
            f'letter-spacing:.06em;margin-bottom:2px">Strike Hints</div>'
            f'<div style="font-size:0.82rem;font-weight:700;color:#F1F5F9">{strike_str}</div></div>'
            f'<div><div style="font-size:9px;color:#64748B;text-transform:uppercase;'
            f'letter-spacing:.06em;margin-bottom:2px">EM Range</div>'
            f'<div style="font-size:0.82rem;font-weight:700;color:#A78BFA">{em_range}</div></div>'
            f'</div>'
            f'{ref_levels_html}'
            f'<div style="font-size:9px;color:#475569;margin-top:10px">'
            f'Not financial advice · Strike hints ≈ 30%/60% of expected move · Reference levels are price magnets, not guaranteed exits</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c_why:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:10px;padding:16px">'
            f'<div style="font-size:9px;color:#64748B;text-transform:uppercase;'
            f'letter-spacing:.06em;margin-bottom:8px">Why this strategy</div>'
            f'{rationale_html}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Volatility Regime bar ─────────────────────────────────────────────────────

def _render_vol_regime_bar(vol: dict | None) -> None:
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
            f'<div style="background:#1E293B;border-radius:3px;height:4px;margin-bottom:6px">'
            f'<div style="width:{min(rank,100):.0f}%;height:100%;background:{rank_clr};border-radius:3px"></div></div>'
            f'<div style="font-size:11px;font-weight:700;color:{rank_clr}">{rank_lbl}</div>'
            f'<div style="font-size:9px;color:#64748B;margin-top:4px">'
            f'52w: {vol["vix_52lo"]:.1f} – {vol["vix_52hi"]:.1f}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:10px;padding:14px 16px;min-height:140px;box-sizing:border-box">'
            f'<div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;'
            f'text-transform:uppercase;margin-bottom:4px">HV30 · Realized</div>'
            f'<div style="font-size:36px;font-weight:900;color:{hv_clr};line-height:1;margin-bottom:4px">'
            f'{hv30_str}</div>'
            f'<div style="font-size:10px;color:#94A3B8;margin-top:10px;line-height:1.6">'
            f'30-day annualized<br>realized volatility</div>'
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
            f'<div style="font-size:10px;color:#94A3B8;margin-top:10px;line-height:1.6">'
            f'30-day implied vol<br>annualized · CBOE VIX</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:10px;padding:14px 16px;min-height:140px;box-sizing:border-box">'
            f'<div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;'
            f'text-transform:uppercase;margin-bottom:4px">IV / HV Ratio</div>'
            f'<div style="font-size:36px;font-weight:900;color:{ratio_clr};line-height:1;margin-bottom:6px">'
            f'{ratio_str}</div>'
            f'<div style="display:inline-block;background:{vol["strategy_color"]}33;'
            f'color:{vol["strategy_color"]};font-size:0.7rem;font-weight:700;'
            f'padding:2px 8px;border-radius:4px;letter-spacing:.05em">'
            f'{vol["strategy_bias"]}</div>'
            f'<div style="font-size:9px;color:#64748B;margin-top:6px;line-height:1.5">'
            f'{vol["strategy_note"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Flow Sweep panel ──────────────────────────────────────────────────────────

def _render_sweep_panel(sweep_df: pd.DataFrame, exp_label: str = "", fetched_at: str = "") -> None:
    time_note = f' <span style="font-weight:400;color:#475569;letter-spacing:0;text-transform:none">&nbsp;·&nbsp; as of {fetched_at}</span>' if fetched_at else ""
    exp_note  = f' — {exp_label}' if exp_label else ""
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        f'text-transform:uppercase;margin:20px 0 10px">'
        f'⚡ Flow Sweeps{exp_note}{time_note}</div>',
        unsafe_allow_html=True,
    )
    if sweep_df.empty:
        st.caption("No unusual sweep activity detected for this expiration.")
        return

    # Header row
    st.markdown(
        '<div style="display:grid;grid-template-columns:60px 80px 80px 80px 80px 70px 70px;'
        'gap:4px;padding:4px 10px;font-size:0.68rem;font-weight:700;color:#64748B;'
        'letter-spacing:.07em;text-transform:uppercase;border-bottom:1px solid #1E293B;'
        'margin-bottom:4px">'
        '<span>Side</span><span>Strike</span><span>Vol/OI</span>'
        '<span>Volume</span><span>OI</span><span>IV</span><span>OTM</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    for _, row in sweep_df.iterrows():
        is_call   = row["side"] == "CALL"
        side_clr  = "#22C55E" if is_call else "#EF4444"
        otm_sign  = "+" if row["otm_pct"] > 0 else ""
        iv_pct    = f'{row["iv"] * 100:.0f}%' if row["iv"] > 0 else "—"
        ratio_clr = "#F59E0B" if row["vol_oi_ratio"] >= 10 else "#A78BFA" if row["vol_oi_ratio"] >= 5 else "#94A3B8"
        st.markdown(
            f'<div style="display:grid;grid-template-columns:60px 80px 80px 80px 80px 70px 70px;'
            f'gap:4px;padding:5px 10px;font-size:0.8rem;color:#F1F5F9;'
            f'background:rgba(255,255,255,0.02);border-radius:5px;margin-bottom:2px;'
            f'border-left:3px solid {side_clr}">'
            f'<span style="font-weight:700;color:{side_clr}">{row["side"]}</span>'
            f'<span>${row["strike"]:,.0f}</span>'
            f'<span style="font-weight:700;color:{ratio_clr}">{row["vol_oi_ratio"]:.1f}x</span>'
            f'<span>{int(row["volume"]):,}</span>'
            f'<span>{int(row["open_interest"]):,}</span>'
            f'<span>{iv_pct}</span>'
            f'<span style="color:#94A3B8">{otm_sign}{row["otm_pct"]:.1f}%</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="font-size:0.7rem;color:#475569;margin-top:6px">'
        'Vol/OI ≥ 3× on OTM strikes = aggressive new positioning (sweep proxy). '
        'Yellow = 10×+ · Purple = 5-10× · Grey = 3-5×. Source: Yahoo Finance (15-min delay).'
        '</div>',
        unsafe_allow_html=True,
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
