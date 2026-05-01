"""0DTE Conditions Meter panel — evaluates live signals and suggests a trade."""

import pandas as pd
import streamlit as st

from stockiq.backend.services.spy_service import get_spy_options_analysis


def render_dte_conditions(
    current_price: float,
    vix_snapshot: dict | None,
    rsi: float | None,
    pc_data: dict | None,
    vwap: float | None = None,
    or_high: float | None = None,
    or_low: float | None = None,
    pdh: float | None = None,
    pdl: float | None = None,
    prev_close: float | None = None,
) -> None:
    try:
        seed      = get_spy_options_analysis(expiration="", current_price=current_price)
        max_pain  = seed["max_pain"]                    if seed else None
        gex_df    = seed.get("gex_df", pd.DataFrame()) if seed else pd.DataFrame()
        total_gex = gex_df["gex"].sum()                if not gex_df.empty else None
    except Exception:
        seed = None
        max_pain = total_gex = None

    signals, call_pts, put_pts = _evaluate_signals(
        current_price, vix_snapshot, rsi, pc_data, max_pain, total_gex,
        vwap, or_high, or_low, pdh, pdl, prev_close,
    )

    net         = call_pts - put_pts
    scored      = call_pts + put_pts
    neutral_pts = len(signals) - scored
    v_label, v_color, v_icon, v_note = _verdict(net)
    trade_html  = _trade_suggestion(net, seed, current_price, max_pain) if net != 0 and seed else ""

    trade_content = trade_html or _neutral_panel()
    st.html(
        _section_header() +
        '<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
        'border-radius:12px;padding:18px 20px;margin-bottom:14px">' +
        _verdict_card(v_label, v_color, v_icon, v_note, call_pts, put_pts, neutral_pts, len(signals)) +
        '<div style="border-top:1px solid #1E293B;margin:16px 0"></div>' +
        trade_content +
        '</div>'
    )

    call_n    = sum(1 for s in signals if s[2] == "CALL")
    put_n     = sum(1 for s in signals if s[2] == "PUT")
    neutral_n = len(signals) - call_n - put_n
    label     = f"Signals — {call_n} Call · {neutral_n} Neutral · {put_n} Put"
    with st.expander(label, expanded=False):
        st.html(_signal_table(signals))


# ── Signal evaluation ──────────────────────────────────────────────────────────

def _evaluate_signals(
    current_price, vix_snapshot, rsi, pc_data, max_pain, total_gex,
    vwap=None, or_high=None, or_low=None, pdh=None, pdl=None, prev_close=None,
):
    signals: list[tuple] = []
    call_pts = put_pts = 0

    vix_val = vix_snapshot.get("current") if vix_snapshot else None
    if vix_val is not None:
        if vix_val < 16:
            signals.append(("VIX", f"{vix_val:.1f}", "CALL", "Cheap options — good day to buy directional calls", "#22C55E"))
            call_pts += 1
        elif vix_val > 25:
            signals.append(("VIX", f"{vix_val:.1f}", "NEUTRAL", "Fear elevated — sell premium (condors/spreads), not directional", "#F59E0B"))
        else:
            signals.append(("VIX", f"{vix_val:.1f}", "NEUTRAL", "Mid-range — no strong options-price edge", "#94A3B8"))
    else:
        signals.append(("VIX", "N/A", "—", "Unavailable", "#475569"))

    if pc_data:
        r = pc_data["ratio"]
        if r < 0.80:
            signals.append(("P/C Ratio", f"{r:.3f}", "CALL", "More calls than puts — market leans bullish", "#22C55E"))
            call_pts += 1
        elif r > 1.10:
            signals.append(("P/C Ratio", f"{r:.3f}", "PUT",  "Fear/hedging dominant — put volume heavy", "#EF4444"))
            put_pts += 1
        else:
            signals.append(("P/C Ratio", f"{r:.3f}", "NEUTRAL", "Balanced put/call positioning", "#94A3B8"))
    else:
        signals.append(("P/C Ratio", "N/A", "—", "Unavailable", "#475569"))

    if max_pain:
        dist = (current_price - max_pain) / max_pain * 100
        if dist > 1.0:
            signals.append(("Max Pain", f"${max_pain:,.0f}", "CALL", f"Price {dist:+.1f}% above — bullish price action", "#22C55E"))
            call_pts += 1
        elif dist < -1.0:
            signals.append(("Max Pain", f"${max_pain:,.0f}", "PUT",  f"Price {dist:+.1f}% below — bearish gravitational pull", "#EF4444"))
            put_pts += 1
        else:
            signals.append(("Max Pain", f"${max_pain:,.0f}", "NEUTRAL", f"Pinned near pain ({dist:+.1f}%) — sideways expected", "#94A3B8"))
    else:
        signals.append(("Max Pain", "N/A", "—", "Unavailable", "#475569"))

    if total_gex is not None:
        gb = total_gex / 1e9
        if total_gex >= 0:
            signals.append(("GEX", f"{gb:+.1f}B", "CALL", "Dealers buy dips & sell rips — market pinned up", "#22C55E"))
            call_pts += 1
        else:
            signals.append(("GEX", f"{gb:+.1f}B", "PUT",  "Dealers amplify moves — drops can accelerate", "#EF4444"))
            put_pts += 1
    else:
        signals.append(("GEX", "N/A", "—", "Unavailable", "#475569"))

    if rsi is not None:
        if rsi >= 55:
            signals.append(("RSI (1d)", f"{rsi:.1f}", "CALL", "Above 55 — bullish daily momentum", "#22C55E"))
            call_pts += 1
        elif rsi <= 45:
            signals.append(("RSI (1d)", f"{rsi:.1f}", "PUT",  "Below 45 — bearish daily momentum", "#EF4444"))
            put_pts += 1
        else:
            signals.append(("RSI (1d)", f"{rsi:.1f}", "NEUTRAL", "45–55 choppy zone — no directional edge", "#94A3B8"))
    else:
        signals.append(("RSI (1d)", "N/A", "—", "Unavailable", "#475569"))

    if vwap is not None:
        dist_pct = (current_price - vwap) / vwap * 100
        if dist_pct > 0.1:
            signals.append(("VWAP", f"${vwap:.2f}", "CALL", f"+{dist_pct:.2f}% above VWAP — intraday trend bullish", "#22C55E"))
            call_pts += 1
        elif dist_pct < -0.1:
            signals.append(("VWAP", f"${vwap:.2f}", "PUT",  f"{dist_pct:.2f}% below VWAP — intraday trend bearish", "#EF4444"))
            put_pts += 1
        else:
            signals.append(("VWAP", f"${vwap:.2f}", "NEUTRAL", f"Hugging VWAP ({dist_pct:+.2f}%) — no intraday edge", "#94A3B8"))
    else:
        signals.append(("VWAP", "N/A", "—", "Intraday data unavailable", "#475569"))

    if or_high is not None and or_low is not None:
        if current_price > or_high:
            signals.append(("OR Break", f">{or_high:.0f}", "CALL", "Above opening range high — trend day, follow the break", "#22C55E"))
            call_pts += 1
        elif current_price < or_low:
            signals.append(("OR Break", f"<{or_low:.0f}", "PUT",  "Below opening range low — trend day breakdown", "#EF4444"))
            put_pts += 1
        else:
            signals.append(("OR Break", f"{or_low:.0f}–{or_high:.0f}", "NEUTRAL", "Inside opening range — wait for a clean break", "#94A3B8"))
    else:
        signals.append(("OR Break", "N/A", "—", "Intraday data unavailable", "#475569"))

    if pdh is not None and pdl is not None:
        if current_price > pdh:
            signals.append(("PDH/PDL", f">${pdh:.0f}", "CALL", "Above prior day high — bulls reclaimed key resistance", "#22C55E"))
            call_pts += 1
        elif current_price < pdl:
            signals.append(("PDH/PDL", f"<${pdl:.0f}", "PUT",  "Below prior day low — bears broke key support", "#EF4444"))
            put_pts += 1
        else:
            signals.append(("PDH/PDL", f"{pdl:.0f}–{pdh:.0f}", "NEUTRAL", "Inside prior day range — no breakout yet", "#94A3B8"))
    else:
        signals.append(("PDH/PDL", "N/A", "—", "Unavailable", "#475569"))

    if prev_close is not None and prev_close > 0:
        gap_pct = (current_price - prev_close) / prev_close * 100
        if gap_pct > 0.5:
            signals.append(("Gap", f"{gap_pct:+.2f}%", "PUT",  f"Large gap up {gap_pct:.2f}% — fade candidate, gap fill likely", "#EF4444"))
            put_pts += 1
        elif gap_pct < -0.5:
            signals.append(("Gap", f"{gap_pct:+.2f}%", "CALL", f"Large gap down {abs(gap_pct):.2f}% — fade candidate, gap fill likely", "#22C55E"))
            call_pts += 1
        elif 0.1 < gap_pct <= 0.5:
            signals.append(("Gap", f"{gap_pct:+.2f}%", "CALL", f"Small gap up {gap_pct:.2f}% — trend follow setup", "#22C55E"))
            call_pts += 1
        elif -0.5 <= gap_pct < -0.1:
            signals.append(("Gap", f"{gap_pct:+.2f}%", "PUT",  f"Small gap down {abs(gap_pct):.2f}% — trend follow setup", "#EF4444"))
            put_pts += 1
        else:
            signals.append(("Gap", f"{gap_pct:+.2f}%", "NEUTRAL", f"Flat open ({gap_pct:+.2f}%) — no gap directional bias", "#94A3B8"))
    else:
        signals.append(("Gap", "N/A", "—", "Unavailable", "#475569"))

    return signals, call_pts, put_pts


def _verdict(net: int) -> tuple:
    if net >= 3:
        return "CALL BIAS",  "#22C55E", "▲", "Strong conditions for call buying or bull spreads"
    if net >= 1:
        return "MILD CALL",  "#86EFAC", "↗", "Slight upside lean — size smaller, defined risk only"
    if net <= -3:
        return "PUT BIAS",   "#EF4444", "▼", "Strong conditions for put buying or bear spreads"
    if net <= -1:
        return "MILD PUT",   "#FCA5A5", "↘", "Slight downside lean — size smaller, defined risk only"
    return "NEUTRAL", "#F59E0B", "↔", "No clear edge — consider iron condors or stay flat"


# ── Option pricing helpers ─────────────────────────────────────────────────────

def _option_mid(chain_df: pd.DataFrame, strike: float) -> float | None:
    """Return mid price for the nearest strike; falls back to lastPrice when bid/ask are stale."""
    if chain_df is None or chain_df.empty:
        return None
    idx = (chain_df["strike"] - strike).abs().idxmin()
    row = chain_df.loc[idx]
    bid  = float(row.get("bid",       0) or 0)
    ask  = float(row.get("ask",       0) or 0)
    last = float(row.get("lastPrice", 0) or 0)
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 2)
    return round(last, 2) if last > 0 else None


def _spx(spy_strike: float) -> int:
    """Approximate SPX / ES / MES index-level equivalent for a SPY strike (~10× ratio)."""
    return round(spy_strike * 10)


# ── Trade suggestion ───────────────────────────────────────────────────────────

def _trade_suggestion(net: int, seed: dict, current_price: float, max_pain: float | None) -> str:
    oi_df    = seed.get("oi_df", pd.DataFrame())
    em_s     = seed.get("expected_move")
    em_move  = em_s["move"] if em_s else 3.0

    call_wall = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"]) if not oi_df.empty else None
    put_wall  = float(oi_df.loc[oi_df["put_oi"].idxmax(), "strike"])  if not oi_df.empty else None
    atm       = round(current_price)

    if net > 0:
        tgt_price, tgt_label = _best_target_call(current_price, em_move, call_wall, max_pain)
        reward    = tgt_price - current_price
        stp_price, stp_label = _best_stop_call(current_price, em_move, reward, put_wall)
        risk      = max(current_price - stp_price, 0.5)
        clr, direction = "#22C55E", "CALL"
        chain_df  = seed.get("raw_calls", pd.DataFrame())
    else:
        tgt_price, tgt_label = _best_target_put(current_price, em_move, put_wall, max_pain)
        reward    = current_price - tgt_price
        stp_price, stp_label = _best_stop_put(current_price, em_move, reward, call_wall)
        risk      = max(stp_price - current_price, 0.5)
        clr, direction = "#EF4444", "PUT"
        chain_df  = seed.get("raw_puts", pd.DataFrame())

    rr     = reward / risk
    rr_clr = "#22C55E" if rr >= 2.0 else "#F59E0B" if rr >= 1.2 else "#EF4444"

    metrics = [
        ("Entry",  f"${atm:,} {direction}", clr),
        ("Target", f"${tgt_price:,}",       clr),
        ("Stop",   f"${stp_price:,}",       "#F59E0B"),
        ("R / R",  f"1 : {rr:.1f}",         rr_clr),
    ]
    grid = "".join(
        f'<div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:10px 12px">'
        f'<div style="font-size:10px;color:#64748B;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">{lbl}</div>'
        f'<div style="font-size:17px;font-weight:800;color:{c};line-height:1">{val}</div>'
        f'</div>'
        for lbl, val, c in metrics
    )

    # ── Option cost + index-level mapping row ──────────────────────────────────
    mid = _option_mid(chain_df, atm)
    mid_str  = f"~${mid:.2f} mid" if mid else "N/A (mkt closed)"
    spx_row  = (
        f'<div style="display:flex;flex-wrap:wrap;gap:16px;align-items:center;'
        f'background:rgba(255,255,255,0.025);border-radius:8px;padding:9px 14px;'
        f'margin-bottom:10px">'
        f'<div>'
        f'<span style="font-size:10px;color:#475569;text-transform:uppercase;'
        f'letter-spacing:.06em">SPY option cost (ATM)</span>&nbsp;&nbsp;'
        f'<span style="font-size:13px;font-weight:700;color:{clr}">{mid_str}</span>'
        f'</div>'
        f'<div style="width:1px;height:24px;background:#1E293B"></div>'
        f'<div style="font-size:11px;color:#64748B">'
        f'<span style="color:#94A3B8;font-weight:600">SPX&thinsp;/&thinsp;ES&thinsp;/&thinsp;MES equiv</span>'
        f'&nbsp;&nbsp;'
        f'Entry&nbsp;<span style="color:#E2E8F0;font-weight:700">{_spx(atm):,}</span>'
        f'&ensp;·&ensp;'
        f'Target&nbsp;<span style="color:{clr};font-weight:700">{_spx(tgt_price):,}</span>'
        f'&ensp;·&ensp;'
        f'Stop&nbsp;<span style="color:#F59E0B;font-weight:700">{_spx(stp_price):,}</span>'
        f'</div>'
        f'</div>'
    )

    return (
        f'<div style="font-size:10px;color:#64748B;font-weight:700;letter-spacing:.07em;'
        f'text-transform:uppercase;margin-bottom:10px">&#127919; Suggested Trade</div>'
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px">'
        f'{grid}</div>'
        f'{spx_row}'
        f'<div style="font-size:11px;color:#475569;line-height:1.6">'
        f'Target: {tgt_label} &nbsp;·&nbsp; Stop: {stp_label}<br>'
        f'&#9200; Enter 9:45 AM–12:00 PM &nbsp;·&nbsp; Close all by 3:45 PM'
        f'</div>'
    )


def _best_target_call(price, em, call_wall, max_pain):
    cands = []
    if call_wall and price + 0.5 < call_wall <= price + em * 1.3:
        cands.append(("call wall", call_wall))
    if max_pain and price + 0.5 < max_pain <= price + em * 1.3:
        cands.append(("max pain", max_pain))
    cands.append(("exp. move ×0.6", price + em * 0.6))
    label, val = cands[0]
    return round(val), label


def _best_stop_call(price, em, reward, put_wall):
    cands = []
    if put_wall and price - em < put_wall < price - 0.5:
        if (price - put_wall) <= reward * 1.5:
            cands.append(("put wall", put_wall))
    cands.append(("1:2 R/R", price - reward / 2))
    label, val = cands[0]
    return round(val), label


def _best_target_put(price, em, put_wall, max_pain):
    cands = []
    if put_wall and price - em * 1.3 <= put_wall < price - 0.5:
        cands.append(("put wall", put_wall))
    if max_pain and price - em * 1.3 <= max_pain < price - 0.5:
        cands.append(("max pain", max_pain))
    cands.append(("exp. move ×0.6", price - em * 0.6))
    label, val = cands[0]
    return round(val), label


def _best_stop_put(price, em, reward, call_wall):
    cands = []
    if call_wall and price + 0.5 < call_wall < price + em:
        if (call_wall - price) <= reward * 1.5:
            cands.append(("call wall", call_wall))
    cands.append(("1:2 R/R", price + reward / 2))
    label, val = cands[0]
    return round(val), label


# ── HTML components ────────────────────────────────────────────────────────────

def _section_header() -> str:
    return (
        '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">'
        '<span style="font-size:13px;font-weight:700;color:#94A3B8;letter-spacing:.06em;text-transform:uppercase">'
        '0DTE Conditions</span>'
        '<span style="font-size:11px;color:#475569">not financial advice</span>'
        '</div>'
    )


def _verdict_card(label, color, icon, note, call_pts, put_pts, neutral_pts, total) -> str:
    # Score bar segments: call (green) | neutral (slate) | put (red)
    bar_segments = ""
    for n, bg in ((call_pts, "#22C55E"), (neutral_pts, "#334155"), (put_pts, "#EF4444")):
        if n > 0:
            bar_segments += (
                f'<div style="flex:{n};background:{bg};height:6px;'
                f'border-radius:3px;transition:flex .3s"></div>'
            )

    pills = (
        f'<span style="font-size:11px;font-weight:700;color:#22C55E;'
        f'background:rgba(34,197,94,.15);border-radius:5px;padding:3px 8px">'
        f'▲ {call_pts} CALL</span>'
        f'<span style="font-size:11px;font-weight:700;color:#94A3B8;'
        f'background:rgba(148,163,184,.12);border-radius:5px;padding:3px 8px">'
        f'→ {neutral_pts} NEUT</span>'
        f'<span style="font-size:11px;font-weight:700;color:#EF4444;'
        f'background:rgba(239,68,68,.15);border-radius:5px;padding:3px 8px">'
        f'▼ {put_pts} PUT</span>'
    )

    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'gap:16px;flex-wrap:wrap;margin-bottom:12px">'
        f'<div>'
        f'<div style="font-size:26px;font-weight:900;color:{color};line-height:1;'
        f'letter-spacing:-.5px">{icon} {label}</div>'
        f'<div style="font-size:12px;color:#64748B;margin-top:5px">{note}</div>'
        f'</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap">{pills}</div>'
        f'</div>'
        f'<div style="display:flex;gap:3px;border-radius:4px;overflow:hidden">'
        f'{bar_segments}'
        f'</div>'
    )


def _neutral_panel() -> str:
    return (
        '<div style="font-size:10px;color:#64748B;font-weight:700;letter-spacing:.07em;'
        'text-transform:uppercase;margin-bottom:10px">&#129300; No Directional Edge</div>'
        '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:10px">'
        '<div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:10px 12px">'
        '<div style="font-size:10px;color:#64748B;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Strategy</div>'
        '<div style="font-size:15px;font-weight:700;color:#F59E0B">Iron Condor / Fly</div>'
        '</div>'
        '<div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:10px 12px">'
        '<div style="font-size:10px;color:#64748B;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Edge</div>'
        '<div style="font-size:15px;font-weight:700;color:#F59E0B">Theta Decay</div>'
        '</div>'
        '</div>'
        '<div style="font-size:11px;color:#475569;line-height:1.6">'
        'Sell premium, let theta work for you<br>'
        '&#9200; No new entries after 12:00 PM &nbsp;·&nbsp; Close all by 3:45 PM'
        '</div>'
    )


_BIAS_ICON = {"CALL": "▲", "PUT": "▼", "NEUTRAL": "→", "—": "·"}
_ROW_BG    = ("rgba(255,255,255,0.025)", "transparent")


def _signal_table(signals: list) -> str:
    header = (
        '<div style="display:grid;grid-template-columns:90px 90px 90px 1fr;'
        'gap:0 12px;padding:5px 12px 7px;border-bottom:1px solid #1E293B;margin-bottom:2px">'
        '<div style="font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:.07em">Signal</div>'
        '<div style="font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:.07em">Value</div>'
        '<div style="font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:.07em">Bias</div>'
        '<div style="font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:.07em">Reading</div>'
        '</div>'
    )
    rows = ""
    for i, (label, value, bias, note, clr) in enumerate(signals):
        icon     = _BIAS_ICON.get(bias, "·")
        bias_clr = clr if bias in ("CALL", "PUT") else "#64748B"
        val_clr  = clr if bias in ("CALL", "PUT") else "#E2E8F0"
        rows += (
            f'<div style="display:grid;grid-template-columns:90px 90px 90px 1fr;'
            f'gap:0 12px;align-items:start;padding:7px 12px;'
            f'background:{_ROW_BG[i % 2]};border-radius:6px">'
            f'<div style="font-size:11px;color:#94A3B8;font-weight:600">{label}</div>'
            f'<div style="font-size:13px;font-weight:700;color:{val_clr}">{value}</div>'
            f'<div style="font-size:12px;font-weight:700;color:{bias_clr}">{icon} {bias if bias != "—" else "—"}</div>'
            f'<div style="font-size:11px;color:#64748B;line-height:1.5">{note}</div>'
            f'</div>'
        )
    return header + rows
