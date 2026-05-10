"""
Pytest configuration and shared fixtures.
Sets up an in-memory SQLite database, overrides FastAPI deps,
and provides reusable factory fixtures for tests.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock

# ── Env overrides BEFORE any app import ────────────────────────
# The app's Settings class validates SECRET_KEY length >= 32 and
# DATABASE_URL starts with postgresql://. We set env vars here so
# the Settings object can be constructed without a real .env file.
os.environ.setdefault("SECRET_KEY", "test_secret_key_that_is_at_least_32_characters_long!")
os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost/fake")
os.environ.setdefault("ALLOW_REGISTRATION", "true")

from app.db.models import Base, Signal, SignalOutcome, Trade, PaperPortfolio, PaperTrade, SystemConfig, UserSettings, MarketHoliday, StockUniverse
from app.db.session import get_db
from app.main import app
from app.auth import (
    User,
    get_current_user,
    hash_password,
    create_access_token,
)


# ── SQLite FK support ──────────────────────────────────────────
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


def _enable_foreign_keys(dbapi_conn, connection_record):
    """SQLite doesn't enforce FKs by default — turn them on."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ── Core Fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """TestClient wired to the in-memory DB with scheduler disabled."""

    def _override_get_db():
        try:
            yield test_db
        finally:
            pass  # don't close — fixture owns the session

    app.dependency_overrides[get_db] = _override_get_db

    with patch("app.main.engine", test_db.get_bind()), \
         patch("app.core.scheduler.start_scheduler", MagicMock()), \
         patch("app.core.scheduler.shutdown_scheduler", MagicMock()):
        with TestClient(app) as tc:
            yield tc

    app.dependency_overrides.clear()


# ── Factory Fixtures ───────────────────────────────────────────


@pytest.fixture()
def create_test_user(test_db):
    """Factory that creates a User row and returns (User, plain_password)."""

    def _create(username: str = "testuser", password: str = "testpassword"):
        user = User(
            username=username,
            hashed_password=hash_password(password),
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user, password

    return _create


@pytest.fixture()
def auth_headers(create_test_user):
    """Register a default user and return {'Authorization': 'Bearer <token>'}."""
    user, _ = create_test_user("authuser", "authpass")
    token = create_access_token(data={"sub": user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def authenticated_client(client, auth_headers):
    """A TestClient wrapper whose .get / .post auto-inject auth headers."""

    class _AuthClient:
        def __init__(self, inner, headers):
            self._inner = inner
            self._headers = headers

        def _merge(self, kwargs):
            h = kwargs.pop("headers", {})
            h.update(self._headers)
            kwargs["headers"] = h
            return kwargs

        def get(self, url, **kw):
            return self._inner.get(url, **self._merge(kw))

        def post(self, url, **kw):
            return self._inner.post(url, **self._merge(kw))

        def put(self, url, **kw):
            return self._inner.put(url, **self._merge(kw))

        def delete(self, url, **kw):
            return self._inner.delete(url, **self._merge(kw))

        def websocket_connect(self, url, **kw):
            return self._inner.websocket_connect(url, **kw)

    return _AuthClient(client, auth_headers)


@pytest.fixture()
def create_test_signal(test_db):
    """Factory to insert a Signal row into the test DB."""

    def _create(**kwargs):
        defaults = dict(
            uuid=str(uuid.uuid4()),
            symbol="RELIANCE.NS",
            signal_type="BUY",
            confidence=0.80,
            sector_score=0.65,
            reason={"ema_condition": True, "darvas_condition": True},
            timestamp=datetime.now(timezone.utc),
            model_version="test-v1",
        )
        defaults.update(kwargs)
        sig = Signal(**defaults)
        test_db.add(sig)
        test_db.commit()
        test_db.refresh(sig)
        return sig

    return _create


@pytest.fixture()
def create_test_trade(test_db, create_test_signal):
    """Factory to insert a Signal + Trade pair."""

    def _create(signal_kwargs=None, **trade_kwargs):
        sig = create_test_signal(**(signal_kwargs or {}))
        defaults = dict(
            signal_id=sig.id,
            symbol=sig.symbol,
            status="OPEN",
            entry_price=2500.0,
            entry_date=datetime.now(timezone.utc),
        )
        defaults.update(trade_kwargs)
        trade = Trade(**defaults)
        test_db.add(trade)
        test_db.commit()
        test_db.refresh(trade)
        return sig, trade

    return _create


@pytest.fixture()
def create_test_outcome(test_db, create_test_signal):
    """Factory to insert a Signal + SignalOutcome pair."""

    def _create(signal_kwargs=None, **outcome_kwargs):
        sig = create_test_signal(**(signal_kwargs or {}))
        defaults = dict(
            signal_id=sig.id,
            outcome="WIN",
            pnl_percent=3.5,
            closed_at=datetime.now(timezone.utc),
        )
        defaults.update(outcome_kwargs)
        outcome = SignalOutcome(**defaults)
        test_db.add(outcome)
        test_db.commit()
        test_db.refresh(outcome)
        return sig, outcome

    return _create


@pytest.fixture()
def create_test_portfolio(test_db):
    """Factory to insert a PaperPortfolio."""

    def _create(name="Test Portfolio", capital=1_000_000.0):
        portfolio = PaperPortfolio(
            name=name,
            initial_capital=capital,
            current_cash=capital,
            is_active=True,
        )
        test_db.add(portfolio)
        test_db.commit()
        test_db.refresh(portfolio)
        return portfolio

    return _create


@pytest.fixture()
def create_admin_user(test_db):
    """Factory that creates an admin User row and returns (User, plain_password)."""

    def _create(username: str = "adminuser", password: str = "adminpassword"):
        user = User(
            username=username,
            hashed_password=hash_password(password),
            is_active=True,
            is_admin=True,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user, password

    return _create


@pytest.fixture()
def admin_auth_headers(create_admin_user):
    """Register an admin user and return {'Authorization': 'Bearer <token>'}."""
    user, _ = create_admin_user("admin", "adminpass")
    token = create_access_token(data={"sub": user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_client(client, admin_auth_headers):
    """A TestClient wrapper whose .get / .post auto-inject admin auth headers."""

    class _AdminClient:
        def __init__(self, inner, headers):
            self._inner = inner
            self._headers = headers

        def _merge(self, kwargs):
            h = kwargs.pop("headers", {})
            h.update(self._headers)
            kwargs["headers"] = h
            return kwargs

        def get(self, url, **kw):
            return self._inner.get(url, **self._merge(kw))

        def post(self, url, **kw):
            return self._inner.post(url, **self._merge(kw))

        def put(self, url, **kw):
            return self._inner.put(url, **self._merge(kw))

        def delete(self, url, **kw):
            return self._inner.delete(url, **self._merge(kw))

    return _AdminClient(client, admin_auth_headers)

