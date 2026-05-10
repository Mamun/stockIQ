"""Fundamentals & Analyst Consensus panel for the Stock Analyzer page."""

import streamlit as st

from stockiq.frontend.theme import BG, DN, MUT, NEU, SEP, UP, VAL


def render_fundamentals_panel(fund: dict, price: float) -> None:
    if not fund:
        return

    left, right = st.columns([1, 1], gap="large")

    with left:
        _render_fundamentals_table(fund)

    with right:
        _render_analyst_block(fund, price)


# ── Fundamentals compact table ─────────────────────────────────────────────────

def _render_fundamentals_table(fund: dict) -> None:
    mcap_val, mcap_lbl = _fmt_mcap(fund.get("market_cap"))
    fpe  = fund.get("forward_pe")
    med  = fund.get("sector_median_pe")
    tpe  = fund.get("trailing_pe")
    eg   = fund.get("eps_growth")
    peg  = fund.get("peg")

    fpe_sub, fpe_clr = "", None
    if fpe and med:
        diff = fpe - med
        fpe_sub = f"sector avg {med:.1f}"
        fpe_clr = UP if fpe < med else DN if fpe > med * 1.15 else None

    eg_val, eg_clr = "—", MUT
    if eg is not None:
        eg_pct = eg * 100
        eg_val = f"{eg_pct:+.1f}%"
        eg_clr = UP if eg_pct >= 10 else DN if eg_pct < 0 else NEU

    peg_sub, peg_clr = "", MUT
    if peg and peg > 0:
        peg_sub = "Undervalued" if peg < 1 else "Fair" if peg < 2 else "Expensive"
        peg_clr = UP if peg < 1 else NEU if peg < 2 else DN

    rows = [
        ("Market Cap",    mcap_val,                            mcap_lbl,                      None),
        ("Forward P/E",   f"{fpe:.1f}" if fpe else "—",        fpe_sub,                       fpe_clr),
        ("Trailing P/E",  f"{tpe:.1f}" if tpe and tpe > 0 else "—", "trailing",              None),
        ("EPS Growth",    eg_val,                              "YoY est.",                    eg_clr),
        ("PEG Ratio",     f"{peg:.2f}" if peg and peg > 0 else "—", peg_sub,                 peg_clr),
    ]

    st.markdown(
        f'<div style="font-size:0.72rem;color:{MUT};text-transform:uppercase;'
        f'letter-spacing:.08em;margin-bottom:6px">Fundamentals</div>',
        unsafe_allow_html=True,
    )

    html_rows = ""
    for i, (label, value, sub, clr) in enumerate(rows):
        bg = f"background:{BG};" if i % 2 == 0 else ""
        val_color = clr or VAL
        sub_html = (
            f'<span style="color:{clr or MUT};font-size:0.7rem;margin-left:6px">{sub}</span>'
            if sub else ""
        )
        html_rows += (
            f'<div style="{bg}display:flex;justify-content:space-between;align-items:center;'
            f'padding:5px 8px;border-radius:4px">'
            f'<span style="color:{MUT};font-size:0.82rem">{label}</span>'
            f'<span style="font-size:0.85rem;font-weight:600;color:{val_color}">'
            f'{value}{sub_html}</span>'
            f'</div>'
        )

    st.markdown(
        f'<div style="border:1px solid {SEP};border-radius:8px;overflow:hidden">'
        f'{html_rows}</div>',
        unsafe_allow_html=True,
    )


# ── Analyst Consensus visual block ─────────────────────────────────────────────

def _render_analyst_block(fund: dict, price: float) -> None:
    cons_lbl, cons_clr = _consensus_label(fund.get("rating"))
    rating      = fund.get("rating")
    n_analysts  = fund.get("num_analysts")
    target      = fund.get("target_mean")
    target_lo   = fund.get("target_low")
    target_hi   = fund.get("target_high")

    upside_html = ""
    if target and price:
        upside = (target - price) / price * 100
        up_clr = UP if upside >= 10 else DN if upside < 0 else NEU
        arrow  = "↑" if upside >= 0 else "↓"
        upside_html = (
            f'<span style="color:{up_clr};font-size:0.82rem;font-weight:600;margin-left:8px">'
            f'{arrow} {upside:+.1f}%</span>'
        )

    analysts_html = (
        f'<span style="color:{MUT};font-size:0.8rem;margin-left:10px">'
        f'{n_analysts} analysts</span>' if n_analysts else ""
    )

    range_html = ""
    if target_lo and target_hi:
        range_html = (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:5px 8px;border-radius:4px">'
            f'<span style="color:{MUT};font-size:0.82rem">Target range</span>'
            f'<span style="font-size:0.85rem;font-weight:600;color:{VAL}">'
            f'${target_lo:,.0f} – ${target_hi:,.0f}</span>'
            f'</div>'
        )

    target_html = ""
    if target:
        target_html = (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:5px 8px;border-radius:4px;background:{BG}">'
            f'<span style="color:{MUT};font-size:0.82rem">Mean target</span>'
            f'<span style="font-size:0.85rem;font-weight:600;color:{VAL}">'
            f'${target:,.2f}{upside_html}</span>'
            f'</div>'
        )

    st.markdown(
        f'<div style="font-size:0.72rem;color:{MUT};text-transform:uppercase;'
        f'letter-spacing:.08em;margin-bottom:6px">Analyst Consensus</div>',
        unsafe_allow_html=True,
    )

    rating_sub = f"score {rating:.1f} / 5.0" if rating else ""

    st.markdown(
        f'<div style="border:1px solid {SEP};border-radius:8px;overflow:hidden">'
        # Badge row
        f'<div style="background:{cons_clr}1a;border-bottom:1px solid {SEP};'
        f'padding:10px 12px;display:flex;align-items:center;gap:10px">'
        f'<span style="background:{cons_clr};color:#fff;font-size:0.82rem;font-weight:700;'
        f'padding:3px 14px;border-radius:20px;letter-spacing:.04em">{cons_lbl}</span>'
        f'{analysts_html}'
        f'<span style="color:{MUT};font-size:0.75rem;margin-left:auto">{rating_sub}</span>'
        f'</div>'
        # Price target rows
        f'{target_html}'
        f'{range_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

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
