
import sys
import os
import pandas as pd
from sqlalchemy import text
import logging
import time

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal, engine
from app.db.models import Base
from app.services.signal_engine import SignalEngine
from app.services import data_provider

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_signals_only():
    print("Cleaning SIGNALS table only (Keeping Users/History)...")
    try:
        with engine.connect() as connection:
            connection.execute(text("TRUNCATE TABLE signals CASCADE"))
            connection.commit()
        print("Signals table truncated.")
    except Exception as e:
        print(f"Error cleaning DB: {e}")

def fetch_and_seed_live_strict():
    print("Fetching LIVE data via yfinance for NSE 500 list (STRICT MODE)...")
    
    # 1. Get List of Stocks from CSV
    try:
        csv_path = 'app/data/nse500_list.csv'
        if not os.path.exists(csv_path):
             csv_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'data', 'nse500_list.csv')
             
        df = pd.read_csv(csv_path)
        all_symbols = df['symbol'].tolist()
        print(f"Loaded {len(all_symbols)} symbols from {csv_path}")
    except Exception as e:
        print(f"Failed to load NSE list: {e}")
        return

    target_symbols = [s.strip() for s in all_symbols if isinstance(s, str)]
    
    # Batch processing
    batch_size = 50
    total = len(target_symbols)
    
    db = SessionLocal()
    engine = SignalEngine(db)
    
    try:
        for i in range(0, total, batch_size):
            batch = target_symbols[i:i+batch_size]
            print(f"Processing Batch {i//batch_size + 1}: {len(batch)} symbols ({i}-{i+len(batch)}/{total})...")
            
            data_map = data_provider.fetch_all_data_map(batch, max_workers=10)
            
            if data_map:
                print(f"  generating signals for {len(data_map)} stocks...")
                signals = engine.generate_signals(list(data_map.keys()), data_map)
                print(f"  + Generated {len(signals)} signals in this batch.")
            
            time.sleep(1)
            
    except Exception as e:
        print(f"Error in fetch/generate loop: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_signals_only()
    fetch_and_seed_live_strict()
