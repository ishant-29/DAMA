"""Tests for MarketCalendarService + holiday admin endpoints."""
import pytest
from datetime import date

from app.db.models import MarketHoliday
from app.services.market_calendar import MarketCalendarService


class TestMarketCalendar:

    def test_saturday_is_not_trading_day(self, test_db):
        """Saturday should never be a trading day."""
        saturday = date(2025, 3, 15)  # a Saturday
        assert not MarketCalendarService.is_trading_day(saturday, test_db)

    def test_sunday_is_not_trading_day(self, test_db):
        sunday = date(2025, 3, 16)
        assert not MarketCalendarService.is_trading_day(sunday, test_db)

    def test_normal_weekday_is_trading_day(self, test_db):
        """A weekday with no holiday should be a trading day."""
        monday = date(2025, 3, 17)
        assert MarketCalendarService.is_trading_day(monday, test_db)

    def test_holiday_is_not_trading_day(self, test_db):
        """A day in the market_holidays table should not be a trading day."""
        holiday = MarketHoliday(date="2025-03-17", description="Test Holiday")
        test_db.add(holiday)
        test_db.commit()

        monday = date(2025, 3, 17)
        assert not MarketCalendarService.is_trading_day(monday, test_db)

    def test_get_trading_days_between(self, test_db):
        """Should exclude weekends and holidays."""
        start = date(2025, 3, 17)  # Monday
        end = date(2025, 3, 21)    # Friday
        days = MarketCalendarService.get_trading_days_between(start, end, test_db)
        assert len(days) == 5  # Mon-Fri, no holidays

        # Add a holiday
        h = MarketHoliday(date="2025-03-19", description="Test")
        test_db.add(h)
        test_db.commit()

        days = MarketCalendarService.get_trading_days_between(start, end, test_db)
        assert len(days) == 4  # Mon, Tue, Thu, Fri


class TestHolidayEndpoints:

    def test_add_holiday(self, admin_client):
        resp = admin_client.post(
            "/admin/market/holidays",
            json={"date": "2025-10-02", "description": "Gandhi Jayanti"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_list_holidays(self, admin_client, test_db):
        h = MarketHoliday(date="2025-08-15", description="Independence Day")
        test_db.add(h)
        test_db.commit()

        resp = admin_client.get("/admin/market/holidays")
        assert resp.status_code == 200
        dates = [x["date"] for x in resp.json()]
        assert "2025-08-15" in dates

    def test_list_holidays_by_year(self, admin_client, test_db):
        h1 = MarketHoliday(date="2025-01-26", description="RD")
        h2 = MarketHoliday(date="2026-01-26", description="RD")
        test_db.add_all([h1, h2])
        test_db.commit()

        resp = admin_client.get("/admin/market/holidays?year=2025")
        assert resp.status_code == 200
        assert all(x["date"].startswith("2025") for x in resp.json())

    def test_delete_holiday(self, admin_client, test_db):
        h = MarketHoliday(date="2025-12-25", description="Christmas")
        test_db.add(h)
        test_db.commit()

        resp = admin_client.delete("/admin/market/holidays/2025-12-25")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_add_duplicate_holiday_returns_409(self, admin_client, test_db):
        h = MarketHoliday(date="2025-08-15", description="Independence Day")
        test_db.add(h)
        test_db.commit()

        resp = admin_client.post(
            "/admin/market/holidays",
            json={"date": "2025-08-15", "description": "Duplicate"}
        )
        assert resp.status_code == 409
