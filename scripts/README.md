# GCS Cache Build Scripts

These scripts pre-populate Google Cloud Storage with slow-changing data so the
app never needs to call the Yahoo Finance `.info` API at runtime. Run them
manually whenever the underlying data needs refreshing.

## Prerequisites

- `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to your GCP service account JSON key
- `GCS_BUCKET` env var set to `stpicker` (or your bucket name)
- Run from the project root: `python3 scripts/<script>.py`

---

## Scripts

### `build_metadata_cache.py`
Uploads company name + sector for all 200 S&P 500 tickers.

**When to run:** Once, then again only if the S&P 500 constituent list changes
(roughly quarterly).

```bash
python3 scripts/build_metadata_cache.py
```

---

### `build_fundamentals_cache.py`
Uploads ROE, profit margins, revenue growth, debt/equity, and earnings growth
for all 200 S&P 500 tickers. Used by the Munger Strategy Scanner.

**When to run:** Once per quarter, after earnings season.

```bash
python3 scripts/build_fundamentals_cache.py
```

---

### `build_short_interest_cache.py`
Uploads short % of float, days-to-cover, shares short, and prior-month shares
short for all 200 S&P 500 tickers. Used by the Squeeze Scanner.

**When to run:** Once per month — FINRA publishes short interest data bi-monthly,
so monthly refreshes are sufficient.

```bash
python3 scripts/build_short_interest_cache.py
```

---

### `build_analyst_consensus_cache.py`
Uploads analyst recommendation mean, number of analysts, and price targets
(mean/high/low) for all 200 S&P 500 tickers. Used by the Strong Buy/Sell scanners.

**When to run:** Once per week — analyst ratings change infrequently.

```bash
python3 scripts/build_analyst_consensus_cache.py
```

---

## Refresh Schedule Summary

| Script                          | GCS path                          | Refresh cadence |
|---------------------------------|-----------------------------------|-----------------|
| `build_metadata_cache.py`       | `screener/ticker_metadata.json`   | Quarterly       |
| `build_fundamentals_cache.py`   | `screener/fundamentals.json`      | Quarterly       |
| `build_short_interest_cache.py` | `screener/short_interest.json`    | Monthly         |
| `build_analyst_consensus_cache.py` | `screener/analyst_consensus.json` | Weekly       |
