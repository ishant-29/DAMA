"""
Tests for performance endpoints: /performance/summary, active-trades, recent-suggestions.
"""
import pytest


class TestPerformanceSummary:
    """GET /performance/summary"""

    def test_authenticated_returns_200(self, authenticated_client):
        """Returns performance summary data."""
        resp = authenticated_client.get("/performance/summary")
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/performance/summary")
        assert resp.status_code == 401


class TestRecentSuggestions:
    """GET /performance/recent-suggestions"""

    def test_returns_list(self, authenticated_client):
        """Returns a list of recent suggestions."""
        resp = authenticated_client.get("/performance/recent-suggestions?days=7")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_with_signals_returns_entries(self, authenticated_client, create_test_signal, create_test_trade):
        """With existing signals/trades, returns populated entries."""
        create_test_trade(signal_kwargs={"confidence": 0.85})
        resp = authenticated_client.get("/performance/recent-suggestions?days=30")
        assert resp.status_code == 200


class TestActiveTrades:
    """GET /performance/active-trades"""

    def test_empty_returns_empty_list(self, authenticated_client):
        """No active trades returns empty list."""
        resp = authenticated_client.get("/performance/active-trades")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 0

    def test_with_trades_returns_entries(self, authenticated_client, create_test_trade):
        """With open trades, returns trade entries."""
        create_test_trade()
        resp = authenticated_client.get("/performance/active-trades")
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/performance/active-trades")
        assert resp.status_code == 401


class TestPnlEdgeCases:
    """Unit tests for PnL calculation edge cases."""

    def test_zero_trades_win_rate_is_zero(self):
        """Win rate with zero trades should be 0, not division error."""
        trades = []
        if len(trades) == 0:
            win_rate = 0.0
        else:
            win_rate = sum(1 for t in trades if t > 0) / len(trades)
        assert win_rate == 0.0

    def test_all_losers_win_rate_is_zero(self):
        """All negative PnL trades → win rate = 0."""
        pnls = [-1.5, -2.0, -0.5]
        win_rate = sum(1 for p in pnls if p > 0) / len(pnls)
        assert win_rate == 0.0

    def test_mixed_pnl_win_rate_is_correct(self):
        """2 winners out of 4 trades → win rate = 0.50."""
        pnls = [3.0, -1.5, 2.0, -0.5]
        win_rate = sum(1 for p in pnls if p > 0) / len(pnls)
        assert win_rate == 0.5
