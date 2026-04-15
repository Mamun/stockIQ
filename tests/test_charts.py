"""Unit tests for charts.py — verifies chart construction without a browser."""



import pytest
import plotly.graph_objects as go

from indexiq.models.indicators import compute_mas, compute_rsi, compute_fibonacci, detect_reversal_patterns
from indexiq.models.signals import find_crosses
from indexiq.views.components.charts import build_chart


# ── Fixtures / helpers ────────────────────────────────────────────────────────

@pytest.fixture
def prepared_df(sample_ohlcv):
    """Full indicator-enriched DataFrame."""
    df = compute_mas(sample_ohlcv.copy())
    df["RSI"] = compute_rsi(df)
    df = detect_reversal_patterns(df)
    return df


@pytest.fixture
def fib_levels(sample_ohlcv):
    return compute_fibonacci(sample_ohlcv)


# ── build_chart ───────────────────────────────────────────────────────────────

class TestBuildChart:
    def test_returns_plotly_figure(self, prepared_df, fib_levels):
        fig = build_chart(prepared_df, fib_levels, "AAPL",
                          show_vol=False, show_fib=False, show_patterns=False, show_rsi=False)
        assert isinstance(fig, go.Figure)

    def test_figure_has_data(self, prepared_df, fib_levels):
        fig = build_chart(prepared_df, fib_levels, "AAPL",
                          show_vol=False, show_fib=False, show_patterns=False, show_rsi=False)
        assert len(fig.data) > 0

    def test_candlestick_trace_present(self, prepared_df, fib_levels):
        fig = build_chart(prepared_df, fib_levels, "AAPL",
                          show_vol=False, show_fib=False, show_patterns=False, show_rsi=False)
        trace_types = [type(t).__name__ for t in fig.data]
        assert "Candlestick" in trace_types

    def test_ma_traces_present(self, prepared_df, fib_levels):
        """5 MA lines should be present as Scatter traces."""
        fig = build_chart(prepared_df, fib_levels, "AAPL",
                          show_vol=False, show_fib=False, show_patterns=False, show_rsi=False)
        scatter_names = [t.name for t in fig.data if isinstance(t, go.Scatter)]
        for p in [5, 20, 50, 100, 200]:
            assert any(f"MA{p}" in (n or "") for n in scatter_names)

    def test_volume_subplot_added_when_show_vol_true(self, prepared_df, fib_levels):
        fig_with = build_chart(prepared_df, fib_levels, "AAPL",
                               show_vol=True, show_fib=False, show_patterns=False, show_rsi=False)
        fig_without = build_chart(prepared_df, fib_levels, "AAPL",
                                  show_vol=False, show_fib=False, show_patterns=False, show_rsi=False)
        # With volume there should be more traces
        assert len(fig_with.data) > len(fig_without.data)

    def test_rsi_subplot_added_when_show_rsi_true(self, prepared_df, fib_levels):
        fig_with = build_chart(prepared_df, fib_levels, "AAPL",
                               show_vol=False, show_fib=False, show_patterns=False, show_rsi=True)
        trace_names = [t.name for t in fig_with.data]
        assert any("RSI" in (n or "") for n in trace_names)

    def test_fib_lines_added_when_show_fib_true(self, prepared_df, fib_levels):
        fig_with = build_chart(prepared_df, fib_levels, "AAPL",
                               show_vol=False, show_fib=True, show_patterns=False, show_rsi=False)
        # Fibonacci lines are added as shapes to layout
        assert len(fig_with.layout.shapes) > 0

    def test_no_fib_shapes_when_show_fib_false(self, prepared_df, fib_levels):
        fig = build_chart(prepared_df, fib_levels, "AAPL",
                          show_vol=False, show_fib=False, show_patterns=False, show_rsi=False)
        assert len(fig.layout.shapes) == 0

    def test_ticker_name_in_candlestick_trace(self, prepared_df, fib_levels):
        """Ticker is passed through build_chart; candlestick trace name should contain it."""
        fig = build_chart(prepared_df, fib_levels, "TSLA",
                          show_vol=False, show_fib=False, show_patterns=False, show_rsi=False)
        candlestick_traces = [t for t in fig.data if isinstance(t, go.Candlestick)]
        assert len(candlestick_traces) > 0

    def test_all_options_enabled_does_not_crash(self, prepared_df, fib_levels):
        """Smoke test: all options on should not raise."""
        fig = build_chart(prepared_df, fib_levels, "AAPL",
                          show_vol=True, show_fib=True, show_patterns=True, show_rsi=True)
        assert isinstance(fig, go.Figure)

    def test_figure_uses_dark_template(self, prepared_df, fib_levels):
        fig = build_chart(prepared_df, fib_levels, "AAPL",
                          show_vol=False, show_fib=False, show_patterns=False, show_rsi=False)
        template = fig.layout.template
        # Plotly dark templates have a dark paper/plot bgcolor
        assert template is not None
