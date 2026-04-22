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
) -> pd.DataFrame:
    """
    Dealer Gamma Exposure (GEX) by strike using Black-Scholes gamma.
    Positive GEX = dealers long gamma (stabilising — they buy dips, sell rips).
    Negative GEX = dealers short gamma (amplifying — moves accelerate).
    Returns DataFrame: strike, gex (in dollars).
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
        valid = (sigma > 0.001) & (oi > 0) & (K > 0)
        if not valid.any():
            return pd.DataFrame(columns=["strike", "gex"])
        K, sigma, oi, strikes = K[valid], sigma[valid], oi[valid], K[valid]
        d1    = (np.log(current_price / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        gamma = np.exp(-0.5 * d1**2) / (np.sqrt(2 * np.pi) * current_price * sigma * np.sqrt(T))
        gex   = sign * gamma * oi * 100 * current_price**2
        return pd.DataFrame({"strike": strikes, "gex": gex})

    combined = (
        pd.concat([_gex_series(calls, +1), _gex_series(puts, -1)])
        .groupby("strike", as_index=False)["gex"].sum()
        .sort_values("strike")
        .reset_index(drop=True)
    )
    return combined


def compute_expected_move(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    current_price: float,
) -> dict | None:
    """
    Expected move from ATM straddle price (call mid + put mid at nearest strike).
    Represents 1-sigma implied range by expiration (~68% probability).
    Returns {'move', 'pct', 'atm_strike', 'low', 'high'} or None.
    """
    def _mid(df: pd.DataFrame, strike: float) -> float:
        row = df[df["strike"] == strike]
        if row.empty:
            return 0.0
        bid  = float(row["bid"].iloc[0])  if "bid"       in row.columns else 0.0
        ask  = float(row["ask"].iloc[0])  if "ask"       in row.columns else 0.0
        last = float(row["lastPrice"].iloc[0]) if "lastPrice" in row.columns else 0.0
        return (bid + ask) / 2 if bid > 0 and ask > 0 else last

    strikes = calls["strike"].values
    if len(strikes) == 0:
        return None
    atm = float(strikes[np.argmin(np.abs(strikes - current_price))])
    em  = _mid(calls, atm) + _mid(puts, atm)
    if em <= 0:
        return None
    return {
        "move":       round(em, 2),
        "pct":        round(em / current_price * 100, 2),
        "atm_strike": atm,
        "low":        round(current_price - em, 2),
        "high":       round(current_price + em, 2),
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
