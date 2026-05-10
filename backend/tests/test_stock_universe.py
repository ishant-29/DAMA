"""Tests for StockUniverseService + stock admin endpoints."""
import pytest
from app.db.models import StockUniverse
from app.services.stock_universe_service import StockUniverseService


class TestStockUniverseService:

    def test_get_all_symbols(self, test_db):
        StockUniverseService._loaded_at = None
        StockUniverseService._cache = {}

        test_db.add(StockUniverse(symbol="RELIANCE.NS", name="Reliance", sector="Energy", index_name="NIFTY50"))
        test_db.add(StockUniverse(symbol="TCS.NS", name="TCS", sector="IT", index_name="NIFTY50"))
        test_db.commit()

        symbols = StockUniverseService.get_all_symbols(test_db)
        assert "RELIANCE.NS" in symbols
        assert "TCS.NS" in symbols
        assert len(symbols) == 2

    def test_get_by_sector(self, test_db):
        StockUniverseService._loaded_at = None
        StockUniverseService._cache = {}

        test_db.add(StockUniverse(symbol="TCS.NS", name="TCS", sector="IT"))
        test_db.add(StockUniverse(symbol="INFY.NS", name="Infosys", sector="IT"))
        test_db.add(StockUniverse(symbol="RELIANCE.NS", name="Reliance", sector="Energy"))
        test_db.commit()

        it_stocks = StockUniverseService.get_by_sector("IT", test_db)
        assert len(it_stocks) == 2
        assert "TCS.NS" in it_stocks

    def test_deactivated_stock_excluded(self, test_db):
        StockUniverseService._loaded_at = None
        StockUniverseService._cache = {}

        test_db.add(StockUniverse(symbol="ACTIVE.NS", name="Active", is_active=True))
        test_db.add(StockUniverse(symbol="DEAD.NS", name="Dead", is_active=False))
        test_db.commit()

        symbols = StockUniverseService.get_all_symbols(test_db)
        assert "ACTIVE.NS" in symbols
        assert "DEAD.NS" not in symbols

    def test_reload_refreshes_cache(self, test_db):
        StockUniverseService._loaded_at = None
        StockUniverseService._cache = {}

        test_db.add(StockUniverse(symbol="A.NS", name="A"))
        test_db.commit()

        symbols = StockUniverseService.get_all_symbols(test_db)
        assert len(symbols) == 1

        test_db.add(StockUniverse(symbol="B.NS", name="B"))
        test_db.commit()

        # Without reload, cache still returns 1
        symbols = StockUniverseService.get_all_symbols(test_db)
        assert len(symbols) == 1  # cached

        StockUniverseService.reload(test_db)
        symbols = StockUniverseService.get_all_symbols(test_db)
        assert len(symbols) == 2


class TestStockEndpoints:

    def test_add_stock(self, admin_client):
        resp = admin_client.post(
            "/admin/stocks",
            json={"symbol": "NEWCO.NS", "name": "New Company", "sector": "IT"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_list_stocks(self, admin_client, test_db):
        test_db.add(StockUniverse(symbol="TEST.NS", name="Test", sector="IT"))
        test_db.commit()

        resp = admin_client.get("/admin/stocks")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_update_stock(self, admin_client, test_db):
        test_db.add(StockUniverse(symbol="UP.NS", name="Update Me", sector="IT"))
        test_db.commit()

        resp = admin_client.put(
            "/admin/stocks/UP.NS",
            json={"sector": "Banking", "is_active": False}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_reload_endpoint(self, admin_client):
        resp = admin_client.post("/admin/stocks/reload")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_add_duplicate_stock_returns_409(self, admin_client, test_db):
        test_db.add(StockUniverse(symbol="DUP.NS", name="Duplicate"))
        test_db.commit()

        resp = admin_client.post(
            "/admin/stocks",
            json={"symbol": "DUP.NS", "name": "Duplicate Again"}
        )
        assert resp.status_code == 409
