
import sys
import os
import pandas as pd
from sqlalchemy import text
import logging

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.services.signal_engine import SignalEngine
from app.services import data_provider

# Setup Logging
logging.basicConfig(level=logging.INFO)

def debug_stock(symbol):
    print(f"DEBUGGING: {symbol} ...")
    
    # 1. Fetch Data
    print("Fetching data...")
    df = data_provider.fetch_ticker_data(symbol)
    
    if df is None or df.empty:
        print("CRITICAL: Failed to fetch any data for HINDCOPPER.NS")
        return

    print("Data Fetched. Last 5 rows:")
    print(df.tail())
    
    # 2. Run Signal Engine
    db = SessionLocal()
    engine = SignalEngine(db)
    
    # Manually calculate indicators to show user
    print("\n--- Manual Indicator Check ---")
    data_map = {symbol: df}
    
    # Use internal method to add indicators
    # Note: engine.generate_signals calls indicators internally but relies on loop.
    # We will call generate_signals and capture stdout.
    
    print("\n--- Running Engine Signal Generation ---")
    signals = engine.generate_signals([symbol], data_map)
    
    print(f"\n--- Result: {len(signals)} Signals Generated ---")
    for s in signals:
        print(f"SIGNAL: {s.signal_type} | Conf: {s.confidence}")
        
    db.close()

if __name__ == "__main__":
    debug_stock("HINDCOPPER.NS")
