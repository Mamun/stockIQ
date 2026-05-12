"""
Options Intelligence panel — orchestration only.

Delegates all rendering to focused sub-modules:
  options_cards    — P/C, Max Pain, Expected Move, GEX summary cards
  options_signals  — Dealer Levels, Gamma Squeeze, Flow Sweeps, OI heatmap data
  options_expander — Educational expander and Volatility Regime bar
  spy_trade_idea   — Strategy suggestion card
"""

from __future__ import annotations

from datetime import date as _date, datetime as _datetime

import pandas as pd
import pytz
import streamlit as st

from stockiq.backend.models.options import compute_strategy_suggestion
from stockiq.backend.services.spy_service import get_spy_aggregated_gex, get_spy_gaps_df, get_spy_options_analysis, get_vol_regime
from stockiq.frontend.views.components.options_charts import oi_gex_combined_chart, oi_heatmap_chart
from stockiq.frontend.views.panels.options_cards import (
    max_pain_style,
    render_expected_move_card,
    render_gex_summary_card,
    render_max_pain_card,
    render_pc_card,
)
from stockiq.frontend.views.panels.options_expander import render_options_expander, render_vol_regime_bar
from stockiq.frontend.views.panels.options_signals import (
    compute_gamma_squeeze,
    compute_signals,
    fetch_multi_exp_oi,
    render_gamma_squeeze_panel,
    render_signals_panel,
    render_sweep_panel,
)
from stockiq.frontend.views.panels.spy_trade_idea import render_spy_trade_idea

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
    render_options_expander(
        expander_seed, current_price, vol,
        pc=expander_seed.get("pc"),
        suggestion=expander_suggestion,
    )

    expirations = seed["expirations"]
    default_idx = expirations.index(today_iso) if today_iso in expirations else 0

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
    max_pain      = data["max_pain"]
    oi_df         = data["oi_df"]
    gex_df        = data.get("gex_df", pd.DataFrame())
    em            = data.get("expected_move")
    dist_pct      = (current_price - max_pain) / max_pain * 100 if max_pain else 0
    mp_color, mp_signal = max_pain_style(dist_pct)
    dist_arrow    = "▲" if dist_pct >= 0 else "▼"

    suggestion = compute_strategy_suggestion(current_price, em, pc, gex_df, oi_df, max_pain, vol, gaps_df=gaps_df)
    with strat_col:
        render_spy_trade_idea(suggestion, selected_label, selected_iso)

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    render_vol_regime_bar(vol)
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#64748B;letter-spacing:.08em;'
        f'text-transform:uppercase;margin-bottom:10px">'
        f'Options Intelligence — Max Pain · Open Interest · Put/Call'
        f'<span style="font-weight:400;color:#475569;letter-spacing:0;'
        f'text-transform:none"> &nbsp;·&nbsp; as of {fetched_at}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _agg        = get_spy_aggregated_gex(seed["expirations"], current_price)
    agg_gex_df      = _agg.get("combined", pd.DataFrame())
    agg_call_gex_df = _agg.get("calls",    pd.DataFrame())
    agg_put_gex_df  = _agg.get("puts",     pd.DataFrame())
    agg_oi_df       = _agg.get("oi",       pd.DataFrame())

    cards_col, chart_col = st.columns([2, 5])
    with cards_col:
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            render_pc_card(pc, pc_scope_note)
        with r1c2:
            render_max_pain_card(max_pain, selected_label, current_price, dist_pct, dist_arrow, mp_color, mp_signal)
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            render_expected_move_card(em, selected_label)
        with r2c2:
            render_gex_summary_card(gex_df, data.get("gex_components"), current_price)
    per_exp = False  # default — aggregated GEX (full dealer book)
    with chart_col:
        if not oi_df.empty or not gex_df.empty:
            per_exp = st.checkbox(
                f"GEX: {selected_label} only",
                value=False,
                key="gex_per_exp",
                help="Default shows net GEX across all near-term expirations (dealer full book). Check to see this expiration only.",
            )
            chart_oi_df    = oi_df    if per_exp else agg_oi_df
            chart_gex_df   = gex_df   if per_exp else agg_gex_df
            chart_call_gex = data.get("call_gex_df") if per_exp else agg_call_gex_df
            chart_put_gex  = data.get("put_gex_df")  if per_exp else agg_put_gex_df
            st.plotly_chart(
                oi_gex_combined_chart(
                    chart_oi_df, chart_gex_df, current_price, max_pain,
                    n_strikes=30 if per_exp else 60,
                    call_gex_df=chart_call_gex,
                    put_gex_df=chart_put_gex,
                ),
                use_container_width=True,
            )
        else:
            st.caption("No options data for this expiration.")

    # Signals use the same GEX source as the chart so levels are consistent.
    signals_gex = gex_df if per_exp else agg_gex_df
    sig_col, squeeze_col = st.columns([1, 1], gap="large")
    with sig_col:
        render_signals_panel(compute_signals(signals_gex, oi_df, current_price, max_pain, selected_label))
    with squeeze_col:
        render_gamma_squeeze_panel(compute_gamma_squeeze(signals_gex, oi_df, pc, current_price))

    sweep_df = data.get("sweep_signals", pd.DataFrame())
    render_sweep_panel(sweep_df, selected_label, fetched_at)

    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748B;'
        'letter-spacing:.08em;text-transform:uppercase;margin:20px 0 10px">'
        'Heatmap — Open Interest by Strike × Expiration</div>',
        unsafe_allow_html=True,
    )
    with st.spinner("Loading heatmap…"):
        call_pivot, put_pivot = fetch_multi_exp_oi(
            seed["expirations"], seed["exp_labels"], current_price
        )
    if not call_pivot.empty:
        st.plotly_chart(oi_heatmap_chart(call_pivot, put_pivot, current_price), use_container_width=True)
    else:
        st.caption("Heatmap data unavailable.")
