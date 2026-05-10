
import pandas as pd
import os
import sys

def check_data():
    base_path = r"c:/Users/bishn/OneDrive/Desktop/project/backend/app/data"
    nse_path = os.path.join(base_path, "nse500_list.csv")
    market_path = os.path.join(base_path, "market_cache.csv")
    output_file = r"c:/Users/bishn/OneDrive/Desktop/project/backend/data_verification_output.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Checking {nse_path}...\n")
        try:
            df_nse = pd.read_csv(nse_path)
            f.write(f"Loaded NSE list. Shape: {df_nse.shape}\n")
            f.write(f"Columns: {df_nse.columns.tolist()}\n")
            # Check sector column
            cols = [c.lower().strip() for c in df_nse.columns]
            if 'sector' in cols:
                f.write(f"✅ 'sector' column found. Unique sectors: {df_nse[df_nse.columns[cols.index('sector')]].nunique()}\n")
            else:
                f.write("❌ 'sector' column NOT found!\n")
        except Exception as e:
            f.write(f"❌ Error loading NSE list: {e}\n")

        f.write(f"\nChecking {market_path}...\n")
        try:
            df_market = pd.read_csv(market_path)
            f.write(f"Loaded Market Cache. Shape: {df_market.shape}\n")
            f.write(f"Columns: {df_market.columns.tolist()}\n")
            
            if 'date' in df_market.columns and 'symbol' in df_market.columns:
                df_market['date'] = pd.to_datetime(df_market['date'], dayfirst=True, errors='coerce')
                f.write(f"Date range: {df_market['date'].min()} to {df_market['date'].max()}\n")
                
                # Check history per symbol
                counts = df_market.groupby('symbol').size()
                f.write(f"Symbols count: {len(counts)}\n")
                f.write(f"Avg days per symbol: {counts.mean()}\n")
                f.write(f"Min days: {counts.min()}, Max days: {counts.max()}\n")
                
                # Check specific symbol if possible (e.g. RELIANCE.NS)
                if 'RELIANCE.NS' in counts.index:
                    f.write(f"RELIANCE.NS has {counts['RELIANCE.NS']} days\n")
            else:
                f.write("❌ 'date' or 'symbol' column missing in market cache\n")
                
        except Exception as e:
            f.write(f"❌ Error loading Market Cache: {e}\n")
    
    print(f"Verification complete. Check {output_file}")

if __name__ == "__main__":
    check_data()
