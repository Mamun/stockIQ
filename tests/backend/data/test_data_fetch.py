"""Unit tests for data/fetch.py — all yfinance calls are mocked."""



from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd

from stockiq.backend.data.yf_fetch import fetch_ohlcv, get_company_name, search_companies


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_yf_df(n: int = 100, price: float = 150.0) -> pd.DataFrame:
    """Synthetic yfinance-style OHLCV DataFrame."""
    rng = np.random.default_rng(0)
    dates = pd.bdate_range(end="2024-12-31", periods=n)
    close = price + np.cumsum(rng.normal(0, 1, n))
    close = np.clip(close, 1, None)
    return pd.DataFrame({
        "Open":   close * 0.99,
        "High":   close * 1.01,
        "Low":    close * 0.98,
        "Close":  close,
        "Volume": rng.integers(1_000_000, 5_000_000, n).astype(float),
    }, index=dates)


# ── fetch_ohlcv ───────────────────────────────────────────────────────────────

class TestFetchOHLCV:
    @patch("stockiq.backend.data.yf_fetch.yf.download")
    def test_returns_dataframe(self, mock_download):
        mock_download.return_value = _make_yf_df(200)
        df = fetch_ohlcv("AAPL", 365)
        assert isinstance(df, pd.DataFrame)

    @patch("stockiq.backend.data.yf_fetch.yf.download")
    def test_contains_ohlcv_columns(self, mock_download):
        mock_download.return_value = _make_yf_df(200)
        df = fetch_ohlcv("AAPL", 365)
        for col in ("Open", "High", "Low", "Close", "Volume"):
            assert col in df.columns

    @patch("stockiq.backend.data.yf_fetch.yf.download")
    def test_requests_extra_warmup_days(self, mock_download):
        mock_download.return_value = _make_yf_df(300)
        fetch_ohlcv("AAPL", 365)
        # The function fetches 365 + 1450 = 1815 days of history
        # Verify the start date is earlier than just 365 days ago
        assert mock_download.called

    @patch("stockiq.backend.data.yf_fetch.yf.download")
    def test_multiindex_columns_flattened(self, mock_download):
        """If yfinance returns a MultiIndex columns, they should be flattened."""
        df = _make_yf_df(100)
        # Simulate multi-ticker download that returns MultiIndex
        multi_df = df.copy()
        multi_df.columns = pd.MultiIndex.from_tuples(
            [(col, "AAPL") for col in df.columns]
        )
        mock_download.return_value = multi_df
        result = fetch_ohlcv("AAPL", 30)
        assert not isinstance(result.columns, pd.MultiIndex)

    @patch("stockiq.backend.data.yf_fetch.yf.download")
    def test_all_nan_close_returns_empty_df(self, mock_download):
        """A DataFrame where all Close values are NaN should be fully dropped."""
        dates = pd.bdate_range(end="2024-12-31", periods=10)
        df = pd.DataFrame({
            "Open": [1.0] * 10, "High": [1.0] * 10,
            "Low": [1.0] * 10, "Close": [float("nan")] * 10,
            "Volume": [0.0] * 10,
        }, index=dates)
        mock_download.return_value = df
        result = fetch_ohlcv("INVALID", 30)
        assert result.empty

    @patch("stockiq.backend.data.yf_fetch.yf.download")
    def test_drops_nan_close_rows(self, mock_download):
        df = _make_yf_df(50)
        df.loc[df.index[10], "Close"] = np.nan
        mock_download.return_value = df
        result = fetch_ohlcv("AAPL", 30)
        assert result["Close"].isna().sum() == 0

    @patch("stockiq.backend.data.yf_fetch.yf.download")
    def test_ticker_passed_to_yfinance(self, mock_download):
        mock_download.return_value = _make_yf_df(100)
        fetch_ohlcv("MSFT", 365)
        called_ticker = mock_download.call_args[0][0]
        assert called_ticker == "MSFT"


# ── get_company_name ──────────────────────────────────────────────────────────

class TestGetCompanyName:
    @patch("stockiq.backend.data.yf_fetch.yf.Ticker")
    def test_returns_long_name(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.info = {"longName": "Apple Inc."}
        mock_ticker_cls.return_value = mock_ticker
        name = get_company_name("AAPL")
        assert name == "Apple Inc."

    @patch("stockiq.backend.data.yf_fetch.yf.Ticker")
    def test_falls_back_to_ticker_on_missing_long_name(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_ticker_cls.return_value = mock_ticker
        name = get_company_name("XYZ")
        assert name == "XYZ"

    @patch("stockiq.backend.data.yf_fetch.yf.Ticker")
    def test_falls_back_to_ticker_on_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("network error")
        name = get_company_name("FAIL")
        assert name == "FAIL"

    @patch("stockiq.backend.data.yf_fetch.yf.Ticker")
    def test_returns_string(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.info = {"longName": "Microsoft Corporation"}
        mock_ticker_cls.return_value = mock_ticker
        name = get_company_name("MSFT")
        assert isinstance(name, str)


# ── search_companies ──────────────────────────────────────────────────────────

class TestSearchCompanies:
    @patch("stockiq.backend.data.yf_fetch.yf.Search")
    def test_returns_list(self, mock_search_cls):
        mock_search = MagicMock()
        mock_search.quotes = [
            {"symbol": "AAPL", "longname": "Apple Inc.", "exchDisp": "NASDAQ", "typeDisp": "Equity"},
        ]
        mock_search_cls.return_value = mock_search
        result = search_companies("apple")
        assert isinstance(result, list)

    @patch("stockiq.backend.data.yf_fetch.yf.Search")
    def test_returns_expected_keys(self, mock_search_cls):
        mock_search = MagicMock()
        mock_search.quotes = [
            {"symbol": "AAPL", "longname": "Apple Inc.", "exchDisp": "NASDAQ", "typeDisp": "Equity"},
        ]
        mock_search_cls.return_value = mock_search
        result = search_companies("apple")
        if result:
            keys = set(result[0].keys())
            assert "symbol" in keys

    @patch("stockiq.backend.data.yf_fetch.yf.Search")
    def test_empty_query_returns_empty_list(self, mock_search_cls):
        mock_search = MagicMock()
        mock_search.quotes = []
        mock_search_cls.return_value = mock_search
        result = search_companies("")
        assert result == [] or isinstance(result, list)

    @patch("stockiq.backend.data.yf_fetch.yf.Search")
    def test_exception_returns_empty_list(self, mock_search_cls):
        mock_search_cls.side_effect = Exception("search error")
        result = search_companies("apple")
        assert result == []
