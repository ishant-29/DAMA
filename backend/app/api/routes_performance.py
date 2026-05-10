from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.db.models import Trade, DailyPerformance, Signal
from app.auth import get_current_user, User  # FIXED: S3-04 — add auth import
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Schema for Responses
class TradeSchema(BaseModel):
    id: int
    symbol: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime]
    exit_price: Optional[float]
    status: str
    pnl_percent: Optional[float]
    holding_days: Optional[int]
    confidence: Optional[float] = 0.0
    
    class Config:
        from_attributes = True

class PerformanceSummarySchema(BaseModel):
    date: datetime
    total_trades_active: int
    win_rate_7d: float = 0.0
    avg_return_7d: float = 0.0
    total_signals_7d: int = 0
    
    win_rate_30d: float = 0.0
    avg_return_30d: float = 0.0
    total_signals_30d: int = 0

    win_rate_90d: float = 0.0
    avg_return_90d: float = 0.0
    max_drawdown_90d: float = 0.0
    total_signals_90d: int = 0
    
    class Config:
        from_attributes = True

@router.get("/summary", response_model=PerformanceSummarySchema)
def get_performance_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """
    Get the latest available rolling performance metrics.
    """
    latest = db.query(DailyPerformance).order_by(desc(DailyPerformance.date)).first()
    if not latest:
        # Return default zeroed if no data yet
        return PerformanceSummarySchema(
            date=datetime.utcnow(),
            total_trades_active=0,
            win_rate_90d=0.0,
            avg_return_90d=0.0,
            max_drawdown_90d=0.0,
            total_signals_90d=0
        )
    return latest

from app.services.data_provider import fetch_all_data_map

from app.core.config import settings

# Simple In-Memory Cache: {symbol: {'price': float, 'timestamp': datetime}}
_PRICE_CACHE = {}
_CACHE_EXPIRY_MINUTES = settings.PRICE_CACHE_EXPIRY_MINUTES

# Helper for Real-Time Prices
def fetch_live_prices(symbols: List[str]) -> dict:
    if not symbols:
        return {}
        
    now = datetime.utcnow()
    result_map = {}
    needed_symbols = []

    # 1. Check Cache
    for sym in symbols:
        cached = _PRICE_CACHE.get(sym)
        if cached:
            age = (now - cached['timestamp']).total_seconds() / 60
            if age < _CACHE_EXPIRY_MINUTES:
                result_map[sym] = cached['price']
                continue
        needed_symbols.append(sym)

    if not needed_symbols:
        return result_map

    # 2. Fetch Missing/Expired using Data Provider (Robust ThreadPool)
    try:
        logger.debug(f"Fetching prices for: {needed_symbols}")  # FIXED: S2-03
        # Use existing service that handles .NS logic and DataFrame formatting
        data_map = fetch_all_data_map(needed_symbols)
        
        fetched_map = {}
        for sym, df in data_map.items():
            if df is not None and not df.empty:
                # data_provider returns lower case columns: date, open, close...
                try:
                    price = float(df.iloc[-1]['close'])
                    fetched_map[sym] = price
                    
                    # Store variants for robust lookup
                    # data_provider might return key as "RELIANCE.NS" or "RELIANCE" depending on input
                    # We passed what was in needed_symbols.
                    
                    # Map simplified key too
                    base_sym = sym.replace('.NS', '').replace('.BO', '')
                    if base_sym != sym:
                        fetched_map[base_sym] = price
                        
                    # Map full key if we got base
                    if '.NS' not in sym and '.BO' not in sym:
                         fetched_map[f"{sym}.NS"] = price
                         
                except Exception as e:
                    logger.error(f"parsing data for {sym}: {e}")  # FIXED: S2-03
             
        # Update Cache
        for sym_key, price in fetched_map.items():
            _PRICE_CACHE[sym_key] = {'price': price, 'timestamp': now}
            result_map[sym_key] = price # Add to current result

        logger.debug(f"Cache keys after update: {list(_PRICE_CACHE.keys())}")  # FIXED: S2-03
        
    except Exception as e:
        logger.error(f"Error fetching prices: {e}", exc_info=True)  # FIXED: S2-03
        
    return result_map

class RecentSignalSchema(BaseModel):
    id: int
    symbol: str
    recommendation_date: datetime
    entry_price: float
    current_price: Optional[float]
    pnl_percent: Optional[float]
    confidence: float
    status: str # OPEN (if trade exists) or WAITING or IGNORED

    class Config:
        from_attributes = True

@router.get("/recent-suggestions", response_model=List[RecentSignalSchema])
def get_recent_suggestions(
    days: int = 7,
    min_confidence: float = 0.50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # FIXED: S3-04
):
    """
    Get all BUY signals from the last N days with their current performance.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # 1. Get Recent Signals (Last N Days)
    recent_signals = db.query(Signal).filter(
        Signal.signal_type == "BUY", 
        Signal.timestamp >= cutoff,
        Signal.confidence >= min_confidence
    ).all()
    
    # 2. Get Signals for ANY Active Trades (OPEN status)
    # We want to show older signals if they are still active
    active_trade_signals = db.query(Signal).join(Trade, Trade.signal_id == Signal.id).filter(
        Trade.status == "OPEN",
        Signal.signal_type == "BUY"
    ).all()
    
    # 3. Merge and Unique by ID
    # Use a dictionary to dedup, prioritizing recent_signals (though they are same objects)
    combined_map = {s.id: s for s in recent_signals}
    for s in active_trade_signals:
        combined_map[s.id] = s
        
    # Convert back to list and sort by timestamp desc
    signals = sorted(combined_map.values(), key=lambda x: x.timestamp, reverse=True)
    
    if not signals:
        return []

    # Get Live Prices
    symbols = list(set([s.symbol for s in signals]))
    price_map = fetch_live_prices(symbols)
    
    # Check if they are active trades
    active_trade_map = {
        t.signal_id: t.status
        for t in db.query(Trade).filter(Trade.signal_id.in_([s.id for s in signals])).all()
    }
    # FIXED: S4-01 — batch load all trades to avoid N+1 query
    trades_by_signal = {
        t.signal_id: t
        for t in db.query(Trade).filter(Trade.signal_id.in_([s.id for s in signals])).all()
    }

    results = []
    for sig in signals:
        # Determine Entry Price (Use signal price or close of that day usually)
        # We don't have signal price stored explicitly? 
        # Wait, Signal Schema doesn't have 'price'.
        # We usually use 'Trade.entry_price'.
        # But if no Trade, what was the price?
        # We might need to fetch historical price at signal date.
        # For approximation without re-fetching history, we assume Signal doesn't store price.
        # Check model: Signal has 'outcome', 'confidence', etc. No price.
        # We'll rely on Current Price - Current Price? No.
        # We need a reference.
        # If Trade exists, use its entry price.
        # If no Trade, we can't easily calculate PnL without historical lookup.
        # Use 0.0 or skip PnL for non-trades.
        
        entry_price = 0.0
        status = "IGNORED"
        
        # Check active trade
        if sig.id in active_trade_map:
            status = active_trade_map[sig.id]
            # Use trade entry price
            t = trades_by_signal.get(sig.id)  # FIXED: S4-01 — use batch-loaded map
            if t: entry_price = t.entry_price

            # Determine Status based on PnL and Trade Status
            if status == "OPEN":
                # Active Trade Logic
                # Must calculate PnL first using live price
                current_price = price_map.get(sig.symbol)
                temp_pnl = 0.0
                if current_price and entry_price > 0:
                     temp_pnl = ((current_price - entry_price) / entry_price) * 100
                
                if temp_pnl > settings.HOLD_STATUS_THRESHOLD_PERCENT:
                    status = "HOLD"
                elif temp_pnl < -settings.HOLD_STATUS_THRESHOLD_PERCENT:
                     status = "HOLD" 
                else:
                    status = "BUY ZONE"
            elif status == "CLOSED" or status == "EXPIRED":
                 # Trade is closed, we need to know if it was a Win or Loss
                 # Trade model has pnl_percent stored
                 if t and t.pnl_percent is not None:
                      if t.pnl_percent > 0:
                           status = "TARGET HIT"
                      else:
                           status = "STOPLOSS HIT"
                 else:
                      status = "COMPLETE" # Fallback if pnl missing

        
        current_price = price_map.get(sig.symbol)
        pnl = 0.0
        
        if current_price and entry_price > 0:
            pnl = ((current_price - entry_price) / entry_price) * 100
            
        results.append(RecentSignalSchema(
            id=sig.id,
            symbol=sig.symbol,
            recommendation_date=sig.timestamp,
            entry_price=entry_price,
            current_price=current_price,
            pnl_percent=pnl if entry_price > 0 else None,
            confidence=sig.confidence,
            status=status
        ))
        
    return results

@router.get("/active-trades", response_model=List[TradeSchema])
def get_active_trades(
    sort_by: str = "date",
    limit: int = 50,
    min_confidence: float = 0.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # FIXED: S3-04
):
    """
    Get currently active trades with LIVE PnL.
    """
    # Join Trade -> Signal to get confidence
    query = db.query(Trade, Signal.confidence).join(Signal, Trade.signal_id == Signal.id)\
        .filter(Trade.status == "OPEN")
    
    if min_confidence > 0:
        query = query.filter(Signal.confidence >= min_confidence)

    # Fetch Base Results
    results = query.all() # Fetch all enabling client-side sort if PnL needed
    
    # 1. Fetch Live Prices
    symbols = list(set([t.symbol for t, _ in results]))
    price_map = fetch_live_prices(symbols)
    
    # 2. Map & Calculate
    mapped = []
    from datetime import datetime
    now = datetime.utcnow()
    
    for t, conf in results:
        data = TradeSchema.model_validate(t)
        data.confidence = conf
        
        # Calc Holding Days
        if t.entry_date:
            data.holding_days = (now - t.entry_date).days
            
        # Calc Live PnL
        current_price = price_map.get(t.symbol)
        if current_price and t.entry_price > 0:
            data.pnl_percent = ((current_price - t.entry_price) / t.entry_price) * 100
        
        mapped.append(data)
    
    # 3. Sort (Now possible on PnL)
    if sort_by == "pnl":
        mapped.sort(key=lambda x: x.pnl_percent or -999, reverse=True)
    elif sort_by == "symbol":
        mapped.sort(key=lambda x: x.symbol)
    else:
        mapped.sort(key=lambda x: x.entry_date, reverse=True)
        
    return mapped[:limit]

@router.get("/history", response_model=List[TradeSchema])
def get_trade_history(
    limit: int = 100,
    offset: int = 0,
    status: str = "CLOSED",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # FIXED: S3-04
):
    """
    Get historical trades (Closed or Expired).
    """
    query = db.query(Trade)
    
    if status != "ALL":
        query = query.filter(Trade.status == status)
    else:
        query = query.filter(Trade.status.in_(["CLOSED", "EXPIRED"]))
        
    query = query.order_by(desc(Trade.exit_date))
    return query.offset(offset).limit(limit).all()

@router.get("/homepage", response_model=dict)
def get_homepage_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """
    Composite endpoint for Homepage Dashboard.
    Returns:
    - Summary Metrics
    - Top 5 Active Trades (by Recency? Or just list)
    - Recent Closed Trades
    """
    summary = get_performance_summary(db)
    
    active_trades = db.query(Trade).join(Signal).filter(
        Trade.status == "OPEN",
        Signal.confidence >= 0.50
    ).order_by(desc(Trade.entry_date)).limit(10).all()
        
    recent_closed = db.query(Trade).filter(Trade.status.in_(["CLOSED", "EXPIRED"]))\
        .order_by(desc(Trade.exit_date)).limit(5).all()
        
    return {
        "metrics": summary,
        "active_recommendations": active_trades,
        "recent_closed": recent_closed
    }
