"""Forward P/E value-growth screener for SPX_TICKERS."""

from ._shared import (
    ttl_cache, CACHE_TTL, SPX_TICKERS,
    pd, datetime, timedelta,
    get_metadata, get_forward_pe, _batch_download, _rsi_last,
)


@ttl_cache(CACHE_TTL["fetch_spx_forward_pe_scan"])
def fetch_spx_forward_pe_scan() -> pd.DataFrame:
    """
    Forward P/E value-growth screener for SPX_TICKERS.

    Per ticker:
      • Forward P/E vs sector median (discount = higher score)
      • EPS growth % YoY
      • PEG ratio
      • Revenue growth %
      • RSI-14
      • Value Growth Score (0–100)

    Prices downloaded in one batch; forward P/E data from local cache —
    no per-ticker .info calls needed.
    """
    fpe_cache  = get_forward_pe()
    meta_cache = get_metadata()

    end_dt   = datetime.today()
    start_dt = end_dt - timedelta(days=60)

    raw = _batch_download(
        SPX_TICKERS,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
    )

    def _get_close(ticker: str) -> pd.DataFrame:
        try:
            df = raw[ticker].copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df.dropna(subset=["Close"])
        except Exception:
            return pd.DataFrame()

    rows = []
    for ticker in SPX_TICKERS:
        fpe = fpe_cache.get(ticker, {})
        forward_pe = fpe.get("forwardPE")
        if not forward_pe or forward_pe <= 0:
            continue

        df = _get_close(ticker)
        if df.empty:
            continue

        meta         = meta_cache.get(ticker, {})
        company_name = meta.get("name", ticker) if meta else ticker
        sector       = meta.get("sector", "—") if meta else "—"
        last_price   = float(df["Close"].iloc[-1])
        rsi          = round(_rsi_last(df), 1) if len(df) >= 15 else None

        earnings_growth = fpe.get("earningsGrowth")
        revenue_growth  = fpe.get("revenueGrowth")
        trailing_pe     = fpe.get("trailingPE")
        peg_ratio       = fpe.get("pegRatio")
        forward_eps     = fpe.get("forwardEps")

        rows.append({
            "Ticker":       ticker,
            "Company":      company_name,
            "Sector":       sector,
            "Price":        round(last_price, 2),
            "Fwd P/E":      round(forward_pe, 1),
            "Trail P/E":    round(trailing_pe, 1) if trailing_pe and trailing_pe > 0 else None,
            "Fwd EPS":      round(forward_eps, 2) if forward_eps else None,
            "EPS Gr %":     round(earnings_growth * 100, 1) if earnings_growth is not None else None,
            "Rev Gr %":     round(revenue_growth * 100, 1) if revenue_growth is not None else None,
            "PEG":          round(peg_ratio, 2) if peg_ratio and peg_ratio > 0 else None,
            "RSI":          rsi,
        })

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)

    # Sector median forward P/E — used for relative discount scoring
    sector_med = out.groupby("Sector")["Fwd P/E"].median().to_dict()
    out["Sector Med P/E"] = out["Sector"].map(sector_med).round(1)

    def _score(row) -> float:
        score = 0.0

        # P/E discount vs sector (up to 40 pts)
        med = sector_med.get(row["Sector"])
        if med and med > 0 and row["Fwd P/E"] > 0:
            discount = (med - row["Fwd P/E"]) / med
            score += max(0.0, min(40.0, discount * 40))

        # EPS growth (up to 30 pts)
        if row["EPS Gr %"] is not None:
            score += max(0.0, min(30.0, row["EPS Gr %"] * 0.5))

        # PEG bonus (up to 20 pts)
        peg = row["PEG"]
        if peg and peg > 0:
            score += 20 if peg < 1 else (10 if peg < 2 else 0)

        # RSI entry check
        rsi = row["RSI"]
        if rsi is not None:
            score += 5 if rsi < 50 else (-5 if rsi > 70 else 0)

        return round(score, 1)

    out["VG Score"] = out.apply(_score, axis=1)

    return (
        out.sort_values("VG Score", ascending=False)
        .reset_index(drop=True)
    )
