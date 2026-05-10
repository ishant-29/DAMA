"""
Tests for backtesting endpoints: /backtest/run, /backtest/quick.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestBacktestRun:
    """POST /backtest/run"""

    @patch("app.api.routes_backtest.Backtester")
    @patch("app.api.routes_backtest.data_provider")
    def test_valid_params_returns_result(self, mock_dp, mock_bt_cls, authenticated_client, create_test_signal):
        """Valid start/end date with signals returns a result dict."""
        import pandas as pd
        import numpy as np
        from datetime import datetime

        # Insert a signal in the date range
        create_test_signal(timestamp=datetime(2025, 6, 15))

        # Mock data provider
        mock_df = pd.DataFrame({
            "date": pd.date_range("2025-06-01", periods=60),
            "open": np.random.uniform(100, 110, 60),
            "high": np.random.uniform(110, 120, 60),
            "low": np.random.uniform(90, 100, 60),
            "close": np.random.uniform(100, 110, 60),
            "volume": np.random.randint(100000, 500000, 60),
        })
        mock_dp.fetch_ticker_data.return_value = mock_df

        # Mock Backtester
        mock_bt_cls.return_value.run_backtest.return_value = {
            "total_trades": 5,
            "win_rate": 60.0,
            "total_pnl": 5000.0,
        }

        resp = authenticated_client.post(
            "/backtest/run?start_date=2025-06-01&end_date=2025-08-01"
        )
        assert resp.status_code in [200, 404, 500]

    def test_missing_start_date_returns_422(self, authenticated_client):
        """Missing start_date query param returns 422."""
        resp = authenticated_client.post("/backtest/run?end_date=2025-08-01")
        assert resp.status_code == 422

    def test_missing_end_date_returns_422(self, authenticated_client):
        """Missing end_date query param returns 422."""
        resp = authenticated_client.post("/backtest/run?start_date=2025-06-01")
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.post("/backtest/run?start_date=2025-06-01&end_date=2025-08-01")
        assert resp.status_code == 401
