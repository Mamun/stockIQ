"""Unit tests for signals.py"""



import numpy as np
import pandas as pd
import pytest

from indexiq.models.signals import signal_score, overall_signal, find_crosses
from indexiq.models.indicators import compute_mas, compute_rsi


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_row(**kwargs) -> pd.Series:
    """Build a minimal row Series for signal_score."""
    defaults = {
        "Close": 100.0,
        "MA5": np.nan, "MA20": np.nan, "MA50": np.nan, "MA100": np.nan, "MA200": np.nan,
        "MA200W": np.nan, "RSI": np.nan,
    }
    defaults.update(kwargs)
    return pd.Series(defaults)


# ── signal_score ──────────────────────────────────────────────────────────────

class TestSignalScore:
    def test_returns_tuple_of_int_and_list(self):
        row = _make_row()
        prev = _make_row()
        score, reasons = signal_score(row, prev)
        assert isinstance(score, int)
        assert isinstance(reasons, list)

    # Use a complete row where Close is above all 5 MAs and MAs are spread out
    # so no component interferes unexpectedly.
    _BULL_ROW  = dict(Close=200, MA5=195, MA20=190, MA50=170, MA100=150, MA200=120)
    _BEAR_ROW  = dict(Close=50,  MA5=80,  MA20=90,  MA50=100, MA100=110, MA200=120)
    _PREV_BULL = dict(MA50=165, MA200=120)   # MA50 still above MA200 (no cross)
    _PREV_BEAR = dict(MA50=115, MA200=120)   # MA50 still below MA200 (no cross)

    def test_all_mas_above_adds_two(self):
        """Price above all 5 MAs → +2 from component 1."""
        row  = _make_row(**self._BULL_ROW)
        prev = _make_row(**self._PREV_BULL)
        score, _ = signal_score(row, prev)
        assert score >= 2

    def test_all_mas_below_subtracts_two(self):
        """Price below all 5 MAs → -2 from component 1."""
        row  = _make_row(**self._BEAR_ROW)
        prev = _make_row(**self._PREV_BEAR)
        score, _ = signal_score(row, prev)
        assert score <= -2

    def test_golden_cross_adds_two(self):
        """MA50 crosses above MA200 → +2 for that component."""
        row  = _make_row(**self._BULL_ROW)                      # MA50=170 > MA200=120 now
        prev = _make_row(MA50=110.0, MA200=120.0)               # MA50 < MA200 before → cross
        score, reasons = signal_score(row, prev)
        assert any("Golden Cross" in r for r in reasons)
        # Cross (+2) + all above (+2) + MA5>MA20 (+1) = ≥ 5
        assert score >= 4

    def test_death_cross_subtracts_two(self):
        """MA50 crosses below MA200 → -2 for that component."""
        row  = _make_row(**self._BEAR_ROW)                      # MA50=100 < MA200=120 now
        prev = _make_row(MA50=130.0, MA200=120.0)               # MA50 > MA200 before → cross
        score, reasons = signal_score(row, prev)
        assert any("Death Cross" in r for r in reasons)
        assert score <= -4

    def test_ma50_above_ma200_no_cross_adds_one(self):
        """MA50 > MA200 without crossover → +1 (sustained bull trend)."""
        row  = _make_row(**self._BULL_ROW)
        prev = _make_row(**self._PREV_BULL)   # MA50 was already above MA200
        score, reasons = signal_score(row, prev)
        assert any("MA50 above MA200" in r for r in reasons)
        assert score >= 1

    def test_ma5_above_ma20_increases_score(self):
        """MA5 > MA20 contributes +1 vs MA5 < MA20."""
        base = dict(Close=200, MA50=170, MA100=150, MA200=120)
        prev = _make_row(**self._PREV_BULL)
        row_above = _make_row(**base, MA5=195, MA20=190)
        row_below = _make_row(**base, MA5=185, MA20=190)
        s_above, _ = signal_score(row_above, prev)
        s_below, _ = signal_score(row_below, prev)
        assert s_above > s_below

    def test_ma5_below_ma20_decreases_score(self):
        """MA5 < MA20 contributes -1 vs MA5 > MA20."""
        base = dict(Close=200, MA50=170, MA100=150, MA200=120)
        prev = _make_row(**self._PREV_BULL)
        row_above = _make_row(**base, MA5=195, MA20=190)
        row_below = _make_row(**base, MA5=185, MA20=190)
        _, reasons_below = signal_score(row_below, prev)
        assert any("short-term momentum negative" in r for r in reasons_below)

    def test_above_ma200w_adds_two(self):
        """Price > MA200W → +2."""
        row  = _make_row(**self._BULL_ROW, MA200W=100)
        prev = _make_row(**self._PREV_BULL)
        score, reasons = signal_score(row, prev)
        assert any("200-week" in r for r in reasons)
        assert score >= 4

    def test_below_ma200w_subtracts_two(self):
        """Price < MA200W → -2."""
        row  = _make_row(**self._BEAR_ROW, MA200W=200)
        prev = _make_row(**self._PREV_BEAR)
        score, reasons = signal_score(row, prev)
        assert any("200-week" in r for r in reasons)
        assert score <= -4

    def test_rsi_overbought_lowers_score(self):
        """RSI >= 70 reduces score by 1 vs neutral RSI."""
        row_ob  = _make_row(**self._BULL_ROW, RSI=75)
        row_neu = _make_row(**self._BULL_ROW, RSI=50)
        prev = _make_row(**self._PREV_BULL)
        s_ob,  reasons_ob  = signal_score(row_ob,  prev)
        s_neu, _           = signal_score(row_neu, prev)
        assert s_ob < s_neu
        assert any("overbought" in r for r in reasons_ob)

    def test_rsi_oversold_raises_score(self):
        """RSI <= 30 increases score by 1 vs neutral RSI."""
        row_os  = _make_row(**self._BULL_ROW, RSI=25)
        row_neu = _make_row(**self._BULL_ROW, RSI=50)
        prev = _make_row(**self._PREV_BULL)
        s_os, reasons_os = signal_score(row_os,  prev)
        s_neu, _         = signal_score(row_neu, prev)
        assert s_os > s_neu
        assert any("oversold" in r for r in reasons_os)

    def test_rsi_neutral_adds_reason(self):
        """RSI 30–70 → reason added, no score change vs no RSI."""
        row_rsi = _make_row(**self._BULL_ROW, RSI=50)
        row_nan = _make_row(**self._BULL_ROW)
        prev = _make_row(**self._PREV_BULL)
        s_rsi, reasons = signal_score(row_rsi, prev)
        s_nan, _       = signal_score(row_nan, prev)
        assert s_rsi == s_nan
        assert any("neutral" in r.lower() for r in reasons)

    def test_all_nan_mas_treated_as_bearish(self):
        """With all NaN MAs, price is counted as below all 5 → -2 from component 1."""
        row  = _make_row()
        prev = _make_row()
        score, _ = signal_score(row, prev)
        assert score == -2

    def test_strong_bull_scenario_score_at_least_4(self):
        """Full bull setup: all MAs above + golden cross + MA200W above + RSI oversold."""
        row = _make_row(
            Close=200,
            MA5=190, MA20=185, MA50=170, MA100=150, MA200=120,
            MA200W=100, RSI=28,
        )
        prev = _make_row(MA50=115, MA200=120)  # golden cross
        score, _ = signal_score(row, prev)
        assert score >= 4

    def test_strong_bear_scenario_score_at_most_minus_4(self):
        """Full bear setup: all MAs below + death cross + MA200W below + RSI overbought."""
        row = _make_row(
            Close=50,
            MA5=80, MA20=90, MA50=100, MA100=110, MA200=120,
            MA200W=130, RSI=75,
        )
        prev = _make_row(MA50=125, MA200=120)  # death cross
        score, _ = signal_score(row, prev)
        assert score <= -4


# ── overall_signal ────────────────────────────────────────────────────────────

class TestOverallSignal:
    @pytest.mark.parametrize("score,expected_label", [
        (4,  "STRONG BUY"),
        (5,  "STRONG BUY"),
        (10, "STRONG BUY"),
        (2,  "BUY"),
        (3,  "BUY"),
        (0,  "NEUTRAL"),
        (1,  "NEUTRAL"),
        (-1, "SELL"),
        (-2, "SELL"),
        (-3, "STRONG SELL"),
        (-10, "STRONG SELL"),
    ])
    def test_label_mapping(self, score, expected_label):
        label, _ = overall_signal(score)
        assert label == expected_label

    @pytest.mark.parametrize("score", [4, 2, 0, -2, -3])
    def test_returns_css_color(self, score):
        _, color = overall_signal(score)
        assert color.startswith("#")
        assert len(color) == 7  # #RRGGBB

    def test_strong_buy_has_green_color(self):
        _, color = overall_signal(4)
        # Green-ish colors in hex
        assert color in ("#16A34A", "#22C55E")

    def test_strong_sell_has_red_color(self):
        _, color = overall_signal(-3)
        assert color == "#DC2626"

    def test_returns_tuple_of_two_strings(self):
        result = overall_signal(0)
        assert len(result) == 2
        assert all(isinstance(x, str) for x in result)


# ── find_crosses ──────────────────────────────────────────────────────────────

class TestFindCrosses:
    def test_returns_tuple_of_two_datetime_indexes(self, sample_ohlcv):
        df = compute_mas(sample_ohlcv.copy())
        golden, death = find_crosses(df)
        assert isinstance(golden, pd.DatetimeIndex)
        assert isinstance(death, pd.DatetimeIndex)

    def test_no_crosses_in_strong_uptrend(self, trending_up_ohlcv):
        """In a strong uptrend, MA50 stays above MA200 → no death crosses."""
        df = compute_mas(trending_up_ohlcv.copy())
        _, death = find_crosses(df)
        assert len(death) == 0

    def test_no_crosses_in_strong_downtrend(self, trending_down_ohlcv):
        """In a strong downtrend, MA50 stays below MA200 → no golden crosses."""
        df = compute_mas(trending_down_ohlcv.copy())
        golden, _ = find_crosses(df)
        assert len(golden) == 0

    def test_golden_cross_detected(self):
        """A step from 100 → 200 forces MA50 to cross above MA200."""
        # 300 bars: 200 flat at 100, then 100 flat at 200
        # MA200 is valid from bar 200. At bar 200 both MAs = 100.
        # At bar 201 MA50 jumps toward 200; MA200 moves slowly → golden cross.
        n = 300
        dates = pd.bdate_range(end="2024-12-31", periods=n)
        close = np.concatenate([np.full(200, 100.0), np.full(100, 200.0)])
        df = pd.DataFrame(
            {"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": [1e6] * n},
            index=dates,
        )
        df = compute_mas(df)
        golden, _ = find_crosses(df)
        assert len(golden) >= 1

    def test_empty_df_returns_empty_indexes(self):
        df = pd.DataFrame({"MA50": pd.Series(dtype=float), "MA200": pd.Series(dtype=float)})
        golden, death = find_crosses(df)
        assert len(golden) == 0
        assert len(death) == 0

    def test_not_both_golden_and_death_on_same_date(self, sample_ohlcv):
        """A single date cannot be both a golden and a death cross."""
        df = compute_mas(sample_ohlcv.copy())
        golden, death = find_crosses(df)
        overlap = golden.intersection(death)
        assert len(overlap) == 0
