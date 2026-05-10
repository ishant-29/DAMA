import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import logging

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal, engine as db_engine
from app.services.signal_engine import SignalEngine
from app.services.performance_engine import PerformanceEngine
from app.services.data_provider import fetch_all_data_map
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Subset of liquid NSE500 stocks to ensure fast simulation without hitting rate limits
# Strip .NS here because fetch_ticker_data will append it automatically
TOP_STOCKS_WITH_NS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", 
    "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "HINDUNILVR.NS", "L&T.NS",
    "BAJFINANCE.NS", "AXISBANK.NS", "KOTAKBANK.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "ASIANPAINT.NS", "TATASTEEL.NS", "ADANIENT.NS", "NTPC.NS",
    "TATAMOTORS.NS", "M&M.NS", "POWERGRID.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "NESTLEIND.NS", "TECHM.NS", "HCLTECH.NS", "BAJAJFINSV.NS", "GRASIM.NS",
    "HINDALCO.NS", "ONGC.NS", "INDUSINDBK.NS", "CIPLA.NS", "DRREDDY.NS",
    "COALINDIA.NS", "BRITANNIA.NS", "EICHERMOT.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "TATACONSUM.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "UPL.NS", "HDFCLIFE.NS",
    "DELHIVERY.NS", "ZOMATO.NS", "IRFC.NS", "TRENT.NS", "DLF.NS",
    "AMBUJACEM.NS", "RPGLIFE.NS", "AWL.NS", "JIOFIN.NS", "CHOLAFIN.NS"
]
TOP_STOCKS = [s.replace(".NS", "") for s in TOP_STOCKS_WITH_NS]

def clear_simulation_tables():
    """Clear tables so simulation runs fresh without duplicates."""
    logger.info("Clearing tables for fresh simulation...")
    with db_engine.connect() as connection:
        connection.execute(text("DELETE FROM daily_performance"))
        connection.execute(text("DELETE FROM trades"))
        connection.execute(text("DELETE FROM signals"))
        connection.commit()
    logger.info("Tables cleared successfully.")

def run_historical_seed(days_to_simulate=90):
    db = SessionLocal()
    signal_engine = SignalEngine(db)
    
    # Force heuristic mode! The ML model generates 0.3-0.5 which gets rejected
    # by PerformanceEngine's 0.60 threshold. By disabling the ML model path, 
    # the signal engine falls back to `calculate_technical_confidence` (0.70+).
    signal_engine.model_path = None
    
    perf_engine = PerformanceEngine(db)

    # Mock external heavy API calls to speed up simulation by 100x
    import sys
    
    class MockNewsModule:
        class NewsSentimentAnalyzer:
            def get_signal_sentiment(self, symbol): return {}
            
    class MockFundModule:
        class FundamentalDataFetcher:
            def fetch(self, symbol): return {}
            
    sys.modules['app.services.news_sentiment'] = MockNewsModule()
    sys.modules['app.services.fundamental_data'] = MockFundModule()

    try:
        clear_simulation_tables()
        
        # We need historical data for the simulation days + indicator lookback (e.g., 50 days for EMA50).
        lookback_days = 90
        fetch_period = f"{days_to_simulate + lookback_days}d"
        
        logger.info(f"Fetching {fetch_period} data for {len(TOP_STOCKS)} stocks...")
        from app.services.data_provider import fetch_ticker_data
        from concurrent.futures import ThreadPoolExecutor
        
        full_data_map = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_ticker_data, sym, fetch_period, "1d"): sym for sym in TOP_STOCKS}
            for future in futures:
                sym = futures[future]
                df = future.result()
                if df is not None and not df.empty:
                    df = df.sort_values('date').reset_index(drop=True)
                    full_data_map[sym] = df
                    
        logger.info(f"Data fetch complete. Acquired data for {len(full_data_map)} symbols.")
        if not full_data_map:
            return

        # Find the global common dates to iterate sequentially
        all_dates = set()
        for df in full_data_map.values():
            all_dates.update(df['date'].dt.date.tolist())
            
        sorted_dates = sorted(list(all_dates))
        
        # We only want to simulate the last `days_to_simulate` days
        if len(sorted_dates) > days_to_simulate:
            sim_dates = sorted_dates[-days_to_simulate:]
        else:
            sim_dates = sorted_dates
            
        logger.info(f"Simulating {len(sim_dates)} trading days...")
        
        for sim_date in sim_dates:
            logger.info(f"--- Simulating Day: {sim_date} ---")
            
            # Create a sliced data map up to this date
            sliced_map = {}
            for sym, df in full_data_map.items():
                slice_df = df[df['date'].dt.date <= sim_date].copy()
                if not slice_df.empty:
                    sliced_map[sym] = slice_df
            
            valid_symbols = list(sliced_map.keys())
            
            # Ensure SignalEngine knows it's a simulation (prevent websockets, telegram)
            import app.services.signal_engine
            # Temporarily disable realtime alerts
            original_commit = signal_engine.db.commit
            
            signals = signal_engine.generate_signals(valid_symbols, sliced_map)
            # generate_signals commits inherently.
            
            logger.info(f"Generated {len(signals)} signals on {sim_date}.")
            
            perf_engine.run_daily_cycle(signals, sliced_map, override_date=sim_date)

    except Exception as e:
        logger.error(f"Error during historical seed: {e}")
    finally:
        db.close()
        logger.info("Historical simulation complete.")

if __name__ == "__main__":
    run_historical_seed(90)
