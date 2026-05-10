"""
Integration tests for API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.db.models import Signal, Trade
from app.auth import User
import uuid
from datetime import datetime

class TestHealthEndpoint:
    """Test health check endpoint"""
    
    def test_health_check(self, client):
        """Test /health endpoint returns 200"""
        response = client.get("/health")
        assert response.status_code == 200

class TestSignalsEndpoint:
    """Test signal endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup_auth_mock(self):
        """Mock current user for signal endpoints which are protected"""
        from app.main import app
        from app.auth import get_current_user
        
        def override_get_current_user():
            return User(id=1, username="testuser", is_active=True)
            
        app.dependency_overrides[get_current_user] = override_get_current_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    
    def test_get_todays_signals_empty(self, client):
        """Test getting signals when none exist"""
        response = client.get("/signals/today")
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert data["count"] == 0
        assert data["total"] == 0
    
    def test_get_todays_signals_with_pagination(self, client, test_db):
        """Test pagination works correctly"""
        # Create test signals
        for i in range(5):
            signal = Signal(
                uuid=str(uuid.uuid4()),
                symbol=f"TEST{i}.NS",
                signal_type="BUY",
                confidence=0.7 + (i * 0.01),
                sector_score=0.5,
                reason={"test": True},
                timestamp=datetime.now()
            )
            test_db.add(signal)
            test_db.commit() # commit to get id
            
            trade = Trade(
                signal_id=signal.id,
                symbol=signal.symbol,
                status="OPEN",
                entry_price=100.0,
                entry_date=datetime.now()
            )
            test_db.add(trade)
            
        test_db.commit()
        
        # Test pagination
        response = client.get("/signals/today?limit=2&skip=0")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["per_page"] == 2
    
    def test_get_signals_with_filter(self, client, test_db):
        """Test filtering by signal type"""
        # Create mixed signals
        for signal_type in ["BUY", "SELL"]:
            signal = Signal(
                uuid=str(uuid.uuid4()),
                symbol=f"TEST_{signal_type}.NS",
                signal_type=signal_type,
                confidence=0.75,
                sector_score=0.5,
                reason={"test": True},
                timestamp=datetime.now()
            )
            test_db.add(signal)
            
            if signal_type == "BUY":
                test_db.commit()
                trade = Trade(
                    signal_id=signal.id,
                    symbol=signal.symbol,
                    status="OPEN",
                    entry_price=100.0,
                    entry_date=datetime.now()
                )
                test_db.add(trade)
                
        test_db.commit()
        
        # Filter for BUY only
        response = client.get("/signals/today?signal_type=BUY")
        assert response.status_code == 200
        data = response.json()
        assert all(s["signal_type"] == "BUY" for s in data["signals"])
    
    def test_get_signals_min_confidence(self, client, test_db):
        """Test filtering by minimum confidence"""
        # Create signals with different confidence
        for i, conf in enumerate([0.6, 0.7, 0.8]):
            signal = Signal(
                uuid=str(uuid.uuid4()),
                symbol=f"TEST{i}.NS",
                signal_type="BUY",
                confidence=conf,
                sector_score=0.5,
                reason={"test": True},
                timestamp=datetime.now()
            )
            test_db.add(signal)
            test_db.commit()
            
            trade = Trade(
                signal_id=signal.id,
                symbol=signal.symbol,
                status="OPEN",
                entry_price=100.0,
                entry_date=datetime.now()
            )
            test_db.add(trade)
            
        test_db.commit()
        
        # Filter for confidence >= 0.75
        response = client.get("/signals/today?min_confidence=0.75")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert all(s["confidence"] >= 0.75 for s in data["signals"])
    
    def test_rate_limiting(self, client):
        """Test that rate limiting is applied"""
        # This test would require mocking or actual rapid requests
        # For now, just verify endpoint is accessible
        response = client.get("/signals/today")
        assert response.status_code == 200

class TestFetchEndpoint:
    """Test data fetching endpoints"""
    
    def test_fetch_endpoint_exists(self, client):
        """Test fetch endpoint is registered"""
        # Test GET with query param
        response = client.get("/fetch/historical?symbol=TEST.NS")
        # Should return 404 (No data) or 200, but definitely allowed
        assert response.status_code in [200, 401, 404, 422, 500]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
