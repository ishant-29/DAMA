
import sys
import os
import pandas as pd
import logging

# Setup mocking for API call context
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging to stdout
logging.basicConfig(level=logging.DEBUG)

from app.services import data_provider
from app.indicators.ema import ema_df
from app.indicators.darvas import darvas_boxes

def debug_analysis(symbol):
    print(f"DEBUGGING ANALYSIS FOR: {symbol}")
    try:
        # A. Fetch Data
        print("1. Fetching data...")
        df = data_provider.fetch_ticker_data(symbol)
        
        if df is None:
            print("ERROR: df is None")
            return
        
        print(f"Data fetched. Shape: {df.shape}")
        if df.empty:
            print("ERROR: df is empty")
            return
            
        print("Columns:", df.columns)
        print("Head:", df.head(1).to_dict())
        
        # B. Normalize Logic (from routes_signals.py)
        print("2. Normalizing...")
        df.columns = [c.lower().strip() for c in df.columns]
        if 'date' not in df.columns:
            df = df.reset_index()
            df.columns = [c.lower().strip() for c in df.columns]
            
        print("Normalized Columns:", df.columns)
        
        # C. Indicator Calculation
        print("3. Calculating Indicators...")
        df = ema_df(df, [10, 20, 50])
        print("EMA done.")
        df = darvas_boxes(df)
        print("Darvas done.")
        
        latest = df.iloc[-1]
        print("Latest Row:", latest.to_dict())
        
        print("SUCCESS: Analysis logic completed without error.")
        
    except Exception as e:
        print(f"CRITICAL EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_analysis("GODREJCP.NS")
