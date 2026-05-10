"""
Tests for analytics endpoints: market-mood, market-regime, sectors, backtest, performance.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestMarketMood:
    """GET /analytics/market-mood"""

    def test_authenticated_returns_200(self, authenticated_client):
        """Authenticated request returns market mood data."""
        resp = authenticated_client.get("/analytics/market-mood")
        assert resp.status_code == 200
        data = resp.json()
        assert "mood" in data
        assert "score" in data
        assert "description" in data

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/analytics/market-mood")
        assert resp.status_code == 401

    def test_empty_signals_returns_neutral(self, authenticated_client):
        """With no signals, mood should be NEUTRAL."""
        resp = authenticated_client.get("/analytics/market-mood")
        data = resp.json()
        assert data["mood"] == "NEUTRAL"


class TestMarketRegime:
    """GET /analytics/market-regime"""

    @patch("app.api.routes_analytics.MarketRegimeDetector")
    @patch("app.api.routes_analytics.get_cached", new_callable=AsyncMock, return_value=None)
    @patch("app.api.routes_analytics.set_cached", new_callable=AsyncMock)
    def test_authenticated_returns_regime(self, mock_set, mock_get, mock_detector_cls, authenticated_client):
        """Returns regime data with mocked detector."""
        mock_result = MagicMock()
        mock_result.regime = "STRONG_BULL"
        mock_result.india_vix = 14.5
        mock_result.nifty_above_ema50 = True
        mock_result.allow_buy_signals = True
        mock_result.regime_description = "Strong bull"
        mock_result.min_confidence_threshold = 0.65
        mock_result.nifty_return_20d = 2.5
        mock_detector_cls.return_value.detect.return_value = mock_result

        resp = authenticated_client.get("/analytics/market-regime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["regime"] == "STRONG_BULL"

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/analytics/market-regime")
        assert resp.status_code == 401


class TestSectorRotation:
    """GET /analytics/sectors"""

    @patch("app.api.routes_analytics.SectorRotationEngine")
    @patch("app.api.routes_analytics.get_cached", new_callable=AsyncMock, return_value=None)
    @patch("app.api.routes_analytics.set_cached", new_callable=AsyncMock)
    def test_authenticated_returns_sectors(self, mock_set, mock_get, mock_engine_cls, authenticated_client):
        """Returns sector rotation report."""
        mock_engine_cls.return_value.get_full_report.return_value = {
            "top_sectors": ["IT", "BANK", "PHARMA"],
            "all_sectors": [],
        }
        resp = authenticated_client.get("/analytics/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert "top_sectors" in data


class TestAnalyticsBacktest:
    """GET /analytics/backtest/{symbol}"""

    @patch("app.api.routes_analytics.Backtester")
    @patch("app.api.routes_analytics.get_cached", new_callable=AsyncMock, return_value=None)
    @patch("app.api.routes_analytics.set_cached", new_callable=AsyncMock)
    def test_valid_symbol_returns_report(self, mock_set, mock_get, mock_bt_cls, authenticated_client):
        """Valid symbol returns backtest report dict."""
        # Use a simple object instead of MagicMock to avoid __dict__ issues on Python 3.14
        class MockReport:
            symbol = "RELIANCE"
            win_rate = 65.0
            total_trades = 10

        mock_bt_cls.return_value.run.return_value = MockReport()

        resp = authenticated_client.get("/analytics/backtest/RELIANCE?days=365")
        assert resp.status_code == 200

    @patch("app.api.routes_analytics.Backtester")
    @patch("app.api.routes_analytics.get_cached", new_callable=AsyncMock, return_value=None)
    def test_invalid_symbol_returns_400(self, mock_get, mock_bt_cls, authenticated_client):
        """Backtester raising ValueError returns 400."""
        mock_bt_cls.return_value.run.side_effect = ValueError("No data")
        resp = authenticated_client.get("/analytics/backtest/FAKE?days=365")
        assert resp.status_code == 400


class TestPerformanceMetrics:
    """GET /analytics/performance"""

    def test_authenticated_returns_200(self, authenticated_client):
        """Returns performance metrics."""
        resp = authenticated_client.get("/analytics/performance?period_days=30")
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/analytics/performance")
        assert resp.status_code == 401
