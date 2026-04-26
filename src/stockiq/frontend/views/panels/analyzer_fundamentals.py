"""Fundamentals & Analyst Consensus panel for the Stock Analyzer page."""

import streamlit as st

from stockiq.frontend.theme import BG, DN, MUT, NEU, SEP, UP, VAL


def render_fundamentals_panel(fund: dict, price: float) -> None:
    if not fund:
        return

    st.markdown(
        '<div style="font-size:0.78rem;color:#64748B;text-transform:uppercase;'
        'letter-spacing:.08em;margin-bottom:8px">Fundamentals</div>',
        unsafe_allow_html=True,
    )

    v1, v2, v3, v4, v5 = st.columns(5)

    mcap_val, mcap_lbl = _fmt_mcap(fund.get("market_cap"))
    v1.markdown(_stat_card("Market Cap", mcap_val, mcap_lbl), unsafe_allow_html=True)

    fpe = fund.get("forward_pe")
    med = fund.get("sector_median_pe")
    if fpe:
        sub    = f"Sector avg {med}" if med else ""
        pe_clr = UP if (med and fpe < med) else DN if (med and fpe > med * 1.15) else None
        v2.markdown(_stat_card("Forward P/E", f"{fpe:.1f}", sub, pe_clr), unsafe_allow_html=True)
    else:
        v2.markdown(_stat_card("Forward P/E", "—"), unsafe_allow_html=True)

    tpe = fund.get("trailing_pe")
    v3.markdown(
        _stat_card("Trailing P/E", f"{tpe:.1f}" if tpe and tpe > 0 else "—"),
        unsafe_allow_html=True,
    )

    eg = fund.get("eps_growth")
    if eg is not None:
        eg_pct = eg * 100
        eg_clr = UP if eg_pct >= 10 else DN if eg_pct < 0 else NEU
        v4.markdown(_stat_card("EPS Growth", f"{eg_pct:+.1f}%", "YoY est.", eg_clr), unsafe_allow_html=True)
    else:
        v4.markdown(_stat_card("EPS Growth", "—", "YoY est."), unsafe_allow_html=True)

    peg = fund.get("peg")
    if peg and peg > 0:
        peg_clr = UP if peg < 1 else NEU if peg < 2 else DN
        peg_sub = "Undervalued" if peg < 1 else "Fair" if peg < 2 else "Expensive"
        v5.markdown(_stat_card("PEG Ratio", f"{peg:.2f}", peg_sub, peg_clr), unsafe_allow_html=True)
    else:
        v5.markdown(_stat_card("PEG Ratio", "—"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

    st.markdown(
        '<div style="font-size:0.78rem;color:#64748B;text-transform:uppercase;'
        'letter-spacing:.08em;margin-bottom:8px">Analyst Consensus</div>',
        unsafe_allow_html=True,
    )

    a1, a2, a3, a4, a5 = st.columns(5)

    cons_lbl, cons_clr = _consensus_label(fund.get("rating"))
    rating     = fund.get("rating")
    rating_sub = f"{rating:.1f} / 5.0" if rating else ""
    a1.markdown(_stat_card("Consensus", cons_lbl, rating_sub, cons_clr), unsafe_allow_html=True)

    n = fund.get("num_analysts")
    a2.markdown(_stat_card("# Analysts", str(n) if n else "—", "covering"), unsafe_allow_html=True)

    target = fund.get("target_mean")
    if target and price:
        a3.markdown(_stat_card("Price Target", f"${target:,.2f}", "mean"), unsafe_allow_html=True)
        upside = (target - price) / price * 100
        up_clr = UP if upside >= 10 else DN if upside < 0 else NEU
        a4.markdown(_stat_card("Upside", f"{upside:+.1f}%", "to mean target", up_clr), unsafe_allow_html=True)
    else:
        a3.markdown(_stat_card("Price Target", "—", "mean"), unsafe_allow_html=True)
        a4.markdown(_stat_card("Upside", "—"), unsafe_allow_html=True)

    lo = fund.get("target_low")
    hi = fund.get("target_high")
    if lo and hi:
        a5.markdown(_stat_card("Target Range", f"${lo:,.0f} – ${hi:,.0f}", "low / high"), unsafe_allow_html=True)
    else:
        a5.markdown(_stat_card("Target Range", "—"), unsafe_allow_html=True)


# ── Pure HTML helpers ──────────────────────────────────────────────────────────

def _stat_card(label: str, value: str, sub: str = "", sub_color: str | None = None) -> str:
    sub_html = (
        f'<div style="font-size:11px;color:{sub_color or MUT};margin-top:3px">{sub}</div>'
        if sub else ""
    )
    return (
        f'<div style="background:{BG};border:1px solid {SEP};border-radius:8px;padding:14px 16px">'
        f'<div style="font-size:11px;color:{MUT};text-transform:uppercase;'
        f'letter-spacing:.05em;margin-bottom:4px">{label}</div>'
        f'<div style="font-size:19px;font-weight:700;color:{VAL}">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def _fmt_mcap(v: float | None) -> tuple[str, str]:
    if v is None:
        return "—", ""
    if v >= 1e12:
        return f"${v/1e12:.2f}T", "Mega Cap"
    if v >= 2e11:
        return f"${v/1e9:.0f}B", "Large Cap"
    if v >= 1e10:
        return f"${v/1e9:.1f}B", "Mid Cap"
    return f"${v/1e9:.1f}B", "Small Cap"


def _consensus_label(rating: float | None) -> tuple[str, str]:
    if rating is None:
        return "—", MUT
    if rating <= 1.5:
        return "Strong Buy", UP
    if rating <= 2.0:
        return "Buy", UP
    if rating <= 2.5:
        return "Mod. Buy", "#86EFAC"
    if rating <= 3.5:
        return "Hold", NEU
    if rating <= 4.0:
        return "Mod. Sell", DN
    return "Sell", DN
