"""
Centralized datetime utilities ensuring consistent timezone handling across the application.
All datetime operations should use these utilities to avoid mixing naive and aware datetimes.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
from zoneinfo import ZoneInfo

# India timezone (IST)
IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def now_utc() -> datetime:
    """Get current time in UTC with timezone awareness."""
    return datetime.now(UTC)


def now_ist() -> datetime:
    """Get current time in IST with timezone awareness."""
    return datetime.now(IST)


def to_utc(dt: Union[datetime, str, None]) -> Optional[datetime]:
    """
    Convert a datetime to UTC with timezone awareness.
    Handles various input formats including naive datetimes, ISO strings, etc.
    """
    if dt is None:
        return None
    
    if isinstance(dt, str):
        # Try parsing ISO format
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            try:
                dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return None
    
    if isinstance(dt, datetime):
        # If naive, assume UTC
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        # Convert to UTC if different timezone
        return dt.astimezone(UTC)
    
    return None


def to_ist(dt: Union[datetime, str, None]) -> Optional[datetime]:
    """Convert a datetime to IST with timezone awareness."""
    utc_dt = to_utc(dt)
    if utc_dt is None:
        return None
    return utc_dt.astimezone(IST)


def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert datetime to naive UTC (strip timezone info for DB compatibility)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC)
    return dt.replace(tzinfo=None)


def format_iso(dt: Union[datetime, str, None]) -> Optional[str]:
    """Format datetime as ISO string."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat()
    return None


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime."""
    formats = [
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def get_market_close_time(date: Optional[datetime] = None) -> datetime:
    """
    Get the market close time (15:30 IST) for a given date.
    Default is today.
    """
    if date is None:
        date = now_ist()
    
    # Market closes at 15:30 IST = 10:00 UTC
    close_time = date.replace(hour=10, minute=0, second=0, microsecond=0)
    return close_time.astimezone(UTC)


def get_trading_day(dt: Optional[datetime] = None) -> datetime:
    """Get the trading day (NSE market date) for a given datetime."""
    if dt is None:
        dt = now_utc()
    
    # If before 10:00 UTC, it's still the previous trading day's candle
    market_open_utc = datetime.time(10, 0)
    current_time = dt.time()
    
    if current_time < market_open_utc and dt.weekday() < 5:
        # Before market open, use previous day's date for trading
        return (dt - timedelta(days=1)).date()
    
    return dt.date()


class DateTimeRange:
    """Helper class for date range operations."""
    
    def __init__(self, start: datetime, end: datetime):
        self.start = to_utc(start)
        self.end = to_utc(end)
    
    def contains(self, dt: datetime) -> bool:
        """Check if datetime is within range."""
        dt_utc = to_utc(dt)
        return self.start <= dt_utc <= self.end if dt_utc else False
    
    def days(self) -> int:
        """Get number of days in range."""
        return (self.end - self.start).days
    
    def to_dict(self) -> dict:
        return {'start': format_iso(self.start), 'end': format_iso(self.end)}