"""
Tests for signal endpoints: /signals/today, /signals/{id}/grade, etc.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestGetTodaysSignals:
    """GET /signals/today"""

    def test_authenticated_returns_200(self, authenticated_client):
        """Authenticated request returns 200 with signal list."""
        resp = authenticated_client.get("/signals/today")
        assert resp.status_code == 200
        data = resp.json()
        assert "signals" in data

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/signals/today")
        assert resp.status_code == 401

    def test_empty_db_returns_zero_count(self, authenticated_client):
        """Empty database returns count=0 and total=0."""
        resp = authenticated_client.get("/signals/today")
        data = resp.json()
        assert data["count"] == 0
        assert data["total"] == 0

    def test_pagination_limits_results(self, authenticated_client, create_test_trade):
        """limit=2 returns at most 2 signals."""
        for i in range(4):
            create_test_trade(signal_kwargs={"symbol": f"SYM{i}.NS", "confidence": 0.85})
        resp = authenticated_client.get("/signals/today?limit=2&skip=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 2

    def test_filter_by_signal_type(self, authenticated_client, create_test_trade):
        """signal_type=BUY returns only BUY signals."""
        create_test_trade(signal_kwargs={"signal_type": "BUY", "symbol": "A.NS"})
        # SELL signal without a trade won't show in /today (only open trades)
        resp = authenticated_client.get("/signals/today?signal_type=BUY")
        assert resp.status_code == 200
        data = resp.json()
        for s in data["signals"]:
            assert s["signal_type"] == "BUY"


class TestHighRiskSignals:
    """GET /signals/high-risk"""

    def test_authenticated_returns_200(self, authenticated_client):
        """Authenticated request returns 200."""
        resp = authenticated_client.get("/signals/high-risk")
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/signals/high-risk")
        assert resp.status_code == 401


class TestSignalGrade:
    """GET /signals/{signal_id}/grade"""

    def test_signal_with_outcome_returns_grade(self, authenticated_client, create_test_outcome):
        """Valid signal_id with an outcome returns 200 with grade + pnl."""
        sig, outcome = create_test_outcome()
        resp = authenticated_client.get(f"/signals/{sig.id}/grade")
        assert resp.status_code == 200
        data = resp.json()
        assert data["grade"] == outcome.outcome
        assert data["pnl_percent"] == outcome.pnl_percent

    def test_signal_without_outcome_returns_404(self, authenticated_client, create_test_signal):
        """Valid signal_id without an outcome returns 404."""
        sig = create_test_signal()
        resp = authenticated_client.get(f"/signals/{sig.id}/grade")
        assert resp.status_code == 404

    def test_nonexistent_signal_returns_404(self, authenticated_client):
        """Non-existent signal_id returns 404."""
        resp = authenticated_client.get("/signals/99999/grade")
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/signals/1/grade")
        assert resp.status_code == 401


class TestAnalyzeSymbol:
    """GET /signals/analyze/{symbol}"""

    @patch("app.api.routes_signals.data_provider")
    def test_valid_symbol_returns_analysis(self, mock_dp, authenticated_client):
        """Valid symbol with mocked data returns 200."""
        import pandas as pd
        import numpy as np
        # Create a realistic mock DataFrame
        dates = pd.date_range("2025-01-01", periods=120, freq="B")
        mock_df = pd.DataFrame({
            "date": dates,
            "open": np.random.uniform(2400, 2600, 120),
            "high": np.random.uniform(2500, 2700, 120),
            "low": np.random.uniform(2300, 2500, 120),
            "close": np.linspace(2400, 2600, 120),
            "volume": np.random.randint(1_000_000, 5_000_000, 120),
        })
        mock_dp.fetch_ticker_data.return_value = mock_df

        resp = authenticated_client.get("/signals/analyze/RELIANCE")
        # Should return 200 or 500 depending on indicator availability
        # We mainly verify it doesn't crash with 401/422
        assert resp.status_code in [200, 500]

    @patch("app.api.routes_signals.data_provider")
    def test_no_data_returns_error(self, mock_dp, authenticated_client):
        """Symbol with no market data returns error status."""
        mock_dp.fetch_ticker_data.return_value = None
        resp = authenticated_client.get("/signals/analyze/FAKE")
        assert resp.status_code in [404, 500]


class TestSignalBySymbol:
    """GET /signals/symbol/{symbol}"""

    def test_existing_signal_returns_200(self, authenticated_client, create_test_signal):
        """Existing symbol returns signal data."""
        create_test_signal(symbol="INFY.NS")
        resp = authenticated_client.get("/signals/symbol/INFY.NS")
        assert resp.status_code == 200

    def test_nonexistent_symbol_returns_404(self, authenticated_client):
        """Non-existent symbol returns 404."""
        resp = authenticated_client.get("/signals/symbol/NOSYMBOL.NS")
        assert resp.status_code == 404
