"""Options analytics: max pain and open interest by strike."""

from datetime import datetime

import numpy as np
import pandas as pd


def compute_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float:
    """
    Return the max-pain strike — the price at which total in-the-money dollar
    value across all open contracts is minimised (dealers gain most).

    Algorithm (vectorised):
      For each candidate strike S:
        call_pain = Σ (S − K) × call_OI  for every call strike K < S
        put_pain  = Σ (K − S) × put_OI   for every put  strike K > S
      max_pain = argmin(call_pain + put_pain)
    """
    call_oi = (
        calls[["strike", "openInterest"]]
        .rename(columns={"openInterest": "call_oi"})
        .groupby("strike", as_index=False)["call_oi"].sum()
    )
    put_oi = (
        puts[["strike", "openInterest"]]
        .rename(columns={"openInterest": "put_oi"})
        .groupby("strike", as_index=False)["put_oi"].sum()
    )
    merged = (
        pd.merge(call_oi, put_oi, on="strike", how="outer")
        .fillna(0)
        .sort_values("strike")
        .reset_index(drop=True)
    )

    strikes      = merged["strike"].values
    call_oi_vals = merged["call_oi"].values
    put_oi_vals  = merged["put_oi"].values

    # Vectorised pain matrix: rows = candidate strikes, cols = chain strikes
    s = strikes[:, np.newaxis]      # (n, 1)
    k = strikes[np.newaxis, :]      # (1, n)

    call_pain = np.sum(np.maximum(s - k, 0) * call_oi_vals, axis=1)
    put_pain  = np.sum(np.maximum(k - s, 0) * put_oi_vals,  axis=1)

    return float(strikes[np.argmin(call_pain + put_pain)])


def compute_oi_by_strike(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    current_price: float,
    n_strikes: int = 30,
) -> pd.DataFrame:
    """
    Return call OI and put OI aggregated per strike, filtered to the
    n_strikes nearest to current_price (split evenly above and below).

    Returns columns: strike, call_oi, put_oi
    """
    call_oi = (
        calls[["strike", "openInterest"]]
        .rename(columns={"openInterest": "call_oi"})
        .groupby("strike", as_index=False)["call_oi"].sum()
    )
    put_oi = (
        puts[["strike", "openInterest"]]
        .rename(columns={"openInterest": "put_oi"})
        .groupby("strike", as_index=False)["put_oi"].sum()
    )
    oi = (
        pd.merge(call_oi, put_oi, on="strike", how="outer")
        .fillna(0)
        .sort_values("strike")
        .reset_index(drop=True)
    )

    idx  = int(np.searchsorted(oi["strike"].values, current_price))
    half = n_strikes // 2
    lo   = max(0, idx - half)
    hi   = min(len(oi), lo + n_strikes)
    lo   = max(0, hi - n_strikes)          # re-align if we hit the top

    return oi.iloc[lo:hi].reset_index(drop=True)


def compute_gex(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    current_price: float,
    expiration: str,
    fallback_iv: float = 0.0,
) -> pd.DataFrame:
    """
    Dealer Gamma Exposure (GEX) by strike using Black-Scholes gamma.
    Positive GEX = dealers long gamma (stabilising — they buy dips, sell rips).
    Negative GEX = dealers short gamma (amplifying — moves accelerate).
    Returns DataFrame: strike, gex (in dollars).

    fallback_iv: used for strikes where the chain reports IV=0 (e.g. after market
    hours when bid/ask are stale). Pass VIX/100 for a reasonable estimate.
    """
    try:
        dte = max((datetime.strptime(expiration, "%Y-%m-%d").date()
                   - datetime.today().date()).days, 0)
    except Exception:
        dte = 7
    T = max(dte, 1) / 365.0
    r = 0.045  # approximate risk-free rate

    def _gex_series(df: pd.DataFrame, sign: float) -> pd.DataFrame:
        K     = df["strike"].values.astype(float)
        sigma = df["impliedVolatility"].fillna(0).values.astype(float)
        oi    = df["openInterest"].fillna(0).values.astype(float)
        # Fill zero/missing IV with fallback (VIX-based) so GEX is still computable
        # after market hours when option chains report IV=0 across all strikes.
        if fallback_iv > 0.001:
            sigma = np.where(sigma < 0.001, fallback_iv, sigma)
        valid = (sigma > 0.001) & (oi > 0) & (K > 0)
        if not valid.any():
            return pd.DataFrame(columns=["strike", "gex"])
        K, sigma, oi, strikes = K[valid], sigma[valid], oi[valid], K[valid]
        d1    = (np.log(current_price / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        gamma = np.exp(-0.5 * d1**2) / (np.sqrt(2 * np.pi) * current_price * sigma * np.sqrt(T))
        gex   = sign * gamma * oi * 100 * current_price
        return pd.DataFrame({"strike": strikes, "gex": gex})

    combined = (
        pd.concat([_gex_series(calls, +1), _gex_series(puts, -1)])
        .groupby("strike", as_index=False)["gex"].sum()
        .sort_values("strike")
        .reset_index(drop=True)
    )
    return combined


def compute_gex_components(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    current_price: float,
    expiration: str,
    fallback_iv: float = 0.0,
) -> dict:
    """
    GEX breakdown for the summary card.

    Returns:
        call_gex   — total positive GEX from calls ($)
        put_gex    — total negative GEX from puts ($)
        net_gex    — call_gex + put_gex
        total_gex  — |call_gex| + |put_gex|  (gross notional)
        call_oi    — total call open interest
        put_oi     — total put open interest
        call_wall  — strike with highest call GEX (dealer resistance level)
        put_wall   — strike with most negative put GEX (dealer support level)
        zero_gamma — interpolated strike where net GEX crosses zero (None if not found)
    """
    try:
        dte = max((datetime.strptime(expiration, "%Y-%m-%d").date()
                   - datetime.today().date()).days, 0)
    except Exception:
        dte = 7
    T = max(dte, 1) / 365.0
    r = 0.045

    def _series(df: pd.DataFrame, sign: float) -> pd.DataFrame:
        K     = df["strike"].values.astype(float)
        sigma = df["impliedVolatility"].fillna(0).values.astype(float)
        oi    = df["openInterest"].fillna(0).values.astype(float)
        if fallback_iv > 0.001:
            sigma = np.where(sigma < 0.001, fallback_iv, sigma)
        valid = (sigma > 0.001) & (oi > 0) & (K > 0)
        if not valid.any():
            return pd.DataFrame(columns=["strike", "gex"])
        K, sigma, oi = K[valid], sigma[valid], oi[valid]
        d1    = (np.log(current_price / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        gamma = np.exp(-0.5 * d1**2) / (np.sqrt(2 * np.pi) * current_price * sigma * np.sqrt(T))
        return pd.DataFrame({"strike": K, "gex": sign * gamma * oi * 100 * current_price})

    call_df = _series(calls, +1).groupby("strike", as_index=False)["gex"].sum()
    put_df  = _series(puts,  -1).groupby("strike", as_index=False)["gex"].sum()

    call_gex  = float(call_df["gex"].sum()) if not call_df.empty else 0.0
    put_gex   = float(put_df["gex"].sum())  if not put_df.empty  else 0.0
    call_wall = float(call_df.loc[call_df["gex"].idxmax(), "strike"]) if not call_df.empty else None
    put_wall  = float(put_df.loc[put_df["gex"].idxmin(),  "strike"])  if not put_df.empty  else None

    # Zero gamma: strike nearest ATM where net GEX profile crosses zero
    combined = (
        pd.concat([call_df, put_df])
        .groupby("strike", as_index=False)["gex"].sum()
        .sort_values("strike")
        .reset_index(drop=True)
    )
    zero_gamma: float | None = None
    if len(combined) >= 2:
        s, g = combined["strike"].values, combined["gex"].values
        crossings = [
            float(s[i] + (s[i + 1] - s[i]) * (-g[i]) / (g[i + 1] - g[i]))
            for i in range(len(g) - 1)
            if g[i] * g[i + 1] < 0
        ]
        if crossings:
            zero_gamma = round(min(crossings, key=lambda x: abs(x - current_price)), 2)

    return {
        "call_gex":   call_gex,
        "put_gex":    put_gex,
        "net_gex":    call_gex + put_gex,
        "total_gex":  abs(call_gex) + abs(put_gex),
        "call_oi":    int(calls["openInterest"].fillna(0).sum()),
        "put_oi":     int(puts["openInterest"].fillna(0).sum()),
        "call_wall":  call_wall,
        "put_wall":   put_wall,
        "zero_gamma": zero_gamma,
    }


def compute_expected_move(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    current_price: float,
    expiration: str = "",
) -> dict | None:
    """
    Expected move as 1-sigma implied range by expiration (~68% probability).

    Primary method: ATM straddle mid-price (call + put).
    Fallback: ATM implied volatility × spot × √(DTE/365) — works when bid/ask
    are unavailable (CBOE provider) or zero (market closed).
    Returns {'move', 'pct', 'atm_strike', 'low', 'high', 'method'} or None.
    """
    def _nearest_strike(df: pd.DataFrame, price: float) -> float | None:
        s = df["strike"].values
        return float(s[np.argmin(np.abs(s - price))]) if len(s) else None

    def _mid(df: pd.DataFrame, target_strike: float) -> float:
        # Find exact row; fall back to nearest strike if exact match missing
        row = df[df["strike"] == target_strike]
        if row.empty:
            nearest = _nearest_strike(df, target_strike)
            if nearest is None:
                return 0.0
            row = df[df["strike"] == nearest]
        if row.empty:
            return 0.0
        bid  = float(row["bid"].iloc[0])       if "bid"       in row.columns else 0.0
        ask  = float(row["ask"].iloc[0])       if "ask"       in row.columns else 0.0
        last = float(row["lastPrice"].iloc[0]) if "lastPrice" in row.columns else 0.0
        # Prefer mid; use whichever side is available rather than requiring both
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
        if bid > 0:
            return bid
        if ask > 0:
            return ask
        return last

    def _atm_iv(df: pd.DataFrame, target_strike: float) -> float:
        """Return IV at the nearest available strike; 0.0 if unavailable."""
        if "impliedVolatility" not in df.columns:
            return 0.0
        nearest = _nearest_strike(df, target_strike)
        if nearest is None:
            return 0.0
        row = df[df["strike"] == nearest]
        if row.empty:
            return 0.0
        return float(row["impliedVolatility"].iloc[0])

    # ATM = nearest strike to current_price across both calls and puts combined
    all_strikes = np.union1d(calls["strike"].values, puts["strike"].values)
    if len(all_strikes) == 0:
        return None
    atm = float(all_strikes[np.argmin(np.abs(all_strikes - current_price))])

    # Primary: straddle mid-price
    em     = _mid(calls, atm) + _mid(puts, atm)
    method = "straddle"

    # Fallback: IV-based when straddle yields zero (CBOE data or market closed)
    if em <= 0:
        iv_c = _atm_iv(calls, atm)
        iv_p = _atm_iv(puts,  atm)
        iv   = (iv_c + iv_p) / 2 if iv_c > 0 and iv_p > 0 else max(iv_c, iv_p)
        if iv > 0:
            dte = 0
            if expiration:
                try:
                    dte = (datetime.strptime(expiration, "%Y-%m-%d").date()
                           - datetime.today().date()).days
                except Exception:
                    pass
            # For same-day or past expiry use intraday DTE (0.5 trading day)
            t = max(dte, 0.5) / 365.0
            em     = current_price * iv * np.sqrt(t)
            method = "iv-based"

    if em <= 0:
        return None
    return {
        "move":       round(em, 2),
        "pct":        round(em / current_price * 100, 2),
        "atm_strike": atm,
        "low":        round(current_price - em, 2),
        "high":       round(current_price + em, 2),
        "method":     method,
    }


def compute_vol_regime(
    vix_close: pd.Series,
    spy_close: pd.Series,
) -> dict | None:
    """
    Volatility regime for options strategy selection.

    IV Rank  = (VIX_now - VIX_52w_low) / (VIX_52w_high - VIX_52w_low) × 100
    HV30     = 30-day annualized realized vol from SPY log returns
    IV30     = VIX (IS the 30-day annualized implied vol for S&P 500)
    IV/HV    = ratio > 1 means options price in more vol than SPY is delivering → sell premium
    """
    if vix_close.empty or len(vix_close) < 10:
        return None

    vix_now  = float(vix_close.iloc[-1])
    vix_52hi = float(vix_close.max())
    vix_52lo = float(vix_close.min())
    iv_rank  = (
        (vix_now - vix_52lo) / (vix_52hi - vix_52lo) * 100
        if vix_52hi > vix_52lo else 50.0
    )

    hv30 = None
    if len(spy_close) >= 31:
        log_rets = np.log(spy_close / spy_close.shift(1)).dropna()
        hv30 = float(log_rets.iloc[-30:].std() * np.sqrt(252) * 100)

    iv30       = vix_now
    iv_hv_ratio = iv30 / hv30 if hv30 and hv30 > 0 else None

    if iv_rank >= 50 and (iv_hv_ratio is None or iv_hv_ratio >= 1.1):
        bias, color = "SELL PREMIUM", "#22C55E"
        note = "Options overpriced vs realized moves — favor credit spreads, iron condors"
    elif iv_rank <= 30 or (iv_hv_ratio is not None and iv_hv_ratio < 0.9):
        bias, color = "BUY PREMIUM", "#A78BFA"
        note = "Options cheap vs realized moves — favor debit spreads, long straddles"
    else:
        bias, color = "NEUTRAL", "#F59E0B"
        note = "Mixed signals — smaller size, wait for cleaner setup"

    return {
        "iv_rank":        round(iv_rank, 1),
        "hv30":           round(hv30, 1) if hv30 else None,
        "iv30":           round(iv30, 1),
        "iv_hv_ratio":    round(iv_hv_ratio, 2) if iv_hv_ratio else None,
        "vix_52hi":       round(vix_52hi, 2),
        "vix_52lo":       round(vix_52lo, 2),
        "strategy_bias":  bias,
        "strategy_color": color,
        "strategy_note":  note,
    }


def compute_strategy_suggestion(
    current_price: float,
    em: dict | None,
    pc: dict | None,
    gex_df: pd.DataFrame,
    oi_df: pd.DataFrame,
    max_pain: float,
    vol: dict | None,
    gaps_df: pd.DataFrame | None = None,
) -> dict | None:
    """
    Synthesize options chain signals into a weekly strategy recommendation.

    Direction bias from: P/C ratio, max pain gravity, total GEX regime, OI wall proximity.
    Strategy type from: direction × vol regime (sell/buy premium).
    Strike hints from: expected move (30% / 60% of EM as short / long legs).
    Reference targets from: nearest unfilled gap fill, OI walls, EM boundary, max pain.
    """
    if not current_price:
        return None

    # ── Direction scoring ──────────────────────────────────────────────────────
    direction_votes: list[str] = []
    rationale: list[str] = []

    if pc:
        r = pc["ratio"]
        if r < 0.8:
            direction_votes.append("bullish")
            rationale.append(f"P/C {r:.2f} — call-heavy positioning, bullish tilt for this expiration")
        elif r > 1.2:
            direction_votes.append("bearish")
            rationale.append(f"P/C {r:.2f} — put-heavy positioning, bearish tilt for this expiration")
        else:
            direction_votes.append("neutral")
            rationale.append(f"P/C {r:.2f} — balanced positioning, no directional edge")

    if max_pain and current_price:
        dist = (max_pain - current_price) / current_price * 100
        if dist > 0.5:
            direction_votes.append("bullish")
            rationale.append(f"Max pain ${max_pain:,.0f} is {abs(dist):.1f}% above spot — gravitational pull upward")
        elif dist < -0.5:
            direction_votes.append("bearish")
            rationale.append(f"Max pain ${max_pain:,.0f} is {abs(dist):.1f}% below spot — gravitational pull downward")
        else:
            direction_votes.append("neutral")
            rationale.append(f"Max pain ${max_pain:,.0f} near spot — no clear directional pull")

    if not gex_df.empty:
        total_gex = float(gex_df["gex"].sum())
        if total_gex >= 0:
            direction_votes.append("neutral")
            rationale.append("Positive GEX — dealers stabilise price, rangebound conditions favoured")
        else:
            near = gex_df[
                (gex_df["strike"] >= current_price * 0.99) &
                (gex_df["strike"] <= current_price * 1.01)
            ]
            near_gex = float(near["gex"].sum()) if not near.empty else 0.0
            if near_gex < -1e7:
                direction_votes.append("bearish")
                rationale.append("Negative near-ATM GEX — dealer hedging amplifies downside moves")
            else:
                direction_votes.append("neutral")
                rationale.append("Negative GEX regime — amplified moves but direction unclear")

    if not oi_df.empty:
        call_wall  = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"])
        put_wall   = float(oi_df.loc[oi_df["put_oi"].idxmax(),  "strike"])
        dist_call  = (call_wall - current_price) / current_price * 100
        dist_put   = (put_wall  - current_price) / current_price * 100
        put_close  = dist_put < 0 and abs(dist_put) < 1.5
        call_close = dist_call > 0 and dist_call < 1.5
        if put_close and call_close:
            direction_votes.append("neutral")
            rationale.append(
                f"Price pinned: put wall ${put_wall:,.0f} ({abs(dist_put):.1f}% below) "
                f"& call wall ${call_wall:,.0f} (+{dist_call:.1f}% above)"
            )
        elif put_close:
            direction_votes.append("bullish")
            rationale.append(f"Put wall ${put_wall:,.0f} ({abs(dist_put):.1f}% below) — strong nearby floor")
        elif call_close:
            direction_votes.append("bearish")
            rationale.append(f"Call wall ${call_wall:,.0f} (+{dist_call:.1f}% above) — ceiling nearby, resistance likely")

    bull_n = direction_votes.count("bullish")
    bear_n = direction_votes.count("bearish")
    neu_n  = direction_votes.count("neutral")

    if bull_n > bear_n and bull_n > neu_n:
        direction, dir_color = "Bullish", "#22C55E"
    elif bear_n > bull_n and bear_n > neu_n:
        direction, dir_color = "Bearish", "#EF4444"
    else:
        direction, dir_color = "Neutral", "#F59E0B"

    max_agree  = max(bull_n, bear_n, neu_n)
    confidence = "HIGH" if max_agree >= 3 else "MODERATE" if max_agree >= 2 else "LOW"
    conf_color = "#22C55E" if confidence == "HIGH" else "#F59E0B" if confidence == "MODERATE" else "#EF4444"

    # ── Strategy selection ─────────────────────────────────────────────────────
    vol_bias = vol["strategy_bias"] if vol else "NEUTRAL"
    vb_color = vol["strategy_color"] if vol else "#F59E0B"

    if direction == "Neutral":
        if vol_bias == "SELL PREMIUM":
            strategy, strat_color = "Iron Condor", "#22C55E"
            strat_note = "Range-bound + high IV — sell credit on both sides within the EM range"
        elif vol_bias == "BUY PREMIUM":
            strategy, strat_color = "Long Straddle", "#A78BFA"
            strat_note = "Range-bound direction but cheap IV — buy ATM straddle for a breakout"
        else:
            strategy, strat_color = "Iron Condor", "#F59E0B"
            strat_note = "Neutral setup — iron condor with reduced size, mixed vol signals"
    elif direction == "Bullish":
        if vol_bias in ("SELL PREMIUM", "NEUTRAL"):
            strategy, strat_color = "Bull Put Spread", "#22C55E"
            strat_note = "Bullish + high IV — sell put spread below the market, collect premium"
        else:
            strategy, strat_color = "Bull Call Spread", "#22C55E"
            strat_note = "Bullish + cheap IV — buy call debit spread above the market"
    else:
        if vol_bias in ("SELL PREMIUM", "NEUTRAL"):
            strategy, strat_color = "Bear Call Spread", "#EF4444"
            strat_note = "Bearish + high IV — sell call spread above the market, collect premium"
        else:
            strategy, strat_color = "Bear Put Spread", "#EF4444"
            strat_note = "Bearish + cheap IV — buy put debit spread below the market"

    # ── Strike hints from expected move ───────────────────────────────────────
    strike_label = ""
    if em:
        move = em["move"]
        if strategy == "Bull Put Spread":
            strike_label = (f"Short ${current_price - move * 0.3:,.0f} "
                            f"· Long ${current_price - move * 0.6:,.0f}")
        elif strategy == "Bear Call Spread":
            strike_label = (f"Short ${current_price + move * 0.3:,.0f} "
                            f"· Long ${current_price + move * 0.6:,.0f}")
        elif strategy == "Iron Condor":
            strike_label = (f"Puts ${current_price - move * 0.6:,.0f}"
                            f"/{current_price - move * 0.3:,.0f} "
                            f"· Calls ${current_price + move * 0.3:,.0f}"
                            f"/{current_price + move * 0.6:,.0f}")
        elif strategy == "Bull Call Spread":
            strike_label = (f"Long ${current_price + move * 0.1:,.0f} "
                            f"· Short ${current_price + move * 0.4:,.0f}")
        elif strategy == "Bear Put Spread":
            strike_label = (f"Long ${current_price - move * 0.1:,.0f} "
                            f"· Short ${current_price - move * 0.4:,.0f}")
        elif strategy == "Long Straddle":
            strike_label = f"ATM ${current_price:,.0f} (call + put)"

    # ── Reference targets ─────────────────────────────────────────────────────
    call_wall_t: float | None = None
    put_wall_t:  float | None = None
    if not oi_df.empty:
        call_wall_t = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"])
        put_wall_t  = float(oi_df.loc[oi_df["put_oi"].idxmax(),  "strike"])

    # Nearest unfilled gap fill level in the trade direction
    gap_fill_level: float | None = None
    gap_fill_pct:   float | None = None
    gap_fill_date:  str   | None = None
    gap_fill_type:  str          = "—"
    if (gaps_df is not None and not gaps_df.empty
            and "Gap" in gaps_df.columns and "Prev Close" in gaps_df.columns
            and "Gap Filled" in gaps_df.columns):
        has_type_col = "Type" in gaps_df.columns
        unfilled = gaps_df[
            (gaps_df["Gap"].abs() >= 0.10) &
            (~gaps_df["Gap Filled"].astype(bool))
        ]
        if direction == "Bullish":
            above = unfilled[unfilled["Prev Close"] > current_price * 1.001]
            if not above.empty:
                idx            = (above["Prev Close"] - current_price).idxmin()
                gap_fill_level = round(float(above.at[idx, "Prev Close"]), 2)
                gap_fill_pct   = round((gap_fill_level - current_price) / current_price * 100, 2)
                gap_fill_date  = idx.strftime("%b %-d") if hasattr(idx, "strftime") else str(idx)[:10]
                gap_fill_type  = str(above.at[idx, "Type"]) if has_type_col else "—"
        elif direction == "Bearish":
            below = unfilled[unfilled["Prev Close"] < current_price * 0.999]
            if not below.empty:
                idx            = (current_price - below["Prev Close"]).idxmin()
                gap_fill_level = round(float(below.at[idx, "Prev Close"]), 2)
                gap_fill_pct   = round((gap_fill_level - current_price) / current_price * 100, 2)
                gap_fill_date  = idx.strftime("%b %-d") if hasattr(idx, "strftime") else str(idx)[:10]
                gap_fill_type  = str(below.at[idx, "Type"]) if has_type_col else "—"

    # Primary reference target (nearest meaningful level in trade direction)
    ref_target:  float | None = None
    ref_source:  str          = "—"
    stop_level:  float | None = None
    stop_source: str          = "—"
    total_gex = float(gex_df["gex"].sum()) if not gex_df.empty else 0.0

    def _gap_label(gtype: str) -> str:
        return f"Gap fill · {gtype}" if gtype and gtype != "—" else "Gap fill"

    if direction == "Bullish":
        cands = []
        breakaway_cand = None
        if gap_fill_level and gap_fill_level > current_price:
            entry = (gap_fill_level, _gap_label(gap_fill_type))
            if gap_fill_type == "Breakaway":
                breakaway_cand = entry
            else:
                cands.append(entry)
        if call_wall_t and call_wall_t > current_price:
            cands.append((call_wall_t, "Call wall"))
        if em and em["high"] > current_price:
            cands.append((em["high"], "EM upper"))
        if max_pain and max_pain > current_price:
            cands.append((max_pain, "Max pain"))
        if breakaway_cand:
            cands.append(breakaway_cand)
        if cands:
            ref_target, ref_source = min(cands, key=lambda x: x[0])
        if put_wall_t and put_wall_t < current_price:
            stop_level, stop_source = put_wall_t, "Put wall"
        elif em:
            stop_level, stop_source = em["low"], "EM lower"
        hold_note = (
            "Hold while GEX > 0 — dealer long gamma keeps dips shallow"
            if total_gex >= 0
            else "Negative GEX — moves can accelerate; take profits near target"
        )
    elif direction == "Bearish":
        cands = []
        breakaway_cand = None
        if gap_fill_level and gap_fill_level < current_price:
            entry = (gap_fill_level, _gap_label(gap_fill_type))
            if gap_fill_type == "Breakaway":
                breakaway_cand = entry
            else:
                cands.append(entry)
        if put_wall_t and put_wall_t < current_price:
            cands.append((put_wall_t, "Put wall"))
        if em and em["low"] < current_price:
            cands.append((em["low"], "EM lower"))
        if max_pain and max_pain < current_price:
            cands.append((max_pain, "Max pain"))
        if breakaway_cand:
            cands.append(breakaway_cand)
        if cands:
            ref_target, ref_source = max(cands, key=lambda x: x[0])
        if call_wall_t and call_wall_t > current_price:
            stop_level, stop_source = call_wall_t, "Call wall"
        elif em:
            stop_level, stop_source = em["high"], "EM upper"
        hold_note = (
            "Negative GEX amplifies drops — hold while GEX stays negative"
            if total_gex < 0
            else "Positive GEX dampens moves — take profits at target, not momentum plays"
        )
    else:
        ref_target  = em["high"] if em else None
        ref_source  = "EM upper"
        stop_level  = em["low"]  if em else None
        stop_source = "EM lower"
        hold_note   = "Iron condor profits if SPY stays within EM range through expiry"

    # Flag if max pain sits between current price and target (acts as friction)
    mp_headwind = bool(
        max_pain and ref_target and (
            (direction == "Bullish" and current_price < max_pain < ref_target) or
            (direction == "Bearish" and ref_target < max_pain < current_price)
        )
    )

    ref_pct  = round((ref_target - current_price) / current_price * 100, 2) if ref_target  else None
    stop_pct = round((stop_level - current_price) / current_price * 100, 2) if stop_level  else None

    return {
        "strategy":    strategy,
        "strat_color": strat_color,
        "strat_note":  strat_note,
        "direction":   direction,
        "dir_color":   dir_color,
        "confidence":  confidence,
        "conf_color":  conf_color,
        "vol_bias":    vol_bias,
        "vb_color":    vb_color,
        "strike_label":  strike_label,
        "em_low":        em["low"]  if em else None,
        "em_high":       em["high"] if em else None,
        "rationale":     rationale[:4],
        # Reference levels
        "ref_target":    ref_target,
        "ref_source":    ref_source,
        "ref_pct":       ref_pct,
        "stop_level":    stop_level,
        "stop_source":   stop_source,
        "stop_pct":      stop_pct,
        "gap_fill":      gap_fill_level,
        "gap_fill_pct":  gap_fill_pct,
        "gap_fill_date": gap_fill_date,
        "gap_fill_type": gap_fill_type,
        "mp_headwind":   mp_headwind,
        "hold_note":     hold_note,
    }


def compute_sweep_signals(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    current_price: float,
    vol_oi_threshold: float = 3.0,
    min_volume: int = 100,
    top_n: int = 8,
) -> pd.DataFrame:
    """
    Sweep proxy: flags OTM strikes where volume >> open interest.
    High vol/OI ratio means aggressive new positioning, not hedging —
    the hallmark of an institutional sweep.

    Returns columns: side, strike, volume, open_interest, vol_oi_ratio, iv, otm_pct
    sorted by vol_oi_ratio descending.
    """
    rows = []
    for df, side, otm_fn in [
        (calls, "CALL", lambda k: k > current_price),
        (puts,  "PUT",  lambda k: k < current_price),
    ]:
        if df.empty or "volume" not in df.columns or "openInterest" not in df.columns:
            continue
        d = df[otm_fn(df["strike"])].copy()
        d = d[(d["volume"] >= min_volume) & (d["openInterest"] > 0)]
        if d.empty:
            continue
        d["vol_oi_ratio"] = d["volume"] / d["openInterest"]
        d = d[d["vol_oi_ratio"] >= vol_oi_threshold]
        if d.empty:
            continue
        d["side"]    = side
        d["otm_pct"] = (d["strike"] - current_price) / current_price * 100
        d["iv"]      = d["impliedVolatility"].fillna(0) if "impliedVolatility" in d.columns else 0.0
        rows.append(d[["side", "strike", "volume", "openInterest", "vol_oi_ratio", "iv", "otm_pct"]])

    if not rows:
        return pd.DataFrame()

    return (
        pd.concat(rows, ignore_index=True)
        .rename(columns={"openInterest": "open_interest"})
        .sort_values("vol_oi_ratio", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def compute_put_call_ratio(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    expiration: str = "",
) -> dict | None:
    """
    P/C ratio computed directly from a single expiration's chain data.
    Uses volume for 0DTE (same-day) expirations, open interest for future dates.
    Falls back to open interest when volume is unavailable or zero.
    """
    try:
        dte = max(
            (datetime.strptime(expiration, "%Y-%m-%d").date() - datetime.today().date()).days, 0
        )
    except Exception:
        dte = 99

    use_volume = dte == 0

    def _total(df: pd.DataFrame, col: str) -> int:
        if col in df.columns:
            v = int(df[col].fillna(0).sum())
            if v > 0:
                return v
        return 0

    col = "volume" if use_volume else "openInterest"
    total_puts  = _total(puts,  col)
    total_calls = _total(calls, col)

    # Fall back to OI if volume is zero (e.g. market closed or CBOE provider)
    if use_volume and total_puts == 0 and total_calls == 0:
        total_puts  = _total(puts,  "openInterest")
        total_calls = _total(calls, "openInterest")
        use_volume  = False

    if not total_calls:
        return None

    ratio = round(total_puts / total_calls, 3)
    if ratio > 1.2:
        signal, color = "Extreme Fear — contrarian bullish", "#22C55E"
    elif ratio > 1.0:
        signal, color = "Fearful — mild bullish lean",       "#86EFAC"
    elif ratio > 0.8:
        signal, color = "Neutral",                            "#94A3B8"
    elif ratio > 0.6:
        signal, color = "Complacent — mild bearish lean",    "#F59E0B"
    else:
        signal, color = "Extreme Greed — contrarian bearish", "#EF4444"

    metric_lbl  = "Volume" if use_volume else "Open interest"
    scope_label = "0DTE" if dte == 0 else f"{dte}d"
    scope_note  = f"{metric_lbl} · {expiration} · {dte} day{'s' if dte != 1 else ''} to expiry"

    return {
        "ratio":       ratio,
        "signal":      signal,
        "color":       color,
        "puts":        total_puts,
        "calls":       total_calls,
        "scope_label": scope_label,
        "scope_note":  scope_note,
        "exp_count":   1,
        "exp_nearest": expiration,
        "exp_farthest": expiration,
    }


def label_expirations(expirations: list[str], today: datetime | None = None) -> list[str]:
    """
    Convert ISO expiration strings to human-readable labels with days-to-expiry.
    e.g. "2026-04-25" → "Apr 25 (5d)"
    """
    ref = (today or datetime.today()).date()
    labels = []
    for e in expirations:
        try:
            exp_date = datetime.strptime(e, "%Y-%m-%d").date()
            dte      = (exp_date - ref).days
            labels.append(f"{exp_date.strftime('%b %d')} ({dte}d)")
        except Exception:
            labels.append(e)
    return labels
