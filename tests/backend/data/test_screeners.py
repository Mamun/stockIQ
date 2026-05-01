"""Unit tests for screener scoring helpers in data/screeners.py.

All tests are pure-logic (no network calls). We test:
  - _quality_score()
  - _proximity_score()
And inline score logic for bounce, squeeze, strong-buy, strong-sell.
"""



import pytest
from stockiq.backend.data.screeners.spx_munger import _quality_score, _proximity_score


# ── _quality_score ────────────────────────────────────────────────────────────

class TestQualityScore:
    def test_returns_tuple_score_and_breakdown(self):
        result = _quality_score({})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], list)

    def test_empty_info_returns_zero(self):
        score, breakdown = _quality_score({})
        assert score == 0.0
        assert breakdown == []

    # ROE component (max 25)
    @pytest.mark.parametrize("roe, expected_pts", [
        (0.25, 25.0),   # 25% >= 20%
        (0.17, 18.0),   # 17% >= 15%
        (0.12, 10.0),   # 12% >= 10%
        (0.05,  5.0),   # 5% > 0%
        (-0.05, 0.0),   # negative
    ])
    def test_roe_tiers(self, roe, expected_pts):
        score, _ = _quality_score({"returnOnEquity": roe})
        assert score == expected_pts

    # Profit Margin component (max 20)
    @pytest.mark.parametrize("pm, expected_pts", [
        (0.25, 20.0),   # 25% >= 20%
        (0.15, 14.0),   # 15% >= 10%
        (0.07,  8.0),   # 7%  >= 5%
        (0.02,  3.0),   # 2%  > 0%
        (-0.1,  0.0),   # negative
    ])
    def test_profit_margin_tiers(self, pm, expected_pts):
        score, _ = _quality_score({"profitMargins": pm})
        assert score == expected_pts

    # Revenue Growth component (max 15)
    @pytest.mark.parametrize("rg, expected_pts", [
        (0.20, 15.0),   # 20% >= 15%
        (0.10, 10.0),   # 10% >= 8%
        (0.05,  6.0),   # 5%  >= 3%
        (0.01,  2.0),   # 1%  >= 0%
        (-0.05, 0.0),   # negative
    ])
    def test_revenue_growth_tiers(self, rg, expected_pts):
        score, _ = _quality_score({"revenueGrowth": rg})
        assert score == expected_pts

    # Debt/Equity component (max 15)
    # yfinance returns D/E as ratio * 100 (e.g. 25 means 0.25)
    @pytest.mark.parametrize("de_raw, expected_pts", [
        (25,  15.0),    # de_ratio = 0.25 < 0.3
        (60,  10.0),    # de_ratio = 0.60 < 0.7
        (100,  5.0),    # de_ratio = 1.00 < 1.5
        (200,  0.0),    # de_ratio = 2.00 >= 1.5
    ])
    def test_debt_to_equity_tiers(self, de_raw, expected_pts):
        score, _ = _quality_score({"debtToEquity": de_raw})
        assert score == expected_pts

    # EPS Growth component (max 10)
    @pytest.mark.parametrize("eg, expected_pts", [
        (0.20, 10.0),   # 20% >= 15%
        (0.10,  7.0),   # 10% >= 8%
        (0.05,  3.0),   # 5%  >= 0%
        (-0.05, 0.0),   # negative
    ])
    def test_eps_growth_tiers(self, eg, expected_pts):
        score, _ = _quality_score({"earningsGrowth": eg})
        assert score == expected_pts

    def test_max_score_with_perfect_fundamentals(self):
        """Best-case inputs → score = 85."""
        info = {
            "returnOnEquity":  0.30,    # 30% → 25 pts
            "profitMargins":   0.25,    # 25% → 20 pts
            "revenueGrowth":   0.20,    # 20% → 15 pts
            "debtToEquity":    20.0,    # 0.20 → 15 pts
            "earningsGrowth":  0.20,    # 20% → 10 pts
        }
        score, breakdown = _quality_score(info)
        assert score == 85.0
        assert len(breakdown) == 5

    def test_partial_info_scores_available_components(self):
        """Only ROE present → only ROE contributes."""
        score, breakdown = _quality_score({"returnOnEquity": 0.25})
        assert score == 25.0
        assert len(breakdown) == 1

    def test_breakdown_contains_component_labels(self):
        info = {
            "returnOnEquity": 0.20,
            "profitMargins":  0.20,
        }
        _, breakdown = _quality_score(info)
        assert any("ROE" in b for b in breakdown)
        assert any("Profit Margin" in b for b in breakdown)

    def test_score_never_exceeds_85(self):
        """Even with extreme values the score caps naturally at 85."""
        info = {
            "returnOnEquity":  10.0,
            "profitMargins":   10.0,
            "revenueGrowth":   10.0,
            "debtToEquity":     0.0,
            "earningsGrowth":  10.0,
        }
        score, _ = _quality_score(info)
        assert score <= 85.0

    def test_none_values_ignored(self):
        """None values in info dict should not raise."""
        info = {"returnOnEquity": None, "profitMargins": 0.15}
        score, _ = _quality_score(info)
        assert score == 14.0  # only profit margin contributes


# ── _proximity_score ──────────────────────────────────────────────────────────

class TestProximityScore:
    @pytest.mark.parametrize("dist_pct, expected", [
        (0.0,   15),
        (1.5,   15),  # <= 2%
        (2.0,   15),  # boundary: <= 2
        (2.1,   12),  # <= 5%
        (5.0,   12),  # boundary: <= 5
        (5.1,    8),  # <= 10%
        (10.0,   8),  # boundary: <= 10
        (10.1,   4),  # <= 15%
        (15.0,   4),  # boundary: <= 15
        (15.1,   2),  # <= 20%
        (20.0,   2),  # boundary: <= 20
        (20.1,   0),  # > 20%
        (50.0,   0),
    ])
    def test_positive_distances(self, dist_pct, expected):
        assert _proximity_score(dist_pct) == expected

    @pytest.mark.parametrize("dist_pct, expected", [
        (-1.0,  15),
        (-5.0,  12),
        (-10.0,  8),
        (-15.0,  4),
        (-20.0,  2),
        (-21.0,  0),
    ])
    def test_negative_distances_use_absolute_value(self, dist_pct, expected):
        """Proximity score uses abs(dist_pct) so negative distances work identically."""
        assert _proximity_score(dist_pct) == expected

    def test_returns_int(self):
        assert isinstance(_proximity_score(5.0), int)

    def test_maximum_score_at_zero_distance(self):
        assert _proximity_score(0.0) == 15

    def test_zero_score_beyond_20_pct(self):
        assert _proximity_score(25.0) == 0
        assert _proximity_score(100.0) == 0


# ── Signal-tier mapping integration ──────────────────────────────────────────

class TestScreenerSignalTiers:
    """Verify the 5-tier signal logic used in fetch_spx_recommendations."""

    @staticmethod
    def _classify(weeks_green: int, months_green: int) -> str:
        """Inline replica of the signal classification from screeners.py."""
        if weeks_green == 4 and months_green == 4:
            return "Strong Buy"
        elif weeks_green == 4 and months_green >= 3:
            return "Buy"
        elif weeks_green >= 3 and months_green >= 3:
            return "Accumulate"
        elif weeks_green >= 2:
            return "Caution"
        else:
            return "Sell"

    @pytest.mark.parametrize("wg, mg, expected", [
        (4, 4, "Strong Buy"),
        (4, 3, "Buy"),
        (4, 2, "Caution"),   # weeks=4 but months < 3
        (3, 3, "Accumulate"),
        (3, 4, "Accumulate"),
        (2, 1, "Caution"),
        (1, 4, "Sell"),
        (0, 0, "Sell"),
    ])
    def test_signal_tiers(self, wg, mg, expected):
        assert self._classify(wg, mg) == expected
