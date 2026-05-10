from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
import pandas as pd
import logging
import os
from app.services import data_provider
from app.auth import get_current_user, User  # FIXED: S3-04 — add auth import

router = APIRouter()
logger = logging.getLogger(__name__)

# 4-hour cache TTL for daily chart data (changes at most once per market day)
_HISTORICAL_CACHE_TTL = 14400

@router.get("/historical")
async def get_historical_data(symbol: str, current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """
    Fetch historical data for a symbol using yfinance.
    Results are Redis-cached for 4 hours (daily OHLCV data changes at most once per session).
    """
    from app.services.cache_redis import get_cached, set_cached
    import math

    cache_key = f"historical:{symbol.upper()}"

    # --- Redis cache check (returns instantly if hit) ---
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        # Fetch data via service
        df = data_provider.fetch_ticker_data(symbol)
        
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        # Calculate Indicators
        df = df.sort_values('date').reset_index(drop=True)
        df['ema_10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

        # Darvas Box Proxy (Using Shared Logic for Consistency)
        from app.indicators.darvas import darvas_boxes
        df = darvas_boxes(df)

        # Format for frontend with explicit type casting and NaN handling
        def safe_float(val):
            if pd.isna(val): return None
            try:
                vf = float(val)
                if math.isnan(vf) or math.isinf(vf): return None
                return vf
            except:
                return None

        result = [
            {
                "name": row['date'].strftime("%Y-%m-%d"),
                "price": safe_float(row['close']),
                "ema10": safe_float(row['ema_10']),
                "ema20": safe_float(row['ema_20']),
                "ema50": safe_float(row['ema_50']),
                "box_high": safe_float(row['darvas_high']),
                "box_low": safe_float(row['darvas_low'])
            }
            for _, row in df.iterrows()
        ]

        # --- Store in Redis (4h TTL — daily data doesn't change intraday) ---
        await set_cached(cache_key, result, ttl=_HISTORICAL_CACHE_TTL)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_historical_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")  # FIXED: S3-08

@router.get("/stocks")
def get_stock_list(current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """
    Returns the list of NSE 500 symbols.
    """
    try:
        symbols = data_provider.get_nse_500_list()
        return symbols
    except Exception as e:
        logger.error(f"Error fetching stock list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")  # FIXED: S3-08

from app.services.update_service import run_bulk_update_task


# Track last update request to prevent abuse
_last_update_request = {"time": None, "count": 0}


@router.post("/update")
def update_data(background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """
    Triggers a background task to fetch fresh data for all NSE 500 stocks.
    Rate limited to prevent abuse (max 1 request per 10 minutes).
    """
    from datetime import datetime, timedelta
    global _last_update_request
    
    now = datetime.now()
    if _last_update_request["time"]:
        elapsed = (now - _last_update_request["time"]).total_seconds()
        if elapsed < 600:  # 10 minutes
            raise HTTPException(
                status_code=429,
                detail=f"Rate limited. Please wait {int(600 - elapsed)} seconds before next update."
            )
    
    _last_update_request = {"time": now, "count": _last_update_request["count"] + 1}
    background_tasks.add_task(run_bulk_update_task)
    return {"message": "Bulk data update started in background", "status": "processing"}
