"""Tests for user settings endpoints + UserSettingsService."""
import pytest


class TestUserSettings:

    def test_get_settings_creates_defaults(self, authenticated_client):
        """GET /user/settings should auto-create default settings for new user."""
        resp = authenticated_client.get("/user/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stop_loss_pct"] == 0.05
        assert data["take_profit_pct"] == 0.10
        assert data["max_positions"] == 5

    def test_update_settings_success(self, authenticated_client):
        # Create defaults first
        authenticated_client.get("/user/settings")

        resp = authenticated_client.put(
            "/user/settings",
            json={"stop_loss_pct": 0.08, "take_profit_pct": 0.20}
        )
        assert resp.status_code == 200
        assert resp.json()["stop_loss_pct"] == 0.08
        assert resp.json()["take_profit_pct"] == 0.20

    def test_update_settings_out_of_range_returns_422(self, authenticated_client):
        # Create defaults first
        authenticated_client.get("/user/settings")

        resp = authenticated_client.put(
            "/user/settings",
            json={"stop_loss_pct": 0.99}
        )
        assert resp.status_code == 422

    def test_update_max_positions_out_of_range(self, authenticated_client):
        authenticated_client.get("/user/settings")

        resp = authenticated_client.put(
            "/user/settings",
            json={"max_positions": 100}
        )
        assert resp.status_code == 422

    def test_reset_settings(self, authenticated_client):
        # Set custom values
        authenticated_client.get("/user/settings")
        authenticated_client.put("/user/settings", json={"stop_loss_pct": 0.15})

        # Reset
        resp = authenticated_client.delete("/user/settings")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"
        assert resp.json()["stop_loss_pct"] == 0.05  # back to default

    def test_update_with_empty_body(self, authenticated_client):
        authenticated_client.get("/user/settings")
        resp = authenticated_client.put("/user/settings", json={})
        assert resp.status_code == 200
