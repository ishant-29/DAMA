"""
Market Calendar Service — determines trading days, holidays, and market hours.
Uses the market_holidays DB table + IST timezone for NSE.
"""

import logging
from datetime import datetime, date, timedelta, timezone, time as dt_time
from sqlalchemy.orm import Session

from app.db.models import MarketHoliday
from app.core.config import settings

logger = logging.getLogger(__name__)

# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# NSE market hours (IST)
MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)


class MarketCalendarService:

    @staticmethod
    def is_trading_day(d: date, db: Session) -> bool:
        """Returns True if the given date is a valid NSE trading day."""
        # Weekends are never trading days
        if d.weekday() >= 5:
            return False

        # Check holiday table
        date_str = d.isoformat()
        holiday = (
            db.query(MarketHoliday)
            .filter(MarketHoliday.date == date_str)
            .first()
        )
        return holiday is None

    @staticmethod
    def is_market_open(db: Session, at: datetime = None) -> bool:
        """
        Returns True if the market is currently open.
        Checks: is today a trading day AND is current IST time within 09:15–15:30?
        """
        if at is None:
            at = datetime.now(IST)
        elif at.tzinfo is None:
            at = at.replace(tzinfo=IST)

        today = at.date()
        if not MarketCalendarService.is_trading_day(today, db):
            return False

        current_time = at.time()
        return MARKET_OPEN <= current_time <= MARKET_CLOSE

    @staticmethod
    def next_open_time(db: Session) -> datetime:
        """
        Returns the next market open datetime.
        If market is currently open, returns now.
        """
        now = datetime.now(IST)

        if MarketCalendarService.is_market_open(db, at=now):
            return now

        # If before open today and today is a trading day
        today = now.date()
        if (MarketCalendarService.is_trading_day(today, db)
                and now.time() < MARKET_OPEN):
            return datetime.combine(today, MARKET_OPEN, tzinfo=IST)

        # Find next trading day
        candidate = today + timedelta(days=1)
        for _ in range(10):  # max 10 days lookahead
            if MarketCalendarService.is_trading_day(candidate, db):
                return datetime.combine(candidate, MARKET_OPEN, tzinfo=IST)
            candidate += timedelta(days=1)

        # Fallback — shouldn't happen
        return datetime.combine(candidate, MARKET_OPEN, tzinfo=IST)

    @staticmethod
    def get_trading_days_between(
        start: date, end: date, db: Session
    ) -> list[date]:
        """Return list of valid trading days in [start, end] range."""
        # Fetch all holidays in range
        holidays_rows = (
            db.query(MarketHoliday.date)
            .filter(
                MarketHoliday.date >= start.isoformat(),
                MarketHoliday.date <= end.isoformat(),
            )
            .all()
        )
        holiday_set = {row.date for row in holidays_rows}

        days = []
        current = start
        while current <= end:
            if current.weekday() < 5 and current.isoformat() not in holiday_set:
                days.append(current)
            current += timedelta(days=1)

        return days

    @staticmethod
    def get_holidays(db: Session, year: int = None) -> list[MarketHoliday]:
        """Get all holidays, optionally filtered by year."""
        query = db.query(MarketHoliday)
        if year:
            query = query.filter(MarketHoliday.date.like(f"{year}-%"))
        return query.order_by(MarketHoliday.date).all()
