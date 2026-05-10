from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Signal, SignalOutcome
from app.services.signal_engine import SignalEngine
import pandas as pd
from datetime import datetime
import os
import numpy as np
from app.indicators.ema import ema_df
from app.indicators.darvas import darvas_boxes
from app.services import data_provider
import logging
from typing import Optional
from app.core.config import settings
from app.auth import get_current_user, User  # FIXED: S1-01 — removed duplicate import

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/today")
async def get_todays_signals(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    signal_type: Optional[str] = Query(None, regex="^(BUY|SELL)$"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get active signals for the homepage.
    - BUYs: Returns ALL currently OPEN trades (Active Positions).
    - SELLs: Returns SELL signals from the last 3 days (Recent Exits/Warnings).
    Results are cached in Redis for 90 seconds.
    """
    # --- Redis cache check ---
    from app.services.cache_redis import get_cached, set_cached
    cache_key = f"signals:today:{skip}:{limit}:{signal_type}:{min_confidence}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached

    # Filter noise: Default to system threshold if not explicitly requesting all (0.0)
    # This cleans up legacy "Active Trades" that were created with low confidence
    if min_confidence == 0.0:
        min_confidence = settings.ML_CONFIDENCE_THRESHOLD

    from datetime import timedelta
    from app.db.models import Trade
    
    # 1. Active BUYs - Optimized single query with LEFT OUTER JOIN
    # Get signals that either have open trades OR are fresh BUY signals without trades
    buy_cutoff = datetime.now() - timedelta(days=settings.SIGNAL_MAX_AGE_DAYS)
    
    # Use OR condition: either has open trade OR no trade at all (fresh signal)
    from sqlalchemy import or_
    active_buys_query = db.query(Signal).outerjoin(
        Trade, Signal.id == Trade.signal_id
    ).filter(
        Signal.signal_type == "BUY",
        Signal.timestamp >= buy_cutoff,
        Signal.confidence >= min_confidence,
    ).filter(
        or_(
            Trade.status == "OPEN",
            Trade.id.is_(None)
        )
    ).group_by(Signal.id)
    
    # 2. Recent SELLs - Same day range as buy cutoff for consistency
    sell_cutoff = datetime.now() - timedelta(days=settings.RECENT_SELL_WINDOW_DAYS)
    recent_sells_query = db.query(Signal).filter(
        Signal.signal_type == "SELL",
        Signal.timestamp >= sell_cutoff,
        Signal.confidence >= min_confidence
    )
    
    combined_signals = []
    total = 0
    
    # helper vars
    limit_fetch = skip + limit
    
    # Execute queries based on requested signal_type filter
    if signal_type == "BUY":
        total = active_buys_query.count()
        combined_signals.extend(
            active_buys_query.order_by(Signal.timestamp.desc()).limit(limit_fetch).all()
        )
    elif signal_type == "SELL":
        total = recent_sells_query.count()
        combined_signals.extend(
            recent_sells_query.order_by(Signal.timestamp.desc()).limit(limit_fetch).all()
        )
    else:
        # Both
        c1 = active_buys_query.count()
        c2 = recent_sells_query.count()
        total = c1 + c2
        
        combined_signals.extend(
            active_buys_query.order_by(Signal.timestamp.desc()).limit(limit_fetch).all()
        )
        combined_signals.extend(
            recent_sells_query.order_by(Signal.timestamp.desc()).limit(limit_fetch).all()
        )
    
    # Sort: Most recent first (by timestamp)
    combined_signals.sort(key=lambda s: s.timestamp, reverse=True)
    
    # Pagination
    paginated = combined_signals[skip : skip + limit]

    # Compute data staleness
    latest_ts = paginated[0].timestamp if paginated else None
    staleness_hours = 0.0
    if latest_ts:
        try:
            diff = datetime.now() - latest_ts
            staleness_hours = round(diff.total_seconds() / 3600, 2)
        except (TypeError, ValueError):
            staleness_hours = 0.0
    
    result = {
        "total": total,
        "count": len(paginated),
        "page": skip // limit + 1 if limit > 0 else 1,
        "per_page": limit,
        "last_updated": str(latest_ts) if latest_ts else None,
        "data_staleness_hours": staleness_hours,
        "signals": [
            {
                "uuid": s.uuid,
                "symbol": s.symbol,
                "signal_type": s.signal_type,
                "confidence": s.confidence,
                "sector_score": s.sector_score,
                "timestamp": s.timestamp,
                "reason": s.reason
            } for s in paginated
        ]
    }

    # --- Store in Redis cache (90s TTL) ---
    await set_cached(cache_key, result, ttl=settings.REDIS_DEFAULT_TTL)
    return result


@router.get("/high-risk")
def get_high_risk_signals(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get high risk signals only"""
    # Relaxed date filter for High Risk too
    from datetime import timedelta
    cutoff_date = datetime.now().date() - timedelta(days=settings.HIGH_RISK_WINDOW_DAYS)
    
    # Simplified query - filter by low confidence threshold instead of JSON field
    query = db.query(Signal).filter(
        Signal.timestamp >= cutoff_date,
        Signal.confidence < settings.ML_CONFIDENCE_THRESHOLD  # High risk = low confidence
    )
    
    total = query.count()
    signals = query.order_by(Signal.confidence.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "count": len(signals),
        "page": skip // limit + 1 if limit > 0 else 1,
        "per_page": limit,
        "signals": [
            {
                "uuid": s.uuid,
                "symbol": s.symbol,
                "signal_type": s.signal_type,
                "confidence": s.confidence,
                "sector_score": s.sector_score,
                "timestamp": s.timestamp,
                "reason": s.reason
            } for s in signals
        ]
    }



@router.get("/symbol/{symbol}")
def get_signal_by_symbol(symbol: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get signal for a specific symbol from database (FAST)
    """
    # Get latest signal for this symbol
    signal = db.query(Signal).filter(
        Signal.symbol == symbol
    ).order_by(Signal.timestamp.desc()).first()
    
    if not signal:
        raise HTTPException(status_code=404, detail=f"No signal found for {symbol}")
    
    return signal



# Cache sector scores to avoid reading CSV on every request
from functools import lru_cache
import time

_SECTOR_CACHE = {
    "last_updated": 0,
    "scores": {}
}

def get_normalized_sector_scores():
    """
    Fetches sector momentum and normalizes it to 0.1-0.9 range
    to match SignalEngine's internal logic.
    Caches for 60 minutes.
    """
    global _SECTOR_CACHE
    now = time.time()
    
    # 60 minute cache
    if now - _SECTOR_CACHE["last_updated"] < settings.SECTOR_CACHE_TTL and _SECTOR_CACHE["scores"]:
        return _SECTOR_CACHE["scores"]
        
    try:
        from app.services.sector import SectorService
        service = SectorService()
        momentum = service.get_sector_momentum() # [{'sector': 'Auto', 'avg_return': 1.2}, ...]
        
        raw_scores = {item['sector']: item['avg_return'] for item in momentum}
        
        if not raw_scores:
            return {}
            
        # Normalize
        min_ret = min(raw_scores.values())
        max_ret = max(raw_scores.values())
        rng = max_ret - min_ret if (max_ret - min_ret) != 0 else 1.0
        
        norm_scores = {}
        for sec, val in raw_scores.items():
            # Range 0.1 to 0.9
            norm = 0.1 + ((val - min_ret) / rng) * 0.8
            norm_scores[sec] = norm
            
        _SECTOR_CACHE = {
            "last_updated": now,
            "scores": norm_scores
        }
        return norm_scores
    except Exception as e:
        logger.error(f"Error calculating sector scores: {e}")
        return {}

@router.get("/analyze/{symbol}")
def analyze_stock(symbol: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Complete analysis with broadened criteria:
    - Trending stocks (holding > Darvas box)
    - Low volume marked as High Risk (not rejected)
    """
    try:
        # STRATEGY: Prefer consistently with Dashboard (DB Signal) if available
        # This solves the mismatch where Dashboard = 61% (ML/Batch) vs Detail = 97% (Heuristic/On-fly)
        
        latest_signal = db.query(Signal).filter(
            Signal.symbol == symbol
        ).order_by(Signal.timestamp.desc()).first()
        
        # If we have a fresh signal (e.g. from today or last few days), return it directly
        # The dashboard shows signals from the last 5 days roughly.
        if latest_signal:
             from datetime import timedelta     
             # If signal is recent (within 5-7 days), trust it as the "Source of Truth"
             if (datetime.now().date() - latest_signal.timestamp.date()).days < settings.SIGNAL_MAX_AGE_DAYS:
                 
                 # Look up sector name 
                 from app.services.sector import SectorService
                 sector_service = SectorService()
                 sector_name = sector_service.sector_map.get(symbol, "Unknown")

                 # Reconstruct the response structure from the DB object
                 return {
                     "symbol": latest_signal.symbol,
                     "timestamp": latest_signal.timestamp,
                     "signal_type": latest_signal.signal_type,
                     "confidence": latest_signal.confidence,
                     "reason": latest_signal.reason,
                     "sector_score": latest_signal.sector_score,
                     "sector": sector_name,
                     # DB doesn't strictly store these bools as top-level columns usually,
                     # but we can infer or extract from 'reason' if stored there, 
                     # or default them.
                     "is_high_risk": latest_signal.reason.get('is_high_risk', False),
                     "vol_valid": latest_signal.reason.get('vol_valid', True) # Default to true if not in legacy signals
                 }

        # Fallback: Calculate on the fly if no signal exists
        # 1. Fetch data
        df = data_provider.fetch_ticker_data(symbol)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")
        
        # 2. Normalize
        df.columns = [c.lower().strip() for c in df.columns]
        if 'date' not in df.columns:
            df = df.reset_index()
            df.columns = [c.lower().strip() for c in df.columns]
        
        if 'date' not in df.columns:
            raise HTTPException(status_code=400, detail="Missing date column")
        
        # 3. Sort & limit to recent data
        df = df.sort_values('date').tail(300).reset_index(drop=True)
        
        # 5. Use SignalEngine for consistent analysis
        engine = SignalEngine(db)
        # Load sector map if needed (it's loaded in __init__)
        
        # CRITICAL FIX: Inject real Sector Scores
        # Previously we passed {}, resulting in 0 bonus
        sector_scores = get_normalized_sector_scores()
        
        analysis = engine.analyze_symbol(symbol, df, sector_scores, model=None, has_model=False)
        
        # Add Sector Name
        from app.services.sector import SectorService
        sector_service = SectorService()
        sector_name = sector_service.sector_map.get(symbol, "Unknown")
        analysis['sector'] = sector_name
        
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis error for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
def trigger_evaluation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Trigger On-Demand ML Model Evaluation.
    Runs the full validation pipeline on the latest data.
    """
    from app.services.evaluator import EvaluatorService
    try:
        service = EvaluatorService()
        results = service.run_evaluation()
        return results
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/{symbol}")
async def get_news_sentiment(symbol: str):
    """
    Returns recent news sentiment for a symbol using FinBERT NLP.
    Cached 30 minutes per symbol.
    """
    from app.services.cache_redis import get_cached, set_cached
    from app.services.news_sentiment import NewsSentimentAnalyzer

    cache_key = f"news:{symbol.upper()}"
    cached = await get_cached(cache_key)
    if cached:
        return cached

    analyzer = NewsSentimentAnalyzer()
    result = analyzer.get_signal_sentiment(symbol.upper())
    await set_cached(cache_key, result, ttl=settings.CACHE_TTL_SHORT)
    return result

@router.get("/{signal_id}/grade")
def get_signal_grade(signal_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get the graded outcome of a given signal ID.
    """
    outcome = db.query(SignalOutcome).filter(SignalOutcome.signal_id == signal_id).first()
    if not outcome:
        raise HTTPException(status_code=404, detail=f"No outcome found for signal {signal_id}")
    
    return {"grade": outcome.outcome, "pnl_percent": outcome.pnl_percent}
