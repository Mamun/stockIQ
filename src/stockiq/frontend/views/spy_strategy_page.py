"""Standalone SPY Strategy Suggestion page — shareable URL."""

from datetime import date as _date, datetime as _datetime

import pandas as pd
import pytz
import streamlit as st

from stockiq.backend.models.options import compute_strategy_suggestion
from stockiq.backend.services.spy_service import (
    get_spy_gaps_df,
    get_spy_options_analysis,
    get_spy_quote,
    get_vol_regime,
)
from stockiq.frontend.views.panels.options_intelligence import (
    _render_strategy_card,
    _render_vol_regime_bar,
)

_ET = pytz.timezone("America/New_York")


def render_spy_strategy_page() -> None:
    st.title("🎯 SPY Trade Idea")
    st.caption(
        "Live options-based strategy for SPY · Powered by OI, GEX, IV Rank, and gap analysis"
    )

    with st.spinner("Loading SPY options data…"):
        quote   = get_spy_quote()
        price   = float(quote.get("price", 0))
        seed    = get_spy_options_analysis(expiration="", current_price=price)
        vol     = get_vol_regime()
        gaps_df = get_spy_gaps_df()

    if not seed or not price:
        st.error("Could not load SPY options data. Try again shortly.")
        return

    today_iso    = _date.today().isoformat()
    exp_override = st.query_params.get("exp", "")

    if exp_override and exp_override in seed["expirations"]:
        data = get_spy_options_analysis(expiration=exp_override, current_price=price) or seed
    elif today_iso in seed["expirations"] and seed.get("expiration") != today_iso:
        data = get_spy_options_analysis(expiration=today_iso, current_price=price) or seed
    else:
        data = seed

    exp_label = (
        dict(zip(seed["expirations"], seed["exp_labels"])).get(data["expiration"], data["expiration"])
    )

    suggestion = compute_strategy_suggestion(
        price,
        data.get("expected_move"),
        data.get("pc"),
        data.get("gex_df", pd.DataFrame()),
        data["oi_df"],
        data["max_pain"],
        vol,
        gaps_df=gaps_df,
    )

    if not suggestion:
        st.warning("Could not compute strategy suggestion — options data may be incomplete.")
        return

    st.divider()
    _render_strategy_card(suggestion, exp_label, data["expiration"])

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    _render_vol_regime_bar(vol)

    fetched_at = _datetime.now(tz=_ET).strftime("%-I:%M %p ET · %b %-d")
    st.caption(
        f"Updated: {fetched_at} · Expiration: {exp_label} · Price anchor: ${price:.2f}"
    )
    st.caption(
        "Not financial advice. Visit [SPY Dashboard → Options tab](/spy) for the full analysis."
    )


render_spy_strategy_page()
