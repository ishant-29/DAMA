import sys
import os
import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import text
import datetime
import time

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal, engine
from app.db.models import Base, Signal, Trade, DailyPerformance, SignalOutcome
from app.services.signal_engine import SignalEngine

def fetch_and_seed():
    print("Starting Live Data Fetch and Seed Process...")

    # 0. Check DB Connection
    print(f"Checking DB connection to {os.getenv('DATABASE_URL', 'default')}...")
    db = SessionLocal()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("DB Connection Successful.")
    except Exception as e:
        print(f"DB Connection Failed: {e}")
        print("Please check your DATABASE_URL environment variable.")
        print("Hint: If running locally with Docker, try port 5433 (e.g., postgresql://user:password@localhost:5433/nse_db)")
        return
    finally:
        db.close()
    
    # 1. Read Stock List
    csv_path = os.path.join(os.path.dirname(__file__), '../app/data/nse500_list.csv')
    if not os.path.exists(csv_path):
        print(f"Error: Stock list not found at {csv_path}")
        return

    print(f"Reading stock list from {csv_path}...")
    try:
        stocks_df = pd.read_csv(csv_path)
        symbols = stocks_df['symbol'].tolist()
        # Ensure symbols are clean and have .NS suffix if needed (they seem to have it in the file)
        # Verify first few
        print(f"Found {len(symbols)} stocks. Examples: {symbols[:5]}")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # 2. Fetch Data using yfinance
    print("Fetching historical data from yfinance (this may take a while)...")
    
    # We can use yf.download for bulk download. It's faster.
    # Grouping into chunks of 50 to avoid URL length issues or timeouts
    chunk_size = 50
    all_data_map = {}
    
    total_chunks = (len(symbols) + chunk_size - 1) // chunk_size
    
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i+chunk_size]
        print(f"Fetching chunk {i//chunk_size + 1}/{total_chunks}: {len(chunk)} symbols...")
        
        try:
            # Download 1 year of data
            # auto_adjust=True gets OHLC adjusted for splits/dividends which is usually good for technical analysis
            df = yf.download(chunk, period="1y", interval="1d", group_by='ticker', auto_adjust=True, progress=False, threads=True)
            
            # yf.download with group_by='ticker' returns a MultiIndex columns if > 1 ticker
            # If only 1 ticker in chunk, it returns normal columns. We need to handle both.
            
            if len(chunk) == 1:
                # Single ticker case
                sym = chunk[0]
                if df.empty:
                    print(f"No data for {sym}")
                    continue
                df['symbol'] = sym
                df = df.reset_index()
                # Rename columns to lowercase for consistency
                df.columns = [c.lower() for c in df.columns]
                all_data_map[sym] = df
            else:
                # Multi-ticker case
                for sym in chunk:
                    try:
                        sym_df = df[sym].copy()
                        if sym_df.empty or sym_df['Close'].dropna().empty:
                            print(f"No data for {sym}")
                            continue
                        
                        sym_df = sym_df.reset_index()
                        # Rename columns: Date, Open, High, Low, Close, Volume
                        sym_df.columns = [c.lower() for c in sym_df.columns]
                        
                        # Ensure 'date' is datetime
                        sym_df['date'] = pd.to_datetime(sym_df['date'])
                        
                        all_data_map[sym] = sym_df
                    except KeyError:
                        print(f"Symbol {sym} not found in response")
                        continue
                        
        except Exception as e:
            print(f"Error fetching chunk: {e}")
            # Try waiting a bit to avoid rate limits
            time.sleep(2)

    print(f"Successfully fetched data for {len(all_data_map)} symbols.")

    if not all_data_map:
        print("No data fetched. Aborting.")
        return

    # 2b. Save to market_cache.csv for Sector Heatmap
    print("Updating market_cache.csv...")
    try:
        all_dfs = []
        for sym, df in all_data_map.items():
            df_copy = df.copy()
            df_copy['symbol'] = sym
            all_dfs.append(df_copy)
        
        if all_dfs:
            cache_path = os.path.join(os.path.dirname(__file__), '../app/data/market_cache.csv')
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            full_df = pd.concat(all_dfs)
            full_df.to_csv(cache_path, index=False)
            print(f"Market Cache Updated at {cache_path}")
    except Exception as e:
        print(f"Error updating market cache: {e}")

    # 3. Clear Database
    print("Resetting database (Signals, Trades, Performance)...")
    db = SessionLocal()
    try:
        # Dropping tables via SQL to handle foreign keys
        with engine.connect() as connection:
            connection.execute(text("TRUNCATE TABLE signals CASCADE"))
            connection.execute(text("TRUNCATE TABLE trades CASCADE"))
            connection.execute(text("TRUNCATE TABLE daily_performance CASCADE"))
            connection.execute(text("TRUNCATE TABLE signal_outcomes CASCADE"))
            connection.commit()
        print("Database truncated (Signals, Trades, Performance).")
        
        # Ensure tables exist
        Base.metadata.create_all(bind=engine)
        print("Schema verified.")
        
    except Exception as e:
        print(f"Error resetting DB: {e}")
        db.close()
        return

    # 4. Generate Signals
    print("Generating signals...")
    try:
        signal_engine = SignalEngine(db)
        
        # SignalEngine expects symbols list and a dict of DataFrames
        valid_symbols = list(all_data_map.keys())
        
        signals = signal_engine.generate_signals(valid_symbols, all_data_map)
        print(f"Generated {len(signals)} signals.")
        
        # Verify
        count = db.query(Signal).count()
        print(f"VERIFICATION: Total Signals in DB: {count}")
        
    except Exception as e:
        print(f"Error generating signals: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    fetch_and_seed()
