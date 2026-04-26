"""SPY Dashboard page — thin orchestrator that composes panels."""

import urllib.parse

import streamlit as st

from stockiq.backend.services.market_service import get_market_overview
from stockiq.backend.services.spy_service import (
    get_put_call_ratio,
    get_spy_chart_df,
    get_spy_gap_table_data,
    get_spy_quote,
)
from stockiq.frontend.views.components.gap_table import render_gap_table
from stockiq.frontend.views.components.summary_card import render_spy_summary_card
from stockiq.frontend.views.panels.ai_forecast import render_ai_forecast
from stockiq.frontend.views.panels.dte_conditions import render_dte_conditions
from stockiq.frontend.views.panels.options_intelligence import render_options_intelligence
from stockiq.frontend.views.panels.spy_chart import render_spy_chart_section
from stockiq.frontend.views.panels.spy_header import render_spy_header


def render_spy_dashboard_tab() -> None:
    # Gap data is historical (changes once at market open) — fetch once per page load,
    # not on every fragment refresh.
    gap_data = get_spy_gap_table_data()

    @st.fragment(run_every="90s")
    def _live_section() -> None:
        quote = get_spy_quote()
        if not quote:
            st.error("Could not load SPY data. Please try again in a moment.")
            return

        overview = get_market_overview()
        rsi = _fetch_daily_rsi()
        pc  = _fetch_pc_ratio()

        render_spy_header(quote, overview["indices"])
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
        intraday = _fetch_intraday_signals(quote)
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

    st.divider()
    try:
        render_ai_forecast(gap_data["gaps_df"], gap_data["quote"])
        st.divider()
    except Exception:
        pass
    _render_gap_section(gap_data)


# ── Private helpers ────────────────────────────────────────────────────────────

def _fetch_daily_rsi() -> float | None:
    try:
        df = get_spy_chart_df(period="1y", interval="1d")
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
        share_url=share_url,
    )


render_spy_dashboard_tab()
