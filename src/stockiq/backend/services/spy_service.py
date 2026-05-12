"""SPY-specific data assembly service."""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from stockiq.backend.config import OPTIONS_SPY_PROVIDERS, QUOTE_SPY_PROVIDERS
from stockiq.backend.data.spy import (
    fetch_put_call_ratio,
    fetch_put_call_ratio_cboe,
    fetch_spx_intraday,
    fetch_spx_quote,
    fetch_spx_quote_cboe,
    fetch_spy_options_data,
    fetch_spy_options_data_cboe,
)
from stockiq.backend.data.market import fetch_vix_ohlc
from stockiq.backend.data.local_gap_cache import apply_gap_cache, save_confirmed_gaps
from stockiq.backend.data.local_ohlc_cache import enrich_with_cache
from stockiq.backend.data.yf_fetch import fetch_ohlcv
from stockiq.backend.models.indicators import classify_gap_types, compute_daily_gaps, compute_rsi, patch_today_gap
from stockiq.backend.models.options import (
    compute_max_pain, compute_oi_by_strike, label_expirations,
    compute_gex, compute_gex_components, compute_expected_move, compute_sweep_signals, compute_vol_regime,
    compute_put_call_ratio,
)

_QUOTE_FETCHERS = {
    "yahoo": fetch_spx_quote,
    "cboe":  fetch_spx_quote_cboe,
}
_OPTIONS_CHAIN_FETCHERS = {
    "yahoo": fetch_spy_options_data,
    "cboe":  fetch_spy_options_data_cboe,
}
_PCR_FETCHERS = {
    "yahoo": fetch_put_call_ratio,
    "cboe":  fetch_put_call_ratio_cboe,
}


def get_spy_quote() -> dict:
    """
    Live SPY quote — fetches all configured providers in parallel, returns the freshest result.
    Freshness is determined by the _ts (Unix timestamp) field each fetcher includes.
    Falls back to any non-empty result when timestamps are unavailable.
    """
    fetchers = [_QUOTE_FETCHERS[p] for p in QUOTE_SPY_PROVIDERS if p in _QUOTE_FETCHERS]
    if not fetchers:
        return {}

    results: list[dict] = []
    pool = ThreadPoolExecutor(max_workers=len(fetchers))
    try:
        futures = {pool.submit(f): f for f in fetchers}
        try:
            for future in as_completed(futures, timeout=12):
                try:
                    r = future.result()
                    if r.get("price", 0) > 0:
                        results.append(r)
                except Exception:
                    pass
        except TimeoutError:
            pass  # use whatever results arrived before timeout
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    if not results:
        return {}
    return max(results, key=lambda r: r.get("_ts", 0))


def _get_spy_daily_df() -> pd.DataFrame:
    """Enriched 1-year daily SPY OHLCV (local-cache-filled). Cached 120 s."""
    return enrich_with_cache(fetch_spx_intraday(period="1y", interval="1d"), "SPY")


def get_spy_chart_df(period: str, interval: str) -> pd.DataFrame:
    """SPY OHLCV + RSI for any period/interval combination (chart display). Cached 120 s."""
    df = fetch_spx_intraday(period=period, interval=interval)
    if not df.empty:
        df = df.copy()
        df["RSI"] = compute_rsi(df)
    return df


def _get_spy_long_rsi() -> pd.Series:
    spy_long_df = fetch_ohlcv("SPY", 365)
    rsi = compute_rsi(spy_long_df)
    return rsi[~spy_long_df.index.duplicated(keep="last")]


def get_spy_gap_table_data() -> dict:
    """
    Fully assembled SPY gap table data.

    Returns:
        {
          "gaps_df":  DataFrame with Gap, RSI, Next Day columns
          "quote":    live quote dict
          "daily_df": enriched 1Y daily df (for AI forecast context)
        }
    """
    daily_df = _get_spy_daily_df()
    quote    = get_spy_quote()
    rsi_long = _get_spy_long_rsi()

    raw_gaps = compute_daily_gaps(daily_df)
    if raw_gaps.empty:
        return {"gaps_df": pd.DataFrame(), "quote": quote, "daily_df": daily_df}
    gaps_df = apply_gap_cache(patch_today_gap(raw_gaps, quote))
    save_confirmed_gaps(gaps_df)

    if not gaps_df.empty:
        last = gaps_df.index[-1]
        if quote.get("price"):
            gaps_df.at[last, "Close"] = round(float(quote["price"]), 2)
        if quote.get("day_high"):
            gaps_df.at[last, "High"] = round(float(quote["day_high"]), 2)
        if quote.get("day_low"):
            gaps_df.at[last, "Low"] = round(float(quote["day_low"]), 2)

    gaps_df["Next Close"] = gaps_df["Close"].shift(-1)
    gaps_df["Next Day"] = gaps_df.apply(
        lambda r: "▲" if (pd.notna(r["Next Close"]) and r["Next Close"] > r["Close"])
                  else ("▼" if (pd.notna(r["Next Close"]) and r["Next Close"] < r["Close"])
                  else "—"),
        axis=1,
    )

    gaps_df["RSI"]  = rsi_long.reindex(gaps_df.index)
    gaps_df["Type"] = classify_gap_types(gaps_df)

    return {"gaps_df": gaps_df, "quote": quote, "daily_df": daily_df}


def get_put_call_ratio(scope: str = "daily") -> dict | None:
    """SPY put/call ratio with sentiment signal. scope: 'daily' | '7d' | '14d' | '21d' | 'monthly'."""
    for provider in OPTIONS_SPY_PROVIDERS:
        fetcher = _PCR_FETCHERS.get(provider)
        if fetcher:
            result = fetcher(scope=scope)
            if result and result.get("puts", 0) > 0 and result.get("calls", 0) > 0:
                return result
    return None


def _yahoo_chain_for_bid_ask(expiration: str, side: str) -> pd.DataFrame:
    """
    Fetch bid/ask from the Yahoo chain for a specific expiration.
    CBOE is preferred for OI but only Yahoo carries live bid/ask quotes.
    Returns an empty DataFrame on any failure.
    """
    try:
        data = fetch_spy_options_data(expiration=expiration)
        if data:
            return data[side]
    except Exception:
        pass
    return pd.DataFrame()


def get_spy_gaps_df() -> pd.DataFrame:
    """
    Unfilled SPY daily gaps for reference-target computation in strategy suggester.
    Reuses the already-cached daily OHLCV — no extra network call.
    Returns DataFrame with Gap, Gap %, Gap Filled, Prev Close, Type columns (DatetimeIndex).
    """
    from stockiq.backend.models.indicators import compute_daily_gaps, patch_today_gap
    from stockiq.backend.data.local_gap_cache import apply_gap_cache
    try:
        daily_df = _get_spy_daily_df()
        if daily_df.empty:
            return pd.DataFrame()
        quote   = get_spy_quote()
        raw     = compute_daily_gaps(daily_df)
        if raw.empty:
            return pd.DataFrame()
        gaps = apply_gap_cache(patch_today_gap(raw, quote))
        gaps["Type"] = classify_gap_types(gaps)
        return gaps
    except Exception:
        return pd.DataFrame()


def get_rsi_top_analysis() -> dict:
    """RSI-based market top detection: divergence, TF stack, failure swing, MA stretch, breadth."""
    from stockiq.backend.models.rsi_top import (
        check_breadth_divergence,
        check_rsi_timeframe_stack,
        compute_ma_stretch,
        detect_bearish_rsi_divergence,
        detect_rsi_failure_swing,
    )
    try:
        daily_df = get_spy_chart_df(period="2y", interval="1d")
        if daily_df.empty:
            return {}
        return {
            "divergence":    detect_bearish_rsi_divergence(daily_df),
            "tf_stack":      check_rsi_timeframe_stack(daily_df),
            "failure_swing": detect_rsi_failure_swing(daily_df),
            "ma_stretch":    compute_ma_stretch(daily_df),
            "breadth":       check_breadth_divergence(daily_df),
        }
    except Exception:
        return {}


def get_vol_regime() -> dict | None:
    """IV Rank, HV30, IV30 (VIX) and strategy bias for options premium selection."""
    try:
        vix_df = fetch_vix_ohlc(period="1y")
        spy_df = fetch_spx_intraday(period="1y", interval="1d")
        if vix_df.empty or spy_df.empty:
            return None
        vix_close = vix_df["Close"].dropna()
        spy_close = spy_df["Close"].dropna() if "Close" in spy_df.columns else pd.Series(dtype=float)
        return compute_vol_regime(vix_close, spy_close)
    except Exception:
        return None


def get_spy_options_analysis(
    expiration: str = "",
    current_price: float = 0.0,
) -> dict | None:
    """
    Max pain + OI-by-strike for one SPY expiration.

    Returns:
        {
          "max_pain":    float         — strike where total OI dollar pain is minimised
          "oi_df":       DataFrame     — columns: strike, call_oi, put_oi (30 strikes around price)
          "expiration":  str           — ISO date used
          "expirations": list[str]     — all available ISO dates
          "exp_labels":  list[str]     — human-readable labels e.g. "Apr 25 (5d)"
        }
    or None if options data is unavailable.
    """
    def _has_oi(d: dict) -> bool:
        return bool(d) and (
            int(d["calls"]["openInterest"].sum()) + int(d["puts"]["openInterest"].sum()) > 0
        )

    data = None
    for provider in OPTIONS_SPY_PROVIDERS:
        fetcher = _OPTIONS_CHAIN_FETCHERS.get(provider)
        if fetcher:
            candidate = fetcher(expiration=expiration)
            if _has_oi(candidate):
                data = candidate
                break
    if not data:
        return None

    max_pain      = compute_max_pain(data["calls"], data["puts"])
    oi_df         = compute_oi_by_strike(data["calls"], data["puts"], current_price or max_pain)
    expected_move = compute_expected_move(data["calls"], data["puts"], current_price or max_pain, data["expiration"])
    pc            = compute_put_call_ratio(data["calls"], data["puts"], data["expiration"])

    # Yahoo chain carries volume, bid/ask, and reliable IV (CBOE iv=0 for short-dated expirations)
    raw_calls = _yahoo_chain_for_bid_ask(data["expiration"], "calls")
    raw_puts  = _yahoo_chain_for_bid_ask(data["expiration"], "puts")
    sweep_df  = compute_sweep_signals(raw_calls, raw_puts, current_price or max_pain)

    # GEX requires IV — CBOE returns iv=0 for short-dated expirations (0DTE/1DTE),
    # and both CBOE and Yahoo return iv=0 after market hours (no bid/ask).
    # Strategy: use Yahoo as base (best IV), fill OI from CBOE per-strike where Yahoo=0.
    # This handles all cases without wholesale switching:
    #   - Longer-dated: Yahoo has OI everywhere → merge is a no-op.
    #   - 0DTE: Yahoo OI=0 everywhere → all OI comes from CBOE.
    #   - 1DTE: Yahoo missing OI at specific strikes → those gaps filled from CBOE.
    _ydata = fetch_spy_options_data(expiration=data["expiration"])
    _yahoo_ok = (
        _ydata
        and _ydata.get("expiration") == data["expiration"]
        and not _ydata["calls"].empty
        and "impliedVolatility" in _ydata["calls"].columns
    )
    _yahoo_has_iv = _yahoo_ok and (_ydata["calls"]["impliedVolatility"] > 0.001).any()

    if _yahoo_has_iv:
        # CBOE provides the complete strike universe (never drops far-OTM strikes).
        # Yahoo provides accurate IV (CBOE IV=0 for short-dated) and timely OI for
        # longer-dated expirations.  Merge: start with CBOE, overlay Yahoo IV where
        # valid, prefer Yahoo OI where non-zero (more current for weekly/monthly).
        def _best_gex_chain(cboe_df: pd.DataFrame, yahoo_df: pd.DataFrame) -> pd.DataFrame:
            out = cboe_df.copy()
            if yahoo_df.empty:
                return out
            y = yahoo_df.set_index("strike")
            if "impliedVolatility" in y.columns:
                yiv = out["strike"].map(y["impliedVolatility"]).fillna(0)
                out.loc[yiv > 0.001, "impliedVolatility"] = yiv[yiv > 0.001]
            if "openInterest" in y.columns:
                yoi = out["strike"].map(y["openInterest"]).fillna(0)
                out.loc[yoi > 0, "openInterest"] = yoi[yoi > 0]
            return out
        _gex_calls = _best_gex_chain(data["calls"], _ydata["calls"])
        _gex_puts  = _best_gex_chain(data["puts"],  _ydata["puts"])
    else:
        # No usable Yahoo IV — fall back to CBOE + VIX fallback
        _gex_calls = data["calls"]
        _gex_puts  = data["puts"]

    # VIX-based fallback IV for after-hours when chain IV is universally 0
    try:
        _vix_df = fetch_vix_ohlc(period="5d")
        _fallback_iv = float(_vix_df["Close"].iloc[-1]) / 100 if not _vix_df.empty else 0.20
    except Exception:
        _fallback_iv = 0.20

    gex_df         = compute_gex(_gex_calls, _gex_puts, current_price or max_pain, data["expiration"], fallback_iv=_fallback_iv)
    gex_components = compute_gex_components(_gex_calls, _gex_puts, current_price or max_pain, data["expiration"], fallback_iv=_fallback_iv)

    return {
        "max_pain":       max_pain,
        "oi_df":          oi_df,
        "gex_df":         gex_df,
        "gex_components": gex_components,
        "expected_move": expected_move,
        "pc":            pc,
        "sweep_signals": sweep_df,
        "expiration":    data["expiration"],
        "expirations":   data["expirations"],
        "exp_labels":    label_expirations(data["expirations"]),
        "raw_calls":     raw_calls,
        "raw_puts":      raw_puts,
    }


def get_spy_aggregated_gex(
    expirations: list[str],
    current_price: float,
    max_exp: int = 6,
) -> pd.DataFrame:
    """Sum GEX across the nearest max_exp expirations by strike.

    Gives the net dealer book exposure — what dealers must hedge across their
    entire options book, not just one expiration.  Positive GEX = long gamma
    (stabilising); negative GEX = short gamma (amplifying).
    """
    def _fetch(exp: str) -> pd.DataFrame:
        try:
            d = get_spy_options_analysis(expiration=exp, current_price=current_price)
            return d.get("gex_df", pd.DataFrame()) if d else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for gdf in pool.map(_fetch, expirations[:max_exp]):
            if gdf is not None and not gdf.empty:
                frames.append(gdf)

    if not frames:
        return pd.DataFrame()

    raw = (
        pd.concat(frames)
        .groupby("strike", as_index=False)["gex"].sum()
    )
    # Bucket to $5 strike increments so $1-increment 0DTE chains don't create
    # 60 thin bars in the chart (CBOE near-term chains use $1 increments).
    raw["strike"] = (raw["strike"] / 5).round() * 5
    return (
        raw.groupby("strike", as_index=False)["gex"].sum()
        .sort_values("strike")
        .reset_index(drop=True)
    )
