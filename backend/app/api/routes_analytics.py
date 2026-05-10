"""
Analytics API endpoints
"""
from dataclasses import asdict  # FIXED: S7-03 — moved from inline (run_backtest_endpoint)
from fastapi import APIRouter, Depends, Query, HTTPException  # FIXED: S7-03 — HTTPException moved from inline
from sqlalchemy.orm import Session

from app.auth import get_current_user, User
from app.core.config import settings  # FIXED: S7-03 — moved from inline (get_market_mood)
from app.db.session import get_db
from app.services.analytics import AnalyticsService  # FIXED: S7-03 — was also imported inline in get_market_mood, get_system_stats
from app.services.auditor import SignalAuditor  # FIXED: S7-03 — moved from inline (trigger_signal_audit)
from app.services.backtester import Backtester  # FIXED: S7-03 — moved from inline (run_backtest_endpoint)
from app.services.cache_redis import get_cached, set_cached  # FIXED: S7-03 — moved from inline (3 endpoints)
from app.services.regime_detector import MarketRegimeDetector  # FIXED: S7-03 — moved from inline (get_market_regime)
from app.services.sector_rotation import SectorRotationEngine  # FIXED: S7-03 — moved from inline (get_sector_rotation)

router = APIRouter()

import time
_bulk_backtest_cache = {"data": None, "ts": 0, "cap": 0}
_BULK_BACKTEST_MEM_TTL = 1800  # 30 minutes


@router.get("/performance")
async def get_performance_metrics(
    period_days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get performance metrics for specified period"""
    analytics = AnalyticsService(db)
    return analytics.get_performance_metrics(period_days)


@router.get("/calibration")
async def get_confidence_calibration(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get confidence score calibration data"""
    analytics = AnalyticsService(db)
    return {
        'calibration': analytics.get_confidence_calibration(),
        'description': 'Actual win rates by predicted confidence range'
    }


@router.get("/signal-types")
async def get_signal_type_performance(
    period_days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compare BUY vs SELL performance"""
    analytics = AnalyticsService(db)
    return analytics.get_signal_type_performance(period_days)


@router.get("/sector-performance")
async def get_sector_performance(
    period_days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get performance metrics broken down by sector"""
    analytics = AnalyticsService(db)
    return analytics.get_sector_performance(period_days)


@router.post("/audit")
async def trigger_signal_audit(
    lookback_days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger manual signal audit"""
    auditor = SignalAuditor(db)
    auditor.audit_signals(lookback_days=lookback_days)
    return {"status": "success", "message": f"Audit complete for last {lookback_days} days"}


@router.get("/market-mood")
async def get_market_mood(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get current market mood based on signal ratios from last 5 days.
    """
    analytics = AnalyticsService(db)
    # Use configurable window for market mood
    metrics = analytics.get_signal_type_performance(period_days=settings.MARKET_MOOD_WINDOW_DAYS)

    buy_count = metrics.get('BUY', {}).get('total', 0)
    sell_count = metrics.get('SELL', {}).get('total', 0)
    total = buy_count + sell_count

    if total == 0:
        return {"mood": "NEUTRAL", "score": 50, "description": "Insufficient Data"}

    buy_ratio = (buy_count / total) * 100

    if buy_ratio >= 75:
        return {"mood": "EXTREME_BULL", "score": buy_ratio, "description": "Aggressive Buying Detected"}
    elif buy_ratio >= 60:
        return {"mood": "BULL", "score": buy_ratio, "description": "Buyers in Control"}
    elif buy_ratio <= 25:
        return {"mood": "EXTREME_BEAR", "score": buy_ratio, "description": "Aggressive Selling Detected"}
    elif buy_ratio <= 40:
        return {"mood": "BEAR", "score": buy_ratio, "description": "Sellers in Control"}
    else:
        return {"mood": "NEUTRAL", "score": buy_ratio, "description": "Market is Stable/Mixed"}


@router.get("/system-stats")
async def get_system_stats(
    period: int = Query(30, alias="period_days", ge=7, le=365), # Support both or just change to period
    initial_capital: float = Query(10000.0, ge=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get holistic system performance (CAGR, Equity Curve, Drawdown).
    """
    analytics = AnalyticsService(db)
    # Map 'period' to what service expects or just update service
    return analytics.get_system_performance(period_days=period, initial_capital=initial_capital)


@router.get("/pnl-distribution")
async def get_pnl_distribution(
    period_days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get distribution of trade PnL results"""
    analytics = AnalyticsService(db)
    return analytics.get_pnl_distribution(period_days)


@router.get("/backtest/{symbol}")
async def run_backtest_endpoint(
    symbol: str,
    days: int = Query(365, ge=30, le=1095),
    current_user: User = Depends(get_current_user)
):
    """
    Run walk-forward backtest for a symbol over N days.
    Returns win rate, P&L stats, and full trade timeline.
    """
    cache_key = f"backtest:{symbol.upper()}:{days}"

    # Cache for 24 hours (expensive computation)
    try:
        cached = await get_cached(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    try:
        backtester = Backtester()
        report = backtester.run(symbol=symbol.upper(), days=days)
        result = asdict(report) if hasattr(report, '__dataclass_fields__') else report.__dict__

        try:
            await set_cached(cache_key, result, ttl=86400)
        except Exception:
            pass

        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Internal server error")  # FIXED: S3-08
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.get("/market-regime")
async def get_market_regime(current_user: User = Depends(get_current_user)):
    """Returns current market regime for dashboard display."""
    # Try cache first
    try:
        cached = await get_cached('market:regime')
        if cached:
            return cached
    except Exception:
        pass

    detector = MarketRegimeDetector()
    regime = detector.detect()

    result = {
        'regime': regime.regime,
        'india_vix': regime.india_vix,
        'nifty_above_ema50': regime.nifty_above_ema50,
        'allow_buy_signals': regime.allow_buy_signals,
        'description': regime.regime_description,
        'min_confidence': regime.min_confidence_threshold,
        'nifty_return_20d': regime.nifty_return_20d,
    }

    try:
        await set_cached('market:regime', result, ttl=5400)
    except Exception:
        pass

    return result


@router.get("/sectors")
async def get_sector_rotation():
    """Returns sector rotation momentum report."""
    try:
        cached = await get_cached('sectors:rotation')
        if cached:
            return cached
    except Exception:
        pass

    engine = SectorRotationEngine()
    report = engine.get_full_report()

    try:
        await set_cached('sectors:rotation', report, ttl=60)
    except Exception:
        pass

    return report


@router.get("/bulk-backtest")
async def get_bulk_backtest(
    initial_capital: float = Query(10000.0, ge=1000),
    current_user: User = Depends(get_current_user)
):
    """
    Run bulk backtest across all 500+ stocks using cached market data.
    Returns aggregate metrics for 7D, 30D, and 90D windows.
    Uses a 3-layer cache: in-memory (30 min) → Redis (1 hr) → recompute.
    """
    global _bulk_backtest_cache

    # Layer 1: In-memory cache (instant, no I/O)
    cap_key = int(initial_capital)
    if (
        _bulk_backtest_cache["data"] is not None
        and (time.time() - _bulk_backtest_cache["ts"]) < _BULK_BACKTEST_MEM_TTL
        and _bulk_backtest_cache.get("cap") == cap_key
    ):
        return _bulk_backtest_cache["data"]

    # Layer 2: Redis cache
    cache_key = f"bulk_backtest:{cap_key}"
    try:
        cached = await get_cached(cache_key)
        if cached:
            _bulk_backtest_cache = {"data": cached, "ts": time.time(), "cap": cap_key}
            return cached
    except Exception:
        pass

    # Layer 3: Recompute (expensive — 500+ stocks × 3 periods)
    try:
        from app.services.bulk_backtester import BulkBacktester
        backtester = BulkBacktester()
        result = backtester.run_all_periods(initial_capital=initial_capital)

        # Store in both caches
        _bulk_backtest_cache = {"data": result, "ts": time.time(), "cap": cap_key}
        try:
            await set_cached(cache_key, result, ttl=3600)  # Redis: 1 hour
        except Exception:
            pass

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk backtest failed: {str(e)}")
