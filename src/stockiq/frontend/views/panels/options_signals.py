"""
Options Intelligence signal panels: dealer levels, gamma squeeze, flow sweeps, multi-exp OI.

Public API:
  compute_signals(gex_df, oi_df, current_price, max_pain, exp_label) -> list[dict]
  render_signals_panel(signals)
  compute_gamma_squeeze(gex_df, oi_df, pc, current_price) -> dict
  render_gamma_squeeze_panel(squeeze)
  render_sweep_panel(sweep_df, exp_label, fetched_at)
  fetch_multi_exp_oi(expirations, exp_labels, current_price) -> (call_pivot, put_pivot)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st

from stockiq.backend.services.spy_service import get_spy_options_analysis


def compute_signals(
    gex_df: pd.DataFrame,
    oi_df: pd.DataFrame,
    current_price: float,
    max_pain: float,
    exp_label: str = "",
) -> list[dict]:
    signals: list[dict] = []
    gex_threshold = gex_df["gex"].abs().quantile(0.75) if not gex_df.empty else 0

    if not gex_df.empty:
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
        exp_note = f" · expires {exp_label}" if exp_label else ""
        signals.append({"type": "Max Pain", "icon": "◎",
                         "desc": f"Strike where all open contracts expire worthless — price gravitates here{exp_note}",
                         "price": max_pain,
                         "dist": (max_pain - current_price) / current_price * 100,
                         "strength": "STRONG", "color": "#A78BFA"})

    signals.sort(key=lambda x: abs(x["dist"]))
    return signals[:5]


def render_signals_panel(signals: list[dict]) -> None:
    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        'text-transform:uppercase;margin:20px 0 10px">⚡ Dealer Levels</div>',
        unsafe_allow_html=True,
    )
    if not signals:
        st.caption("Insufficient options data for signals.")
        return
    for sig in signals:
        dist_clr  = "#22C55E" if sig["dist"] >= 0 else "#EF4444"
        badge_clr = "#F59E0B" if sig["strength"] == "STRONG" else "#64748B"
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
            f'border-radius:8px;padding:10px 14px;margin-bottom:6px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">'
            f'<span style="font-weight:700;color:#F1F5F9;font-size:0.88rem">{sig["icon"]} {sig["type"]}</span>'
            f'<span style="background:{badge_clr}33;color:{badge_clr};font-size:0.7rem;font-weight:700;'
            f'padding:1px 7px;border-radius:4px;letter-spacing:.05em">{sig["strength"]}</span>'
            f'</div>'
            f'<div style="font-size:0.78rem;color:#94A3B8;margin-bottom:3px">{sig["desc"]}</div>'
            f'<div style="font-size:0.75rem;color:#64748B">@ ${sig["price"]:,.2f} &nbsp;'
            f'<span style="color:{dist_clr}">{sig["dist"]:+.2f}%</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def compute_gamma_squeeze(
    gex_df: pd.DataFrame,
    oi_df: pd.DataFrame,
    pc: dict | None,
    current_price: float,
) -> dict:
    factors: dict[str, int] = {}

    gamma_score = 0
    if not gex_df.empty:
        total_gex = float(gex_df["gex"].sum())
        if total_gex < 0:
            # SPY net negative GEX typically ranges $50M–$500M; score scales 0–30.
            gamma_score = min(30, int(abs(total_gex) / 1e7))
    factors["Gamma Regime"] = gamma_score

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

    flow_score = 0
    if pc:
        r = pc["ratio"]
        flow_score = 20 if r < 0.6 else 15 if r < 0.8 else 10 if r < 1.0 else 5 if r < 1.2 else 0
    factors["Flow Alignment"] = flow_score

    vol_score = 0
    if not oi_df.empty:
        total_c = float(oi_df["call_oi"].sum())
        total_p = float(oi_df["put_oi"].sum())
        if total_c + total_p > 0:
            call_share = total_c / (total_c + total_p)
            vol_score = 15 if call_share > 0.65 else 10 if call_share > 0.55 else 5 if call_share > 0.45 else 0
    factors["Volume Confirm"] = vol_score

    dex_score = 0
    if not gex_df.empty:
        near = gex_df[(gex_df["strike"] >= current_price * 0.98) & (gex_df["strike"] <= current_price * 1.02)]
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

    pc_ratio   = pc["ratio"] if pc else 1.0
    direction  = "Bullish Squeeze" if pc_ratio < 1.0 else "Bearish Squeeze"
    bias_label = "BULLISH BIAS"    if pc_ratio < 1.0 else "BEARISH BIAS"
    bias_color = "#22C55E"         if pc_ratio < 1.0 else "#EF4444"

    return {"score": total, "label": label, "badge_color": badge_color,
            "factors": factors, "direction": direction,
            "bias_label": bias_label, "bias_color": bias_color}


def render_gamma_squeeze_panel(squeeze: dict) -> None:
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
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<span style="background:{squeeze["bias_color"]}33;color:{squeeze["bias_color"]};'
        f'font-size:0.7rem;font-weight:700;padding:1px 8px;border-radius:4px;letter-spacing:.06em">{squeeze["bias_label"]}</span>'
        f'</div>'
        f'<span style="font-weight:700;color:#F1F5F9">{squeeze["direction"]}</span>'
        f'<span style="background:{badge_color}33;color:{badge_color};font-size:0.72rem;'
        f'font-weight:700;padding:2px 10px;border-radius:4px;letter-spacing:.05em">{squeeze["label"].upper()}</span>'
        f'</div>'
        f'<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px">PROBABILITY SCORE</div>'
        f'<div style="font-size:2.2rem;font-weight:900;color:#F1F5F9;line-height:1;margin-bottom:10px">'
        f'{score}<span style="font-size:0.9rem;color:#64748B">/100</span></div>'
        f'<div style="background:linear-gradient(to right,{badge_color} {score}%,#1E293B {score}%);'
        f'border-radius:4px;height:6px;margin-bottom:4px"></div>'
        f'<div style="display:flex;justify-content:space-between;font-size:0.65rem;color:#475569;margin-bottom:14px">'
        f'<span>Unlikely</span><span>Possible</span><span>Likely</span><span>Imminent</span></div>'
        f'<div style="font-size:0.7rem;color:#64748B;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">FACTOR BREAKDOWN</div>',
        unsafe_allow_html=True,
    )
    for factor, val in factors.items():
        max_val = _MAX.get(factor, 10)
        bar_w   = val / max_val * 100 if max_val else 0
        bar_clr = "#22C55E" if bar_w > 60 else "#F59E0B" if bar_w > 30 else "#475569"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">'
            f'<span style="font-size:0.8rem;color:#94A3B8;width:150px;white-space:nowrap">{factor}</span>'
            f'<div style="flex:1;background:linear-gradient(to right,{bar_clr} {bar_w:.0f}%,#1E293B {bar_w:.0f}%);'
            f'border-radius:3px;height:5px"></div>'
            f'<span style="font-size:0.82rem;color:#F1F5F9;width:22px;text-align:right">{val}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def render_sweep_panel(sweep_df: pd.DataFrame, exp_label: str = "", fetched_at: str = "") -> None:
    time_note = (
        f' <span style="font-weight:400;color:#475569;letter-spacing:0;text-transform:none">&nbsp;·&nbsp; as of {fetched_at}</span>'
        if fetched_at else ""
    )
    exp_note = f' — {exp_label}' if exp_label else ""
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        f'text-transform:uppercase;margin:20px 0 10px">⚡ Flow Sweeps{exp_note}{time_note}</div>',
        unsafe_allow_html=True,
    )
    if sweep_df.empty:
        st.caption("No unusual sweep activity detected for this expiration.")
        return

    st.markdown(
        '<div style="display:grid;grid-template-columns:60px 80px 80px 80px 80px 70px 70px;'
        'gap:4px;padding:4px 10px;font-size:0.68rem;font-weight:700;color:#64748B;'
        'letter-spacing:.07em;text-transform:uppercase;border-bottom:1px solid #1E293B;margin-bottom:4px">'
        '<span>Side</span><span>Strike</span><span>Vol/OI</span>'
        '<span>Volume</span><span>OI</span><span>IV</span><span>OTM</span></div>',
        unsafe_allow_html=True,
    )
    for _, row in sweep_df.iterrows():
        is_call  = row["side"] == "CALL"
        side_clr = "#22C55E" if is_call else "#EF4444"
        otm_sign = "+" if row["otm_pct"] > 0 else ""
        iv_pct   = f'{row["iv"] * 100:.0f}%' if row["iv"] > 0 else "—"
        ratio_clr = "#F59E0B" if row["vol_oi_ratio"] >= 10 else "#A78BFA" if row["vol_oi_ratio"] >= 5 else "#94A3B8"
        st.markdown(
            f'<div style="display:grid;grid-template-columns:60px 80px 80px 80px 80px 70px 70px;'
            f'gap:4px;padding:5px 10px;font-size:0.8rem;color:#F1F5F9;'
            f'background:rgba(255,255,255,0.02);border-radius:5px;margin-bottom:2px;border-left:3px solid {side_clr}">'
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


def fetch_multi_exp_oi(
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
