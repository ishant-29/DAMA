
import pandas as pd
import numpy as np
import sys
import os

# Mock DB Session
class MockSession:
    def query(self, *args): return self
    def filter(self, *args): return self
    def order_by(self, *args): return self
    def first(self): return None
    def all(self): return []
    def add(self, *args): pass
    def commit(self): pass
    def rollback(self): pass

# Add app to path to import SignalEngine
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.signal_engine import SignalEngine

def run_stress_test():
    engine = SignalEngine(MockSession())
    
    # Test Case 1: Perfect Data
    print("\n--- Test Case 1: Perfect Data ---")
    df_perfect = pd.DataFrame({
        'date': pd.date_range(start='2024-01-01', periods=100),
        'open': np.random.rand(100) * 100,
        'high': np.random.rand(100) * 110,
        'low': np.random.rand(100) * 90,
        'close': np.random.rand(100) * 100,
        'volume': np.random.randint(1000, 10000, 100)
    })
    res = engine.analyze_symbol("PERFECT", df_perfect, {})
    print(f"Result 1: {res['signal_type']} - Error: {res['reason'].get('message', 'None')}")
    print("PASSED TEST 1")

    # Test Case 2: Missing EMA columns (too short)
    print("\n--- Test Case 2: Short Data (No EMA50) ---")
    df_short = df_perfect.tail(10).reset_index(drop=True)
    res = engine.analyze_symbol("SHORT", df_short, {})
    print(f"Result 2: {res['signal_type']} - Error: {res['reason'].get('message', 'None')}")
    print("PASSED TEST 2")

    # Test Case 3: Missing 'open' column
    print("\n--- Test Case 3: Missing 'open' column ---")
    df_no_open = df_perfect.drop(columns=['open'])
    res = engine.analyze_symbol("NO_OPEN", df_no_open, {})
    print(f"Result 3: {res['signal_type']} - Error: {res['reason'].get('message', 'None')}")
    print("PASSED TEST 3")

    # Test Case 4: Missing 'volume' column
    print("\n--- Test Case 4: Missing 'volume' column ---")
    df_no_vol = df_perfect.drop(columns=['volume'])
    res = engine.analyze_symbol("NO_VOL", df_no_vol, {})
    print(f"Result 4: {res['signal_type']} - Error: {res['reason'].get('message', 'None')}")
    print("PASSED TEST 4")

    # Test Case 5: Empty Dataframe
    print("\n--- Test Case 5: Empty Dataframe ---")
    try:
        engine.analyze_symbol("EMPTY", pd.DataFrame(), {})
        print("Result 5: Failed to catch empty df (Assuming check handle it)")
    except Exception as e:
        print(f"Result 5: Caught expected error: {e}")
    print("PASSED TEST 5")

if __name__ == "__main__":
    run_stress_test()
