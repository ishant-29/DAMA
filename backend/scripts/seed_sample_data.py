import sys
import os
import pandas as pd
from sqlalchemy.orm import Session

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.services.signal_engine import SignalEngine
from app.db.models import Signal



def seed():
    print("Seeding data...")
    db: Session = SessionLocal()
    try:
        # Load sample csv
        path = os.getenv("SAMPLE_DATA_PATH", "sample_data/nse500_sample.csv")
        if not os.path.exists(path):
            print(f"Sample data not found at {path}")
            return
            
        df = pd.read_csv(path)
        df['date'] = pd.to_datetime(df['date'])
        
        # Validate Schema first
        # Clear existing signals to avoid duplicates/stale data
        # Validate Schema / Reset Table
        # Drop table to ensure schema update (new columns)
        from sqlalchemy import text
        from app.db.session import engine
        from app.db.models import Base
        
        try:
             # Dropping table requires commit/connection management
             # Using engine connection
             with engine.connect() as connection:
                 connection.execute(text("DROP TABLE IF EXISTS signals CASCADE"))
                 connection.commit()
             print("Dropped existing signals table.")
             
             # Recreate
             Base.metadata.create_all(bind=engine)
             print("Recreated signals table with new schema.")
             
        except Exception as e:
            print(f"Warning dropping/creating table: {e}")
            
        # Re-init session after DDL
        db.close()
        db = SessionLocal() 


        # Generate Signals
        print("Generating signals from sample data...")
        engine = SignalEngine(db)
        # Group by symbol
        data_map = {sym: group for sym, group in df.groupby('symbol')}
        
        # --- DEBUG: INJECT PERFECT SIGNALS ---
        # Force AMBUJACEM.NS to be a perfect BUY (Boost Volume)
        if 'AMBUJACEM.NS' in data_map:
            print("Injecting perfect BUY signal for AMBUJACEM.NS")
            df_rel = data_map['AMBUJACEM.NS'].copy()
            df_rel = df_rel.sort_values('date').reset_index(drop=True)
            
            # 1. Boost Volume (4x average)
            avg_vol = df_rel['volume'].iloc[-21:-1].mean()
            if pd.isna(avg_vol) or avg_vol == 0: avg_vol = 100000
            df_rel.loc[df_rel.index[-1], 'volume'] = int(avg_vol * 5.0)
            
            # 2. Boost Price (Ensure Breakout holds)
            # REVERTING PRICE CHANGE: Original data already had breakout. 
            # modifying price might have broken it.
            # recent_high = df_rel['high'].iloc[-20:-1].max()
            # ...
            
            data_map['AMBUJACEM.NS'] = df_rel

        # Force RPGLIFE.NS to be a perfect BUY
        if 'RPGLIFE.NS' in data_map:
            print("Injecting perfect BUY signal for RPGLIFE.NS")
            df_tcs = data_map['RPGLIFE.NS'].copy()
            df_tcs = df_tcs.sort_values('date').reset_index(drop=True)
            
            # 1. Boost Volume
            avg_vol = df_tcs['volume'].iloc[-21:-1].mean()
            if pd.isna(avg_vol) or avg_vol == 0: avg_vol = 100000
            df_tcs.loc[df_tcs.index[-1], 'volume'] = int(avg_vol * 5.0)
            
            data_map['RPGLIFE.NS'] = df_tcs
        # -------------------------------------
        symbols = list(data_map.keys())
        
        signals = engine.generate_signals(symbols, data_map)
        print(f"Generated {len(signals)} signals.")
        
        # Verify persistence
        count = db.query(Signal).count()
        print(f"VERIFICATION: Total Signals in DB: {count}")
        
    except Exception as e:
        print(f"Error seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
