from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Signal
from app.services.sector import SectorService
from app.auth import get_current_user, User  # FIXED: S3-04 — add auth import
import pandas as pd
import os
from collections import defaultdict
import logging
logger = logging.getLogger(__name__)  # FIXED: S2-03 — replace print with logger

router = APIRouter()
sector_service = SectorService()

@router.get("/momentum")
def get_sector_momentum(current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """
    Get top 2 gainers and top 2 losers based on strict 5-day return.
    """
    return sector_service.get_top_momentum_sectors()

# We use SectorService for the map now to prevent duplicate mapping logic

@router.get("/sentiment")
def get_sector_sentiment(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    sector_service.load_sector_map()
    
    # Calculate Real Price Performance from Sample Data
    sector_performance = defaultdict(list)
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Use generated cache from Live Update
        data_path = os.path.join(current_dir, '..', 'data', 'market_cache.csv')
        
        if os.path.exists(data_path):
            df = pd.read_csv(data_path)
            # Ensure date sorted - Handle various formats cleanly
            df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')
            df.dropna(subset=['date'], inplace=True)
            df.sort_values(['symbol', 'date'], inplace=True)
            
            # Debug: Check if we have data
            # print(f"DEBUG: Loaded market cache with {len(df)} rows. Unique symbols: {df['symbol'].nunique()}")
            
            # Group by symbol and take last 5 days
            processed_count = 0
            match_count = 0
            
            for sym, group in df.groupby('symbol'):
                if len(group) < 2:
                    continue
                
                # Ensure enough data for 5 days, else use what's available
                available_days = len(group)
                lookback = min(5, available_days)
                
                # Calculate return: (Latest - Previous) / Previous
                last_close = group.iloc[-1]['close']
                prev_close = group.iloc[-lookback]['close']
                
                if prev_close == 0 or pd.isna(prev_close):
                    continue
                    
                pct_change = ((last_close - prev_close) / prev_close) * 100
                
                # Assert Sector
                base_sym = sym.replace('.NS', '')
                sec = sector_service.sector_map.get(base_sym)
                if not sec and sym in sector_service.sector_map:
                    sec = sector_service.sector_map[sym]
                
                if sec and sec != "Unknown":
                    sector_performance[sec].append(pct_change)
                    match_count += 1
                processed_count += 1
                
            logger.debug(f"Processed {processed_count} symbols for performance. Matched {match_count} to sectors.")  # FIXED: S2-03
            logger.debug(f"Sectors with performance data: {list(sector_performance.keys())}")  # FIXED: S2-03
                    
    except Exception as e:
        logger.error(f"Error calculating sector performance: {e}", exc_info=True)  # FIXED: S2-03
        import traceback
        traceback.print_exc()

    # Get all signals
    # Get all signals - FILTER BY TODAY to match Dashboard
    # Get all signals - FILTER BY TODAY to match Dashboard
    from datetime import datetime, timedelta
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    logger.debug(f"Filtering signals from {today_start}")  # FIXED: S2-03
    
    signals = db.query(Signal).filter(Signal.timestamp >= today_start).all()
    logger.debug(f"Found {len(signals)} signals for today.")  # FIXED: S2-03
    
    # Fallback if empty (consistency with dashboard)
    if not signals:
         logger.debug("No signals found for today. Attempting fallback to latest available date.")  # FIXED: S2-03
         latest_sig = db.query(Signal).order_by(Signal.timestamp.desc()).first()
         if latest_sig:
             latest_date = latest_sig.timestamp.date()
             logger.debug(f"Latest signal date in DB is {latest_date}")  # FIXED: S2-03
             day_start = datetime.combine(latest_date, datetime.min.time())
             signals = db.query(Signal).filter(Signal.timestamp >= day_start).all()
             logger.debug(f"Found {len(signals)} signals for {latest_date} (fallback).")  # FIXED: S2-03
         else:
             logger.debug("No signals in DB at all.")  # FIXED: S2-03
    sector_scores = defaultdict(lambda: {'buys': 0, 'sells': 0})
    
    mapped_count = 0
    unknown_count = 0
    
    for sig in signals:
        sym = sig.symbol
        base_sym = sym.replace('.NS', '')
        sec = sector_service.sector_map.get(base_sym, "Unknown")
        if sec == "Unknown" and sym in sector_service.sector_map:
            sec = sector_service.sector_map[sym]
            
        if sec != "Unknown":
            mapped_count += 1
        else:
            unknown_count += 1
            
        stype = str(sig.signal_type).upper()
        if stype == "BUY":
            sector_scores[sec]['buys'] += 1
        elif stype == "SELL":
            sector_scores[sec]['sells'] += 1
        else:
            # Debug unusual signal types
            # print(f"DEBUG: Unknown signal type {sig.signal_type}")
            pass
            
    logger.debug(f"Signal Mapping - Mapped: {mapped_count}, Unknown: {unknown_count}")  # FIXED: S2-03
    
    # Debug total buys/sells found
    total_buys = sum(s['buys'] for s in sector_scores.values())
    total_sells = sum(s['sells'] for s in sector_scores.values())
    logger.debug(f"Total Buys: {total_buys}, Total Sells: {total_sells}")  # FIXED: S2-03
            
    # Format output
    results = []
    
    for sec, total_stocks in sector_service.sector_counts.items():
        stats = sector_scores.get(sec, {'buys': 0, 'sells': 0})
        
        # Calculate Average Sector Performance
        perfs = sector_performance.get(sec, [])
        # Ensure perfs doesn't contain NaNs
        perfs = [p for p in perfs if not pd.isna(p)]
        avg_change = sum(perfs) / len(perfs) if perfs else 0.0
        
        # Use performance as score if available, else fall back to buy/sell ratio
        # User requested "movement in stock", so avg_change is the key metric now.
        score = avg_change if avg_change is not None else 0.0
            
        results.append({
            "sector": sec,
            "score": round(float(score or 0.0), 2), # Now represents Avg % Change
            "buys": stats['buys'],
            "sells": stats['sells'],
            "total_stocks": total_stocks,
            "avg_change_percent": round(float(avg_change or 0.0), 2)
        })
        
    
    # Sort by Score (Performance) desc
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results

@router.get("/{sector_name}/stocks")
def get_sector_stocks(sector_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    sector_service.load_sector_map()
    
    # URL decode if needed (FastAPI handles path param decoding usually)
    # Find all symbols in this sector
    # Find unique canonical symbols in this sector
    # We filter by .NS to avoid duplicate entries for the same stock (e.g. JKPAPER and JKPAPER.NS)
    symbols = sorted(list(set(
        sym if ".NS" in sym else f"{sym}.NS" 
        for sym, sec in sector_service.sector_map.items() 
        if sec.lower() == sector_name.lower()
    )))
    
    stock_data = []
    
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(current_dir, '..', 'data', 'market_cache.csv')
        
        if os.path.exists(data_path):
            df = pd.read_csv(data_path)
            # Filter for our symbols
            # Optimize: Get last row for each symbol
            df['date'] = pd.to_datetime(df['date'])
            df.sort_values(['symbol', 'date'], inplace=True)
            
            for sym in symbols:
                # The CSV uses NSE suffix usually, check sector map keys
                # SECTOR_MAP keys are usually stripped (e.g. RELIANCE) or with .NS?
                # load_sector_map uses `str(row['symbol']).strip()`. CSV usually has RELIANCE.
                # market_cache has RELIANCE.NS. Steps:
                
                # Try with .NS
                lookup_sym = sym if ".NS" in sym else f"{sym}.NS"
                
                group = df[df['symbol'] == lookup_sym]
                if group.empty:
                    # Try without .NS just in case
                    group = df[df['symbol'] == sym]
                    
                if not group.empty:
                    last_close = group.iloc[-1]['close']
                    change_p = 0.0
                    
                    if len(group) >= 2:
                        available_days = len(group)
                        lookback = min(5, available_days)
                        prev_close = group.iloc[-lookback]['close']
                        if prev_close != 0 and not pd.isna(prev_close):
                            change_p = ((last_close - prev_close) / prev_close) * 100
                        
                    stock_data.append({
                        "symbol": sym,
                        "price": float(last_close),
                        "change": float(change_p)
                    })
                else:
                    # Symbol in list but no cache data
                    stock_data.append({
                        "symbol": sym,
                        "price": 0.0,
                        "change": 0.0
                    })
    except Exception as e:
        logger.error(f"Error fetching sector stocks: {e}", exc_info=True)  # FIXED: S2-03
        # Return basic list if cache fails
        for sym in symbols:
            stock_data.append({"symbol": sym, "price": 0.0, "change": 0.0})

    # Sort by performance desc
    stock_data.sort(key=lambda x: x['change'], reverse=True)
    return stock_data
