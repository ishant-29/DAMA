import logging
import os
import pandas as pd
from app.db.session import SessionLocal
from app.services.signal_engine import SignalEngine
from app.services.performance_engine import PerformanceEngine
from app.services.data_provider import get_nse_500_list, fetch_all_data_map
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Track the last run times of autonomous tasks (initialized to now to prevent immediate execution on startup)
_LAST_RUNS = {
    # Initial offset: Start first refresh 5 minutes after server start (30-25=5)
    "market_refresh": datetime.now() - timedelta(minutes=25),
    "evaluation": datetime.now(),
    "paper_monitor": datetime.now()
}

def run_bulk_update_task():
    """Background task to update all symbols and regenerate signals."""
    logger.info("Starting bulk data update...")
    
    # 1. Fetch Data
    symbols = get_nse_500_list()
    if not symbols:
        logger.error("No symbols found to update.")
        return

    # Using 10 workers for faster IO
    data_map = fetch_all_data_map(symbols, max_workers=10)
    logger.info(f"Data fetch complete. Got data for {len(data_map)} symbols.")
    
    if not data_map:
        return

    # 2. Run Signal Engine
    db = SessionLocal()
    try:
        engine = SignalEngine(db)
        # Only pass symbols we actually have data for
        valid_symbols = list(data_map.keys())
        
        logger.info("Running Signal Engine on fetched data...")
        
        # Save Cached Data for Sector Analysis
        try:
            all_dfs = []
            for sym, df in data_map.items():
                if df is not None and not df.empty:
                    df = df.copy() # Avoid SettingWithCopyWarning
                    df['symbol'] = sym
                    all_dfs.append(df)
            
            if all_dfs:
                cache_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_cache.csv')
                # Ensure directory exists
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                
                full_df = pd.concat(all_dfs)
                # Final safety check before CSV
                full_df.to_csv(cache_path, index=False)
                logger.info(f"Market Data Cached to {cache_path}")
        except Exception as e:
            logger.error(f"Failed to cache market data: {e}", exc_info=True)

        signals = engine.generate_signals(valid_symbols, data_map)
        logger.info(f"Signal Generation Complete. Generated {len(signals)} signals.")
        
        # 3. Running Performance Engine (New Logic)
        try:
            logger.info("Starting Performance Engine Cycle...")
            perf_engine = PerformanceEngine(db)
            perf_engine.run_daily_cycle(signals, data_map)
            logger.info("Performance Engine Cycle Complete.")
        except Exception as e:
            logger.error(f"Error in Performance Engine: {e}")
            
    except Exception as e:
        logger.error(f"Error in signal generation task: {e}")
        
    finally:
        db.close()


def run_realtime_cache_update():
    """Lighter version of update to refresh the market cache more frequently."""
    logger.info("Starting real-time market cache update...")
    try:
        symbols = get_nse_500_list()
        if not symbols:
            logger.error("No symbols found to update.")
            return

        # Fetch last 1 month for the heatmap calculation (ensures 5 trading days after holidays)
        data_map = fetch_all_data_map(symbols, max_workers=10, period="1mo")
        logger.info(f"Real-time fetch complete. Got data for {len(data_map)} symbols.")
        
        if not data_map:
            return

        all_dfs = []
        for sym, df in data_map.items():
            df['symbol'] = sym
            all_dfs.append(df)
        
        if all_dfs:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            cache_path = os.path.join(current_dir, '..', 'data', 'market_cache.csv')
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            # Concatenate and save
            full_df = pd.concat(all_dfs)
            full_df.to_csv(cache_path, index=False)
            logger.info(f"Real-time Market Data Refreshed at {cache_path}")
            return True
            
    except Exception as e:
        logger.error(f"Error in real-time cache update: {e}", exc_info=True)
        return False

def run_autonomous_cycle():
    """
    Core autonomous loop. Runs every few seconds but tasks have cooldowns.
    """
    global _LAST_RUNS
    now = datetime.now()
    # Debug log to verify execution
    logger.info(f"==> Autonomous Cycle Check at {now}")
    db = SessionLocal()
    
    try:
        # 1. Paper Trading Monitoring (Every 10 min during market hours - roughly)
        if not _LAST_RUNS["paper_monitor"] or (now - _LAST_RUNS["paper_monitor"]) > timedelta(minutes=10):
            logger.info("Autonomous: Running Paper Trading Monitor...")
            from app.services.paper_trader import PaperTradingEngine
            engine = PaperTradingEngine()
            engine.monitor_open_positions(db)
            _LAST_RUNS["paper_monitor"] = now

        # 2. Market Data & Signal Refresh (Every 30 min)
        # This replaces the manual "Refresh System" trigger
        if (now - _LAST_RUNS["market_refresh"]) > timedelta(minutes=30):
            logger.info("==> Autonomous: Running Full Market & Signal Refresh...")
            run_bulk_update_task()
            _LAST_RUNS["market_refresh"] = now

        # 3. ML Signal Evaluation (Every 30 min)
        if not _LAST_RUNS["evaluation"] or (now - _LAST_RUNS["evaluation"]) > timedelta(minutes=30):
            logger.info("Autonomous: Running Signal Evaluation...")
            from app.services.evaluator import EvaluatorService
            eval_service = EvaluatorService()
            eval_service.run_evaluation()
            _LAST_RUNS["evaluation"] = now
            
    except Exception as e:
        logger.error(f"Error in autonomous cycle: {e}")
    finally:
        db.close()

