"""
Tests for WebSocket endpoint: /ws/signals.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.auth import create_access_token


class TestWebSocket:
    """WS /ws/signals"""

    def test_valid_token_accepts_connection(self, client, test_db, create_test_user):
        """Valid JWT in ?token= query param accepts WebSocket connection."""
        user, _ = create_test_user("wsuser", "wspass")
        token = create_access_token(data={"sub": user.username})

        # Patch SessionLocal so the WS handler uses our test DB instead of real PostgreSQL
        with patch("app.main.SessionLocal", return_value=test_db):
            with client.websocket_connect(f"/ws/signals?token={token}") as ws:
                ws.send_text("ping")
                data = ws.receive_json()
                assert data["type"] == "pong"

    def test_no_token_rejects_connection(self, client):
        """Missing token query param rejects with close code."""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/signals") as ws:
                ws.receive_text()

    def test_invalid_token_rejects_connection(self, client):
        """Invalid JWT rejects WebSocket connection."""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/signals?token=invalid.jwt.token") as ws:
                ws.receive_text()

    def test_expired_token_rejects_connection(self, client, create_test_user):
        """Expired JWT rejects WebSocket connection."""
        from datetime import timedelta
        user, _ = create_test_user("expwsuser", "pass")
        token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/signals?token={token}") as ws:
                ws.receive_text()
