"""
Tests for JWT authentication: login, register, and token validation.
"""
import os
import pytest
from datetime import timedelta
from unittest.mock import patch
from app.auth import create_access_token


class TestLogin:
    """POST /auth/login"""

    def test_login_valid_credentials_returns_token(self, client, create_test_user):
        """Valid username + password returns 200 with access_token."""
        create_test_user("loginuser", "correctpass")
        resp = client.post("/auth/login", data={"username": "loginuser", "password": "correctpass"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self, client, create_test_user):
        """Wrong password returns 401 Unauthorized."""
        create_test_user("wrongpw", "right")
        resp = client.post("/auth/login", data={"username": "wrongpw", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user_returns_401(self, client):
        """Non-existent username returns 401 Unauthorized."""
        resp = client.post("/auth/login", data={"username": "ghost", "password": "nope"})
        assert resp.status_code == 401


class TestRegister:
    """POST /auth/register"""

    def test_register_when_enabled_creates_user(self, client):
        """Registration succeeds when ALLOW_REGISTRATION=true."""
        with patch.dict(os.environ, {"ALLOW_REGISTRATION": "true"}):
            resp = client.post("/auth/register", json={"username": "newuser", "password": "newpass123"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_register_when_disabled_returns_403(self, client):
        """Registration returns 403 when ALLOW_REGISTRATION=false."""
        from app.core.config import settings
        original = settings.ALLOW_REGISTRATION
        settings.ALLOW_REGISTRATION = False
        try:
            resp = client.post("/auth/register", json={"username": "blocked", "password": "pass"})
            assert resp.status_code == 403
        finally:
            settings.ALLOW_REGISTRATION = original

    def test_register_duplicate_username_returns_400(self, client, create_test_user):
        """Duplicate username returns 400 Bad Request."""
        create_test_user("dupuser", "pass1")
        resp = client.post("/auth/register", json={"username": "dupuser", "password": "pass2"})
        assert resp.status_code == 400


class TestTokenValidation:
    """Protected endpoints with invalid/missing/expired tokens."""

    def test_no_token_returns_401(self, client):
        """Request without Authorization header returns 401."""
        resp = client.get("/signals/today")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client):
        """Malformed JWT returns 401."""
        resp = client.get("/signals/today", headers={"Authorization": "Bearer not.a.real.jwt"})
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client, create_test_user):
        """Expired JWT returns 401."""
        user, _ = create_test_user("expuser", "pass")
        token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        resp = client.get("/signals/today", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_valid_token_accesses_protected_route(self, authenticated_client):
        """Valid token allows access to protected endpoint."""
        resp = authenticated_client.get("/signals/today")
        assert resp.status_code == 200
