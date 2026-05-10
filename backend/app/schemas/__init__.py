"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Dict, List

class SignalResponse(BaseModel):
    """Response schema for signal data"""
    uuid: str
    symbol: str
    signal_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sector_score: float
    reason: Dict
    timestamp: datetime
    model_version: Optional[str] = None
    
    class Config:
        from_attributes = True  # Updated from orm_mode for pydantic v2

class FetchHistoricalRequest(BaseModel):
    """Request schema for fetching historical data"""
    symbols: List[str] = Field(..., min_length=1, max_length=100, description="Stock symbols to fetch")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        """Ensure symbols end with .NS for NSE stocks"""
        return [s if s.endswith('.NS') else f"{s}.NS" for s in v]
    
    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate date format"""
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v

class SignalFilter(BaseModel):
    """Request schema for filtering signals"""
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)
    max_confidence: float = Field(1.0, ge=0.0, le=1.0)
    signal_type: Optional[str] = Field(None, regex="^(BUY|SELL)$")
    symbols: Optional[List[str]] = None
    
    @validator('max_confidence')
    def validate_confidence_range(cls, v, values):
        """Ensure max >= min"""
        if 'min_confidence' in values and v < values['min_confidence']:
            raise ValueError('max_confidence must be >= min_confidence')
        return v

class PaginationParams(BaseModel):
    """Pagination parameters"""
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=500, description="Maximum number of records to return")
