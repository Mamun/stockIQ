"""RSI-based structural top detection panel."""

import streamlit as st


def render_rsi_top_signals(analysis: dict) -> None:
    if not analysis:
        return

    signals   = _build_signals(analysis)
    confluence = _confluence_verdict(analysis)
    rows_html  = "".join(_signal_row(s) for s in signals)

    st.html(
        _section_header()
        + _confluence_card(confluence)
        + '<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;'
          'border-radius:12px;overflow:hidden;margin-top:10px">'
        + rows_html
        + '</div>'
    )

    with st.expander("How to read · Verdict guide & optional intelligence", expanded=False):
        st.html(_legend_html())


# ── Confluence verdict ─────────────────────────────────────────────────────────

def _confluence_verdict(a: dict) -> dict:
    """
    RSI > 70 alone is NOT a top. The real top signal requires confluence of:
      1. RSI overbought (≥ 70 daily)
      2. Bearish RSI divergence (momentum weakening at new highs)
      3. Breadth deteriorating (fewer stocks participating)
    Resistance context (MA stretch / failure swing) raises confidence further.
    """
    tfs = a.get("tf_stack", {})
    div = a.get("divergence", {})
    br  = a.get("breadth", {})
    fs  = a.get("failure_swing", {})
    mas = a.get("ma_stretch", {})

    d_rsi           = tfs.get("daily_rsi") or 0
    rsi_ob          = d_rsi >= 70
    divergence_on   = div.get("detected", False)
    breadth_weak    = br.get("detected", False) or br.get("breadth_declining", False)
    # Supporting context — adds confidence but not required for the core signal
    fs_active       = fs.get("detected", False) or fs.get("approaching", False)
    stretched       = (mas.get("pct_above_200") or 0) >= 10

    core_count = sum([rsi_ob, divergence_on, breadth_weak])

    conditions = [
        (rsi_ob,        f"RSI {d_rsi:.0f} ≥ 70" if rsi_ob else f"RSI {d_rsi:.0f} — not overbought"),
        (divergence_on, "Bearish divergence active" if divergence_on else "No RSI divergence"),
        (breadth_weak,  "Breadth deteriorating" if breadth_weak else "Breadth not confirming"),
    ]
    extras = []
    if fs_active:
        extras.append("Failure swing forming")
    if stretched:
        extras.append(f"+{mas.get('pct_above_200', 0):.0f}% above 200 DMA")

    if core_count == 3:
        label, color, verdict = "REAL TOP SIGNAL", "#EF4444", "All three core conditions aligned — high conviction shorting setup"
    elif core_count == 2 and rsi_ob:
        label, color, verdict = "HIGH RISK", "#F97316", "Two of three conditions met — wait for the third before acting"
    elif rsi_ob and core_count == 1:
        label, color, verdict = "ELEVATED CAUTION", "#FBBF24", "RSI overbought but divergence and breadth not confirming"
    elif rsi_ob:
        label, color, verdict = "OVERBOUGHT ONLY", "#94A3B8", "RSI > 70 is necessary but not sufficient — no top yet"
    else:
        label, color, verdict = "NOT A TOP", "#22C55E", "RSI below 70 — overbought condition not met, top unlikely"

    return {
        "label":      label,
        "color":      color,
        "verdict":    verdict,
        "conditions": conditions,
        "extras":     extras,
        "core_count": core_count,
        "rsi_ob":     rsi_ob,
        "d_rsi":      d_rsi,
    }


def _confluence_card(c: dict) -> str:
    # Condition pills
    pills = ""
    for met, text in c["conditions"]:
        pcol = "#4ADE80" if met else "#64748B"
        pbg  = "#052E16" if met else "#0F172A"
        icon = "✓" if met else "○"
        pills += (
            f'<span style="font-size:11px;font-weight:600;color:{pcol};background:{pbg};'
            f'border-radius:5px;padding:3px 9px;white-space:nowrap">{icon} {text}</span>'
        )
    for text in c["extras"]:
        pills += (
            f'<span style="font-size:11px;font-weight:600;color:#A78BFA;background:#1E1B4B;'
            f'border-radius:5px;padding:3px 9px;white-space:nowrap">+ {text}</span>'
        )

    # Score bar (3 segments for 3 core conditions)
    filled   = c["core_count"]
    unfilled = 3 - filled
    bar      = (
        f'<div style="display:flex;gap:3px;margin-top:8px">'
        + f'<div style="flex:{filled};height:4px;background:{c["color"]};border-radius:2px"></div>' * (1 if filled else 0)
        + f'<div style="flex:{unfilled};height:4px;background:#1E293B;border-radius:2px"></div>' * (1 if unfilled else 0)
        + '</div>'
    ) if filled or unfilled else ""

    note = (
        '<span style="font-size:11px;color:#475569;font-style:italic">'
        'RSI &gt; 70 alone is not a top — requires divergence + failing breadth + resistance</span>'
    )

    return (
        f'<div style="background:rgba(255,255,255,0.04);border:1px solid {c["color"]}44;'
        f'border-left:4px solid {c["color"]};border-radius:10px;padding:14px 16px">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">'
        f'<div>'
        f'<div style="font-size:20px;font-weight:900;color:{c["color"]};line-height:1;letter-spacing:-.3px">'
        f'{c["label"]}</div>'
        f'<div style="font-size:12px;color:#94A3B8;margin-top:4px">{c["verdict"]}</div>'
        f'</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap">{pills}</div>'
        f'</div>'
        f'{bar}'
        f'<div style="margin-top:8px">{note}</div>'
        f'</div>'
    )


# ── Signal builder ─────────────────────────────────────────────────────────────

def _build_signals(a: dict) -> list[dict]:
    signals: list[dict] = []

    # 1. RSI Divergence
    div = a.get("divergence", {})
    if div.get("detected"):
        signals.append({
            "name": "RSI Divergence",
            "value": f"H1 {div['rsi_at_high1']} → H2 {div['rsi_at_high2']}",
            "note": (
                f"Price new high ({div['date1']} → {div['date2']}) but RSI lower — "
                "momentum weakening before potential rollover"
            ),
            "status": "warn",
        })
    else:
        p1 = div.get("rsi_at_high1")
        p2 = div.get("rsi_at_high2")
        val = f"{p1} / {p2}" if p1 and p2 else "Not detected"
        signals.append({
            "name": "RSI Divergence",
            "value": val,
            "note": "No bearish price/RSI divergence in the last 90 days",
            "status": "ok",
        })

    # 2. RSI Timeframe Stack
    tfs = a.get("tf_stack", {})
    d_rsi = tfs.get("daily_rsi")
    w_rsi = tfs.get("weekly_rsi")
    tf_val = f"D {d_rsi}" + (f" / W {w_rsi}" if w_rsi is not None else "")
    if tfs.get("stacked"):
        signals.append({
            "name": "TF Stack",
            "value": tf_val,
            "note": "Daily RSI ≥ 75 AND weekly RSI ≥ 65 — overbought across both timeframes, higher reversal risk",
            "status": "warn",
        })
    elif tfs.get("daily_overbought") or tfs.get("weekly_overbought"):
        signals.append({
            "name": "TF Stack",
            "value": tf_val,
            "note": "One timeframe overbought — watch for the other to confirm before shorting",
            "status": "caution",
        })
    else:
        signals.append({
            "name": "TF Stack",
            "value": tf_val or "N/A",
            "note": "Daily and weekly RSI both below overbought thresholds",
            "status": "ok",
        })

    # 3. RSI Failure Swing
    fs = a.get("failure_swing", {})
    if fs.get("detected"):
        signals.append({
            "name": "Failure Swing",
            "value": f"H1={fs['h1']} H2={fs['h2']} L1={fs['l1']}",
            "note": "H2 < H1 and RSI broke below neckline (L1) — confirmed bearish failure swing",
            "status": "warn",
        })
    elif fs.get("approaching"):
        l1 = fs.get("l1", "—")
        cr = fs.get("current_rsi", "—")
        signals.append({
            "name": "Failure Swing",
            "value": f"RSI {cr} → L1 {l1}",
            "note": f"H2 < H1 formed — RSI approaching neckline at {l1}, break below would confirm",
            "status": "caution",
        })
    else:
        cr = fs.get("current_rsi", "—")
        h1 = fs.get("h1")
        note = (
            f"H1={h1} identified — waiting for pullback/H2 to form"
            if h1 else "No failure swing pattern forming"
        )
        signals.append({
            "name": "Failure Swing",
            "value": f"RSI {cr}",
            "note": note,
            "status": "ok",
        })

    # 4. MA Stretch (price vs 200 DMA)
    mas = a.get("ma_stretch", {})
    pct_200 = mas.get("pct_above_200")
    if pct_200 is not None:
        ma200 = mas.get("ma200", 0)
        level = mas.get("stretch_level", "Normal")
        sign = "+" if pct_200 >= 0 else ""
        if pct_200 >= 15:
            st_status = "warn"
        elif pct_200 >= 10:
            st_status = "caution"
        else:
            st_status = "ok"
        signals.append({
            "name": "MA Stretch",
            "value": f"{sign}{pct_200:.1f}% vs 200 DMA",
            "note": f"{level} — 200 DMA at ${ma200:,.0f}; ≥10% extension historically precedes corrections",
            "status": st_status,
        })
    else:
        signals.append({
            "name": "MA Stretch",
            "value": "N/A",
            "note": "Insufficient data for 200-day MA",
            "status": "ok",
        })

    # 5. Breadth Divergence
    br = a.get("breadth", {})
    if not br.get("available", False):
        signals.append({
            "name": "Breadth",
            "value": f"RSI {br.get('spx_rsi', '—')}",
            "note": "^SPXA50R breadth data unavailable (market closed or data feed issue)",
            "status": "na",
        })
    elif br.get("detected"):
        trend = br.get("breadth_trend", 0)
        bpct  = br.get("breadth_pct", 0)
        signals.append({
            "name": "Breadth",
            "value": f"{bpct:.0f}% above 50 MA",
            "note": (
                f"SPX RSI {br['spx_rsi']} but breadth trending down ({trend:+.0f}pt/10d) — "
                "fewer stocks participating, hidden weakness"
            ),
            "status": "warn",
        })
    elif br.get("breadth_declining"):
        trend = br.get("breadth_trend", 0)
        bpct  = br.get("breadth_pct", 0)
        signals.append({
            "name": "Breadth",
            "value": f"{bpct:.0f}% above 50 MA",
            "note": f"Breadth declining ({trend:+.0f}pt/10d) — watch RSI for confluence",
            "status": "caution",
        })
    else:
        bpct = br.get("breadth_pct")
        val  = f"{bpct:.0f}% above 50 MA" if bpct is not None else "—"
        signals.append({
            "name": "Breadth",
            "value": val,
            "note": "Breadth stable — participation is broad, no hidden weakness",
            "status": "ok",
        })

    return signals


# ── HTML helpers ───────────────────────────────────────────────────────────────

_STATUS: dict[str, tuple[str, str, str]] = {
    "warn":    ("#FCA5A5", "#450A0A", "▲ WARN"),
    "caution": ("#FCD34D", "#422006", "~ WATCH"),
    "ok":      ("#4ADE80", "#052E16", "✓ OK"),
    "na":      ("#94A3B8", "#1E293B", "— N/A"),
}

_ROW_BG = ("rgba(255,255,255,0.02)", "transparent")


def _signal_row(s: dict, idx: int = 0) -> str:
    txt_col, bg_col, badge = _STATUS.get(s["status"], _STATUS["na"])
    border = f"border-left:3px solid {txt_col};"
    row_bg = _ROW_BG[hash(s["name"]) % 2]
    return (
        f'<div style="display:grid;grid-template-columns:108px 200px 1fr;gap:0 14px;'
        f'align-items:center;padding:10px 14px;border-bottom:1px solid #0F172A;'
        f'{border}background:{row_bg}">'
        f'<div style="font-size:11px;color:#94A3B8;font-weight:600">{s["name"]}</div>'
        f'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
        f'<span style="font-size:10px;font-weight:700;color:{txt_col};background:{bg_col};'
        f'border-radius:4px;padding:2px 6px;white-space:nowrap">{badge}</span>'
        f'<span style="font-size:12px;font-weight:700;color:#E2E8F0;font-family:monospace;'
        f'white-space:nowrap">{s["value"]}</span>'
        f'</div>'
        f'<div style="font-size:11px;color:#64748B;line-height:1.5">{s["note"]}</div>'
        f'</div>'
    )


def _legend_html() -> str:
    verdicts = [
        ("#22C55E", "NOT A TOP",
         "RSI below 70",
         "Base condition not met. Overbought RSI is a prerequisite — without it the other signals carry little weight. "
         "Normal pullbacks and dips are buying opportunities, not topping signals."),
        ("#94A3B8", "OVERBOUGHT ONLY",
         "RSI ≥ 70 · divergence absent · breadth not confirming",
         "Market is extended but participation is still broad and momentum isn't rolling over. "
         "Avoid adding new longs at current levels, but shorting is premature — "
         "overbought markets can stay overbought for weeks."),
        ("#FBBF24", "ELEVATED CAUTION",
         "RSI ≥ 70 + one confirming signal",
         "One of the two confirming conditions (divergence or breadth) is warning. "
         "Reduce position size, tighten stops on longs, and wait for the second condition "
         "before initiating any short position."),
        ("#F97316", "HIGH RISK",
         "RSI ≥ 70 + divergence + breadth (or either one is present)",
         "Two of three core conditions aligned. This is a serious warning — "
         "consider partial hedges (put spreads, reducing exposure). "
         "Wait for the final condition before a full short thesis."),
        ("#EF4444", "REAL TOP SIGNAL",
         "RSI ≥ 70 + bearish divergence + breadth deteriorating — all three",
         "All core conditions aligned. High-conviction topping setup. "
         "This is when put buying or bear spreads make sense with real size. "
         "Optional intelligence below can sharpen entry timing."),
    ]

    optional = [
        ("Failure Swing",
         "Wilder's RSI reversal pattern",
         "RSI peaks above 70 (H1) → dips below 70 (L1) → rallies but can't exceed H1 (H2 &lt; H1) → breaks below L1. "
         "Confirmed break below L1 is the entry trigger. "
         "Use this to time the short entry precisely once the REAL TOP SIGNAL is active — "
         "it tells you <em>when</em> to pull the trigger, not <em>whether</em> to."),
        ("MA Stretch (+X% above 200 DMA)",
         "Mean-reversion gravity",
         "Price historically reverts toward the 200 DMA. "
         "At 10%+ above: elevated reversion risk. "
         "At 15%+: very high — prior instances include major pre-correction peaks. "
         "At 20%+: extreme, historically seen near significant market tops (2000, 2021). "
         "This signal adds confidence to the top thesis and informs how far a correction could run."),
        ("TF Stack (Daily ≥ 75 + Weekly ≥ 65)",
         "Multi-timeframe overbought",
         "When both the daily and weekly RSI are stretched, the market is overextended across timeframes — "
         "not just a short-term condition. Tops formed with both timeframes overbought tend to produce "
         "deeper and more sustained corrections than single-timeframe extremes."),
    ]

    # ── Verdict rows ──────────────────────────────────────────────────────────
    def _vrow(color, label, trigger, explanation):
        return (
            f'<div style="display:grid;grid-template-columns:130px 260px 1fr;gap:0 14px;'
            f'align-items:start;padding:10px 12px;border-bottom:1px solid #0F172A;">'
            f'<div style="font-size:12px;font-weight:800;color:{color}">{label}</div>'
            f'<div style="font-size:11px;color:#64748B;line-height:1.5">{trigger}</div>'
            f'<div style="font-size:11px;color:#94A3B8;line-height:1.6">{explanation}</div>'
            f'</div>'
        )

    verdict_header = (
        '<div style="display:grid;grid-template-columns:130px 260px 1fr;gap:0 14px;'
        'padding:6px 12px 8px;border-bottom:1px solid #1E293B">'
        '<div style="font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:.07em">Verdict</div>'
        '<div style="font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:.07em">Conditions</div>'
        '<div style="font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:.07em">What it means</div>'
        '</div>'
    )
    verdict_rows = "".join(_vrow(*v) for v in verdicts)

    # ── Optional intelligence rows ─────────────────────────────────────────────
    def _orow(name, subtitle, explanation):
        return (
            f'<div style="display:grid;grid-template-columns:180px 1fr;gap:0 14px;'
            f'align-items:start;padding:10px 12px;border-bottom:1px solid #0F172A;">'
            f'<div>'
            f'<div style="font-size:12px;font-weight:700;color:#A78BFA">{name}</div>'
            f'<div style="font-size:10px;color:#475569;margin-top:2px">{subtitle}</div>'
            f'</div>'
            f'<div style="font-size:11px;color:#94A3B8;line-height:1.6">{explanation}</div>'
            f'</div>'
        )

    opt_header = (
        '<div style="font-size:10px;color:#A78BFA;font-weight:700;text-transform:uppercase;'
        'letter-spacing:.07em;padding:10px 12px 6px;border-bottom:1px solid #1E293B;'
        'border-top:2px solid #1E1B4B;margin-top:4px">'
        '+ Optional Intelligence — sharpens timing, does not replace core conditions'
        '</div>'
    )
    opt_rows = "".join(_orow(*o) for o in optional)

    rule = (
        '<div style="padding:10px 12px;border-top:1px solid #1E293B;">'
        '<div style="font-size:11px;color:#475569;font-style:italic;line-height:1.8">'
        '<strong style="color:#94A3B8">Core rule:</strong> '
        'Never short on RSI alone. Never short on divergence alone. '
        'The three core signals must converge — RSI sets the stage, '
        'divergence shows momentum is fading, breadth confirms the distribution is real. '
        'Optional signals then help time the entry.'
        '</div>'
        '</div>'
    )

    return (
        '<div style="background:#0B1120;border:1px solid #1E293B;border-radius:10px;overflow:hidden">'
        + verdict_header + verdict_rows
        + opt_header + opt_rows
        + rule
        + '</div>'
    )


def _section_header() -> str:
    return (
        '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">'
        '<span style="font-size:13px;font-weight:700;color:#94A3B8;'
        'letter-spacing:.06em;text-transform:uppercase">SPX Top Signals</span>'
        '<span style="font-size:10px;color:#475569">RSI structure · daily/weekly</span>'
        '</div>'
    )
