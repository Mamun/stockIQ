"""
Options Intelligence metric cards: P/C ratio, Max Pain, Expected Move, GEX summary.

Public API:
  max_pain_style(dist_pct) -> (color, signal_text)
  render_pc_card(pc, pc_scope_note)
  render_max_pain_card(max_pain, label, current_price, dist_pct, arrow, mp_color, mp_signal)
  render_expected_move_card(em, exp_label)
  render_gex_summary_card(gex_df)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def max_pain_style(dist_pct: float) -> tuple[str, str]:
    if abs(dist_pct) <= 0.5:
        return "#22C55E", "Pinned near max pain — low movement expected"
    if abs(dist_pct) <= 2.0:
        return "#86EFAC", "Close to max pain — mild gravitational pull"
    if abs(dist_pct) <= 4.0:
        return "#F59E0B", "Drifting from max pain — watch for reversion"
    return "#EF4444", "Far from max pain — strong directional move"


def render_pc_card(pc: dict | None, pc_scope_note: str) -> None:
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


def render_max_pain_card(
    max_pain: float,
    label: str,
    current_price: float,
    dist_pct: float,
    arrow: str,
    mp_color: str,
    mp_signal: str,
) -> None:
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


def render_expected_move_card(em: dict | None, exp_label: str) -> None:
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


def render_gex_summary_card(
    gex_df: pd.DataFrame,
    gex_components: dict | None = None,
    current_price: float = 0.0,
) -> None:
    if gex_df.empty:
        st.markdown(
            '<div style="padding:16px;font-size:11px;color:#64748B">GEX unavailable.</div>',
            unsafe_allow_html=True,
        )
        return

    def _fmt(v: float) -> str:
        if abs(v) >= 1e9:
            return f"{v / 1e9:+.2f}B"
        return f"{v / 1e6:+.1f}M"

    def _fmt_abs(v: float) -> str:
        if abs(v) >= 1e9:
            return f"{v / 1e9:.2f}B"
        return f"{v / 1e6:.1f}M"

    def _pct(strike: float | None) -> str:
        if not strike or not current_price:
            return ""
        p = (strike - current_price) / current_price * 100
        return f"{p:+.2f}%"

    net_gex = gex_components["net_gex"] if gex_components else float(gex_df["gex"].sum())

    if net_gex >= 0:
        gex_color = "#22C55E"
        gex_gamma = "Long Gamma"
        gex_note  = "Dealers buy dips &amp; sell rips — price tends to stay range-bound"
    else:
        gex_color = "#EF4444"
        gex_gamma = "Short Gamma"
        gex_note  = "Dealers amplify moves — expect larger intraday swings"

    net_label = _fmt(net_gex)

    if gex_components:
        call_gex_lbl   = _fmt(gex_components["call_gex"])
        put_gex_lbl    = _fmt(gex_components["put_gex"])
        total_gex_lbl  = _fmt_abs(gex_components["total_gex"])
        call_oi        = gex_components["call_oi"]
        put_oi         = gex_components["put_oi"]
        total_oi       = call_oi + put_oi
        call_wall      = gex_components.get("call_wall")
        put_wall       = gex_components.get("put_wall")
        zero_gamma     = gex_components.get("zero_gamma")
        cw_str  = f"${call_wall:,.0f}"  if call_wall  else "—"
        pw_str  = f"${put_wall:,.0f}"   if put_wall   else "—"
        zg_str  = f"${zero_gamma:,.2f}" if zero_gamma else "—"

        breakdown_html = f"""
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:10px">
    <div>
      <div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Call GEX</div>
      <div style="font-size:12px;font-weight:700;color:#22C55E">{call_gex_lbl}</div>
      <div style="font-size:9px;color:#475569">{call_oi:,} OI</div>
    </div>
    <div>
      <div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Put GEX</div>
      <div style="font-size:12px;font-weight:700;color:#EF4444">{put_gex_lbl}</div>
      <div style="font-size:9px;color:#475569">{put_oi:,} OI</div>
    </div>
    <div>
      <div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Total GEX</div>
      <div style="font-size:12px;font-weight:700;color:#94A3B8">{total_gex_lbl}</div>
      <div style="font-size:9px;color:#475569">{total_oi:,} OI</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:8px;
              padding-top:8px;border-top:1px solid #1E293B">
    <div>
      <div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Call Wall</div>
      <div style="font-size:12px;font-weight:700;color:#22C55E">{cw_str}</div>
      <div style="font-size:9px;color:#475569">{_pct(call_wall)}</div>
    </div>
    <div>
      <div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Put Wall</div>
      <div style="font-size:12px;font-weight:700;color:#EF4444">{pw_str}</div>
      <div style="font-size:9px;color:#475569">{_pct(put_wall)}</div>
    </div>
    <div>
      <div style="font-size:9px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">Zero Gamma</div>
      <div style="font-size:12px;font-weight:700;color:#F59E0B">{zg_str}</div>
      <div style="font-size:9px;color:#475569">{_pct(zero_gamma)}</div>
    </div>
  </div>"""
    else:
        peak_support = float(gex_df.loc[gex_df["gex"].idxmax(), "strike"])
        peak_resist  = float(gex_df.loc[gex_df["gex"].idxmin(), "strike"])
        breakdown_html = f"""
  <div style="font-size:10px;color:#94A3B8;line-height:1.8;margin-top:8px">
    Peak dealer support: <b style="color:#22C55E">${peak_support:,.0f}</b><br>
    Peak dealer flip: <b style="color:#EF4444">${peak_resist:,.0f}</b>
  </div>"""

    st.markdown(
        f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid #1E293B;border-radius:10px;
            padding:16px;box-sizing:border-box">
  <div style="font-size:10px;color:#94A3B8;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:4px">Gamma Exposure (GEX)</div>
  <div style="font-size:28px;font-weight:900;color:{gex_color};line-height:1;margin:2px 0">{net_label}</div>
  <div style="font-size:11px;font-weight:700;color:{gex_color}">{gex_gamma}
    <span style="color:#64748B;font-size:9px;font-weight:400"> · Net GEX</span>
  </div>
  {breakdown_html}
  <div style="font-size:9px;color:#475569;margin-top:8px">{gex_note}</div>
</div>""",
        unsafe_allow_html=True,
    )
