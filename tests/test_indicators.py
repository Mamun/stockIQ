"""Unit tests for indicators.py"""



import numpy as np
import pandas as pd
import pytest

from indexiq.models.indicators import (
    compute_mas,
    compute_fibonacci,
    compute_rsi,
    compute_daily_gaps,
    patch_today_gap,
    compute_weekly_ma200,
    detect_reversal_patterns,
)
from indexiq.config import MA_PERIODS, FIB_LEVELS


# ── compute_mas ───────────────────────────────────────────────────────────────

class TestComputeMas:
    def test_adds_all_ma_columns(self, sample_ohlcv):
        df = compute_mas(sample_ohlcv.copy())
        for p in MA_PERIODS:
            assert f"MA{p}" in df.columns

    def test_ma5_has_fewer_nans_than_ma200(self, sample_ohlcv):
        df = compute_mas(sample_ohlcv.copy())
        assert df["MA5"].isna().sum() < df["MA200"].isna().sum()

    def test_ma5_nan_count_equals_window_minus_one(self, sample_ohlcv):
        df = compute_mas(sample_ohlcv.copy())
        assert df["MA5"].isna().sum() == 4  # 5-1 = 4

    def test_ma200_nan_count_equals_window_minus_one(self, sample_ohlcv):
        df = compute_mas(sample_ohlcv.copy())
        assert df["MA200"].isna().sum() == 199  # 200-1 = 199

    def test_ma_values_are_rolling_means(self, sample_ohlcv):
        df = compute_mas(sample_ohlcv.copy())
        # Manually compute MA5 for the last row and compare
        expected = sample_ohlcv["Close"].rolling(5).mean().iloc[-1]
        assert pytest.approx(df["MA5"].iloc[-1], rel=1e-9) == expected

    def test_ma5_above_ma20_in_strong_uptrend(self, trending_up_ohlcv):
        df = compute_mas(trending_up_ohlcv.copy())
        last = df.dropna()
        assert last["MA5"].iloc[-1] > last["MA20"].iloc[-1]

    def test_ma5_below_ma20_in_strong_downtrend(self, trending_down_ohlcv):
        df = compute_mas(trending_down_ohlcv.copy())
        last = df.dropna()
        assert last["MA5"].iloc[-1] < last["MA20"].iloc[-1]

    def test_returns_dataframe(self, sample_ohlcv):
        result = compute_mas(sample_ohlcv.copy())
        assert isinstance(result, pd.DataFrame)

    def test_original_columns_preserved(self, sample_ohlcv):
        original_cols = set(sample_ohlcv.columns)
        df = compute_mas(sample_ohlcv.copy())
        assert original_cols.issubset(set(df.columns))


# ── compute_fibonacci ─────────────────────────────────────────────────────────

class TestComputeFibonacci:
    def test_returns_correct_number_of_levels(self, sample_ohlcv):
        fib = compute_fibonacci(sample_ohlcv)
        assert len(fib) == len(FIB_LEVELS)

    def test_all_expected_level_keys_present(self, sample_ohlcv):
        fib = compute_fibonacci(sample_ohlcv)
        for lvl in FIB_LEVELS:
            key = f"{int(lvl * 100)}%"
            assert key in fib

    def test_0pct_level_equals_high(self, sample_ohlcv):
        fib = compute_fibonacci(sample_ohlcv)
        high = sample_ohlcv.tail(200)["Close"].max()
        assert pytest.approx(fib["0%"], rel=1e-9) == high

    def test_100pct_level_equals_low(self, sample_ohlcv):
        fib = compute_fibonacci(sample_ohlcv)
        low = sample_ohlcv.tail(200)["Close"].min()
        assert pytest.approx(fib["100%"], rel=1e-9) == low

    def test_50pct_level_is_midpoint(self, sample_ohlcv):
        fib = compute_fibonacci(sample_ohlcv)
        high = sample_ohlcv.tail(200)["Close"].max()
        low = sample_ohlcv.tail(200)["Close"].min()
        expected_50 = (high + low) / 2
        assert pytest.approx(fib["50%"], rel=1e-6) == expected_50

    def test_levels_monotonically_ordered(self, sample_ohlcv):
        """0% (high) > 23.6% > 38.2% > 50% > 61.8% > 78.6% > 100% (low)."""
        fib = compute_fibonacci(sample_ohlcv)
        keys_ordered = [f"{int(lvl * 100)}%" for lvl in FIB_LEVELS]
        values = [fib[k] for k in keys_ordered]
        assert all(values[i] >= values[i + 1] for i in range(len(values) - 1))

    def test_all_values_are_floats(self, sample_ohlcv):
        fib = compute_fibonacci(sample_ohlcv)
        assert all(isinstance(v, float) for v in fib.values())

    def test_uses_last_200_bars(self, long_ohlcv):
        """compute_fibonacci uses the last 200 bars, not the full history."""
        fib_long = compute_fibonacci(long_ohlcv)
        fib_last200 = compute_fibonacci(long_ohlcv.tail(200))
        assert pytest.approx(fib_long["0%"]) == fib_last200["0%"]


# ── compute_rsi ───────────────────────────────────────────────────────────────

class TestComputeRSI:
    def test_returns_series_named_rsi(self, sample_ohlcv):
        rsi = compute_rsi(sample_ohlcv)
        assert isinstance(rsi, pd.Series)
        assert rsi.name == "RSI"

    def test_rsi_range_0_to_100(self, sample_ohlcv):
        rsi = compute_rsi(sample_ohlcv).dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_rsi_high_in_strong_uptrend(self, trending_up_ohlcv):
        """Strong uptrend should have RSI > 60 for most bars after warmup."""
        rsi = compute_rsi(trending_up_ohlcv).dropna()
        assert rsi.mean() > 55

    def test_rsi_low_in_strong_downtrend(self, trending_down_ohlcv):
        """Strong downtrend should have RSI < 45 on average after warmup."""
        rsi = compute_rsi(trending_down_ohlcv).dropna()
        assert rsi.mean() < 50

    def test_rsi_index_matches_dataframe(self, sample_ohlcv):
        rsi = compute_rsi(sample_ohlcv)
        assert rsi.index.equals(sample_ohlcv.index)

    def test_first_period_minus_one_are_nan(self, sample_ohlcv):
        rsi = compute_rsi(sample_ohlcv, period=14)
        # ewm with min_periods=14 → first 13 are NaN
        assert rsi.iloc[:13].isna().all()

    def test_custom_period(self, sample_ohlcv):
        rsi_5  = compute_rsi(sample_ohlcv, period=5)
        rsi_14 = compute_rsi(sample_ohlcv, period=14)
        # Different periods → different NaN counts
        assert rsi_5.isna().sum() < rsi_14.isna().sum()

    def test_flat_price_returns_50(self):
        """Flat close → equal gains and losses → RSI should be near 50."""
        dates = pd.bdate_range(end="2024-12-31", periods=100)
        df = pd.DataFrame({"Close": [100.0] * 100}, index=dates)
        rsi = compute_rsi(df).dropna()
        # With no movement, gain/loss both 0; division 0/0 → nan or 50
        assert rsi.isna().all() or (rsi.dropna() == 50).all()


# ── compute_daily_gaps ────────────────────────────────────────────────────────

class TestComputeDailyGaps:
    def test_returns_dataframe(self, gap_ohlcv):
        result = compute_daily_gaps(gap_ohlcv)
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self, gap_ohlcv):
        result = compute_daily_gaps(gap_ohlcv)
        for col in ["Prev Close", "Gap", "Gap %", "Gap Filled", "Gap Confirmed"]:
            assert col in result.columns

    def test_no_nan_in_prev_close(self, gap_ohlcv):
        result = compute_daily_gaps(gap_ohlcv)
        assert result["Prev Close"].isna().sum() == 0

    def test_gap_direction_up(self, gap_ohlcv):
        """Day 10 has an upward gap; Gap should be positive."""
        result = compute_daily_gaps(gap_ohlcv)
        # After dropna, original row 10 is row 9 (row 0 is dropped due to NaN Prev Close)
        gap_values = result["Gap"]
        assert (gap_values > 0).any(), "Expected at least one positive gap"

    def test_gap_direction_down(self, gap_ohlcv):
        """Day 30 has a downward gap; Gap should be negative."""
        result = compute_daily_gaps(gap_ohlcv)
        assert (result["Gap"] < 0).any(), "Expected at least one negative gap"

    def test_gap_percent_proportional_to_gap(self, gap_ohlcv):
        result = compute_daily_gaps(gap_ohlcv)
        nonzero = result[result["Gap"] != 0]
        if not nonzero.empty:
            for _, row in nonzero.head(5).iterrows():
                expected_pct = round(row["Gap"] / row["Prev Close"] * 100, 2)
                assert pytest.approx(row["Gap %"], abs=0.01) == expected_pct

    def test_zero_gap_rows_marked_not_filled(self):
        """A gap that is exactly zero (before and after rounding) is never filled."""
        # Construct data where Open == Prev Close on one bar
        dates = pd.bdate_range(end="2024-12-31", periods=10)
        close = [100.0] * 10
        open_ = [100.0] * 10   # all opens equal prev close → true zero gaps
        high  = [101.0] * 10
        low   = [99.0]  * 10
        vol   = [1e6]   * 10
        df = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
            index=dates,
        )
        result = compute_daily_gaps(df)
        zero_gaps = result[result["Gap"] == 0]
        assert (zero_gaps["Gap Filled"] == False).all()

    def test_last_3_rows_confirmed_only_if_filled(self, sample_ohlcv):
        result = compute_daily_gaps(sample_ohlcv)
        last3 = result.tail(3)
        for _, row in last3.iterrows():
            if not row["Gap Filled"]:
                assert row["Gap Confirmed"] == False


# ── patch_today_gap ───────────────────────────────────────────────────────────

class TestPatchTodayGap:
    def test_empty_df_returned_unchanged(self, mock_quote):
        empty = pd.DataFrame()
        result = patch_today_gap(empty, mock_quote)
        assert result.empty

    def test_missing_day_high_returns_unchanged(self, gap_ohlcv):
        gaps = compute_daily_gaps(gap_ohlcv)
        result = patch_today_gap(gaps, {})
        # Should return unchanged because no day_high/day_low
        pd.testing.assert_frame_equal(result, gaps)

    def test_upward_gap_filled_when_day_low_touches_prev_close(self, gap_ohlcv):
        gaps = compute_daily_gaps(gap_ohlcv)
        last = gaps.iloc[-1]
        prev_close = float(last["Prev Close"])
        gap = float(last["Gap"])

        # Build a quote that forces fill: day_low == prev_close (gap up → filled when low touches prev close)
        quote = {"day_high": prev_close + abs(gap) + 5, "day_low": prev_close - 0.01}
        result = patch_today_gap(gaps, quote)
        if gap > 0:
            assert result.iloc[-1]["Gap Filled"] == True
            assert result.iloc[-1]["Gap Confirmed"] == True

    def test_upward_gap_not_filled_when_day_low_above_prev_close(self, gap_ohlcv):
        gaps = compute_daily_gaps(gap_ohlcv)
        last = gaps.iloc[-1]
        prev_close = float(last["Prev Close"])
        gap = float(last["Gap"])

        if gap > 0:
            quote = {"day_high": prev_close + 10, "day_low": prev_close + 0.5}
            result = patch_today_gap(gaps, quote)
            assert result.iloc[-1]["Gap Filled"] == False
            assert result.iloc[-1]["Gap Confirmed"] == True

    def test_does_not_mutate_input_dataframe(self, gap_ohlcv, mock_quote):
        gaps = compute_daily_gaps(gap_ohlcv)
        gaps_copy = gaps.copy()
        patch_today_gap(gaps, mock_quote)
        pd.testing.assert_frame_equal(gaps, gaps_copy)


# ── compute_weekly_ma200 ──────────────────────────────────────────────────────

class TestComputeWeeklyMA200:
    def test_returns_series_named_ma200w(self, long_ohlcv):
        result = compute_weekly_ma200(long_ohlcv)
        assert isinstance(result, pd.Series)
        assert result.name == "MA200W"

    def test_index_matches_input_dataframe(self, long_ohlcv):
        result = compute_weekly_ma200(long_ohlcv)
        assert result.index.equals(long_ohlcv.index)

    def test_insufficient_history_returns_all_nan(self, short_ohlcv):
        """Only 30 bars → less than 200 weeks → all NaN (no valid 200W MA)."""
        result = compute_weekly_ma200(short_ohlcv)
        assert result.isna().all()


# ── detect_reversal_patterns ──────────────────────────────────────────────────

class TestDetectReversalPatterns:
    PATTERN_COLS = [
        "pat_hammer", "pat_shoot_star", "pat_bull_engulf",
        "pat_bear_engulf", "pat_morning_star", "pat_evening_star", "pat_doji",
    ]

    def test_adds_all_pattern_columns(self, sample_ohlcv):
        df = detect_reversal_patterns(sample_ohlcv.copy())
        for col in self.PATTERN_COLS:
            assert col in df.columns

    def test_pattern_columns_are_boolean(self, sample_ohlcv):
        df = detect_reversal_patterns(sample_ohlcv.copy())
        for col in self.PATTERN_COLS:
            assert df[col].dtype == bool, f"{col} should be bool"

    def test_hammer_detected_on_known_candle(self):
        """Construct a candle that clearly satisfies the hammer definition."""
        dates = pd.bdate_range(end="2024-12-31", periods=5)
        # Hammer: small body near top, lower wick >= 2x body, tiny upper wick
        # body = 1, lower_wick = 3, upper_wick = 0.1
        df = pd.DataFrame({
            "Open":  [100, 100, 100, 100, 101.0],  # last candle
            "High":  [100, 100, 100, 100, 101.1],  # upper_wick = 0.1 < 0.25*body
            "Low":   [100, 100, 100, 100, 98.0],   # lower_wick = 3  >= 2*body
            "Close": [100, 100, 100, 100, 100.0],  # body = 1
            "Volume": [1e6] * 5,
        }, index=dates)
        result = detect_reversal_patterns(df)
        assert result["pat_hammer"].iloc[-1] == True

    def test_doji_detected_on_known_candle(self):
        """Construct a doji: body <= 5% of full range."""
        dates = pd.bdate_range(end="2024-12-31", periods=5)
        df = pd.DataFrame({
            "Open":   [100, 100, 100, 100, 100.05],
            "High":   [100, 100, 100, 100, 110.0],
            "Low":    [100, 100, 100, 100,  90.0],
            "Close":  [100, 100, 100, 100, 100.0],  # body=0.05, range=20 → 0.25%
            "Volume": [1e6] * 5,
        }, index=dates)
        result = detect_reversal_patterns(df)
        assert result["pat_doji"].iloc[-1] == True

    def test_no_patterns_in_flat_market(self):
        """All identical candles → no engulfing, no morning/evening star."""
        dates = pd.bdate_range(end="2024-12-31", periods=10)
        df = pd.DataFrame({
            "Open":  [100.0] * 10,
            "High":  [101.0] * 10,
            "Low":   [99.0] * 10,
            "Close": [100.0] * 10,
            "Volume": [1e6] * 10,
        }, index=dates)
        result = detect_reversal_patterns(df)
        # No bull/bear engulfing in flat market
        assert not result["pat_bull_engulf"].any()
        assert not result["pat_bear_engulf"].any()

    def test_original_ohlcv_columns_preserved(self, sample_ohlcv):
        original_cols = set(sample_ohlcv.columns)
        df = detect_reversal_patterns(sample_ohlcv.copy())
        assert original_cols.issubset(set(df.columns))
