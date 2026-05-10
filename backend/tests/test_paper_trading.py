"""
Tests for paper trading endpoints: /paper/portfolio, /paper/trade, etc.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestCreatePortfolio:
    """POST /paper/portfolio"""

    def test_creates_portfolio_successfully(self, authenticated_client):
        """Creates a new portfolio and returns its details."""
        resp = authenticated_client.post("/paper/portfolio?name=TestPortfolio&capital=500000")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TestPortfolio"
        assert data["initial_capital"] == 500000

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.post("/paper/portfolio?name=X&capital=100000")
        assert resp.status_code == 401


class TestGetPortfolio:
    """GET /paper/portfolio"""

    def test_with_portfolio_returns_200(self, authenticated_client, create_test_portfolio):
        """Returns portfolio report when one exists."""
        create_test_portfolio()
        resp = authenticated_client.get("/paper/portfolio")
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.get("/paper/portfolio")
        assert resp.status_code == 401


class TestExecutePaperTrade:
    """POST /paper/trade/{symbol}"""

    def test_quantity_zero_returns_422(self, authenticated_client):
        """quantity=0 fails validation (ge=1)."""
        resp = authenticated_client.post("/paper/trade/RELIANCE?quantity=0")
        assert resp.status_code == 422

    def test_quantity_negative_returns_422(self, authenticated_client):
        """quantity=-5 fails validation (ge=1)."""
        resp = authenticated_client.post("/paper/trade/RELIANCE?quantity=-5")
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.post("/paper/trade/RELIANCE?quantity=10")
        assert resp.status_code == 401


class TestGetTrades:
    """GET /paper/trades"""

    def test_returns_list_or_404_without_portfolio(self, authenticated_client):
        """Returns a list or 404 when no portfolio exists."""
        resp = authenticated_client.get("/paper/trades")
        assert resp.status_code in [200, 404]


class TestTaxReport:
    """GET /paper/tax-report"""

    def test_returns_report(self, authenticated_client):
        """Returns tax report dict."""
        resp = authenticated_client.get("/paper/tax-report")
        assert resp.status_code == 200

    def test_csv_returns_file(self, authenticated_client):
        """CSV endpoint returns downloadable content."""
        resp = authenticated_client.get("/paper/tax-report/csv")
        assert resp.status_code == 200


class TestTriggerMonitoring:
    """POST /paper/monitor"""

    def test_authenticated_returns_200(self, authenticated_client):
        """Monitoring trigger returns 200."""
        resp = authenticated_client.post("/paper/monitor")
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        resp = client.post("/paper/monitor")
        assert resp.status_code == 401
