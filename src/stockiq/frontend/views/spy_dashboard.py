"""SPY Dashboard page — thin orchestrator that composes panels."""

import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st

from stockiq.backend.services.market_service import get_market_overview
from stockiq.backend.services.spy_service import (
    get_put_call_ratio,
    get_rsi_top_analysis,
    get_spy_chart_df,
    get_spy_gap_table_data,
    get_spy_quote,
)
from stockiq.frontend.views.components.gap_table import render_gap_table
from stockiq.frontend.views.components.summary_card import render_spy_summary_card
from stockiq.frontend.views.panels.ai_forecast import render_ai_forecast
from stockiq.frontend.views.panels.dte_conditions import render_dte_conditions
from stockiq.frontend.views.panels.options_intelligence import render_options_intelligence
from stockiq.frontend.views.panels.rsi_top_signals import render_rsi_top_signals
from stockiq.frontend.views.panels.spy_chart import render_spy_chart_section
from stockiq.frontend.views.panels.spy_header import render_spy_header


_TAB_LABELS = {"market": "Market Overview", "options": "Options"}
_TAB_KEY    = "spy_active_tab"


def render_spy_dashboard_tab() -> None:
    # Gap data is historical (changes once at market open) — fetch once per page load,
    # not on every fragment refresh.
    try:
        gap_data = get_spy_gap_table_data()
    except Exception:
        gap_data = {"gaps_df": pd.DataFrame(), "quote": {}, "daily_df": pd.DataFrame()}

    # Seed session state from URL on the very first load; subsequent reruns use
    # session state so the widget never fights itself with a re-evaluated default.
    if _TAB_KEY not in st.session_state:
        url_tab = st.query_params.get("tab", "market")
        st.session_state[_TAB_KEY] = url_tab if url_tab in _TAB_LABELS else "market"

    def _sync_url() -> None:
        st.query_params["tab"] = st.session_state[_TAB_KEY]

    st.segmented_control(
        "Tab",
        options=list(_TAB_LABELS.keys()),
        format_func=_TAB_LABELS.get,
        key=_TAB_KEY,
        label_visibility="collapsed",
        on_change=_sync_url,
    )
    active_tab = st.session_state[_TAB_KEY]

    @st.fragment(run_every="90s")
    def _live_section() -> None:
        # Fire all independent fetches in parallel — they share no dependencies.
        with ThreadPoolExecutor(max_workers=5) as pool:
            f_quote    = pool.submit(get_spy_quote)
            f_overview = pool.submit(get_market_overview)
            f_rsi      = pool.submit(_fetch_daily_rsi)
            f_pc       = pool.submit(_fetch_pc_ratio)
            f_rsi_top  = pool.submit(_fetch_rsi_top_analysis)

            quote = f_quote.result(timeout=15)
            if not quote:
                st.error("Could not load SPY data. Please try again in a moment.")
                return

            # quote is needed for prev_close; fetch intraday while others finish
            intraday = _fetch_intraday_signals(quote)

            overview = f_overview.result(timeout=10)
            rsi      = f_rsi.result(timeout=10)
            pc       = f_pc.result(timeout=10)
            rsi_top  = f_rsi_top.result(timeout=30)

        render_spy_header(quote, overview["indices"])

        if active_tab == "market":
            render_spy_summary_card(
                quote, quote["price"], quote["change"], quote["change_pct"],
                gap_data["daily_df"],
                rsi=rsi,
                vix_snapshot=overview["vix"],
                pc_data=pc,
            )
            st.divider()
            render_spy_chart_section(quote)
            st.divider()
            render_rsi_top_signals(rsi_top)
            st.divider()
            try:
                render_ai_forecast(gap_data["gaps_df"], gap_data["quote"])
                st.divider()
            except Exception:
                pass
            _render_gap_section(gap_data)
        else:
            render_dte_conditions(
                quote["price"], overview["vix"], rsi, pc,
                vwap=intraday["vwap"],
                or_high=intraday["or_high"],
                or_low=intraday["or_low"],
                pdh=intraday["pdh"],
                pdl=intraday["pdl"],
                prev_close=intraday["prev_close"],
            )
            st.divider()
            render_options_intelligence(quote["price"])

    _live_section()


# ── Private helpers ────────────────────────────────────────────────────────────

def _fetch_rsi_top_analysis() -> dict:
    try:
        return get_rsi_top_analysis()
    except Exception:
        return {}


def _fetch_daily_rsi() -> float | None:
    try:
        df = get_spy_chart_df(period="2y", interval="1d")
        if not df.empty and "RSI" in df.columns:
            series = df["RSI"].dropna()
            if not series.empty:
                return float(series.iloc[-1])
    except Exception:
        pass
    return None


def _fetch_pc_ratio() -> dict | None:
    try:
        return get_put_call_ratio(scope="daily")
    except Exception:
        return None


def _fetch_intraday_signals(quote: dict) -> dict:
    result: dict = {
        "vwap": None, "or_high": None, "or_low": None,
        "pdh": None, "pdl": None,
        "prev_close": quote.get("prev_close"),
    }
    try:
        df = get_spy_chart_df(period="1d", interval="5m")
        if not df.empty and "Volume" in df.columns and not df["Volume"].isna().all():
            tp     = (df["High"] + df["Low"] + df["Close"]) / 3
            cumvol = df["Volume"].cumsum()
            vwap   = (tp * df["Volume"]).cumsum() / cumvol.replace(0, float("nan"))
            last   = vwap.dropna()
            if not last.empty:
                result["vwap"] = float(last.iloc[-1])
        if not df.empty and len(df) >= 3:
            _or = df.head(3)
            result["or_high"] = float(_or["High"].max())
            result["or_low"]  = float(_or["Low"].min())
    except Exception:
        pass
    try:
        daily = get_spy_chart_df(period="5d", interval="1d")
        if len(daily) >= 2:
            prev = daily.iloc[-2]
            result["pdh"] = float(prev["High"])
            result["pdl"] = float(prev["Low"])
    except Exception:
        pass
    return result


def _render_gap_section(gap_data: dict) -> None:
    gaps_df = gap_data["gaps_df"]
    try:
        parsed    = urllib.parse.urlparse(st.context.url)
        share_url = f"{parsed.scheme}://{parsed.netloc}/spy-gaps"
    except Exception:
        share_url = "/spy-gaps"

    render_gap_table(
        gaps_df,
        title="Daily Gaps (Last 30 Days)",
        show_rsi=True,
        show_next_day=True,
        show_type=True,
        share_url=share_url,
    )


render_spy_dashboard_tab()
