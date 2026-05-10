"""
Pydantic response schemas for the NSE Signal Engine API.
Provides strict typing, auto-validation, and OpenAPI documentation.
"""
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class SignalReason(BaseModel):
    """Technical reason details for a signal."""
    ema_condition: bool = False
    darvas_condition: bool = False
    trend: Optional[str] = None
    is_high_risk: Optional[bool] = None
    vol_ratio: Optional[float] = None
    message: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional fields (e.g. legacy reason keys)


class SignalResult(BaseModel):
    """Single signal analysis result."""
    uuid: Optional[str] = None
    symbol: str
    signal_type: Literal["BUY", "SELL", "NEUTRAL"]
    confidence: float = Field(ge=0.0, le=1.0)
    sector_score: float = 0.0
    sector: Optional[str] = None
    timestamp: Optional[Any] = None  # datetime or str
    reason: SignalReason = SignalReason()
    is_high_risk: bool = False
    vol_valid: bool = False
    ml_used: bool = False

    class Config:
        from_attributes = True  # Support ORM objects


class SignalListResponse(BaseModel):
    """Paginated list of signals returned by /signals/today."""
    total: int = 0
    count: int = 0
    page: int = 1
    per_page: int = 50
    last_updated: Optional[str] = None
    data_staleness_hours: float = 0.0
    signals: list[dict] = []  # Keep as dict for backward compat with existing serialization


class BacktestSignalEvent(BaseModel):
    """A single event in a walk-forward backtest timeline."""
    date: str
    signal: Literal["BUY", "SELL"]
    entry_price: float
    exit_price: Optional[float] = None
    pnl_pct: Optional[float] = None


class BacktestResult(BaseModel):
    """Response schema for GET /analytics/backtest/{symbol}."""
    symbol: str
    days: int
    win_rate: float
    avg_return_pct: float
    max_drawdown_pct: float
    total_signals_generated: int
    signal_timeline: list[BacktestSignalEvent] = []
