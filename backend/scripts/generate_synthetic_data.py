import pandas as pd
import yfinance as yf
import os
import time

def main():
    print("Fetching REAL market data using yfinance...")
    
    list_path = 'app/data/nse500_list.csv'
    if not os.path.exists(list_path):
        print(f"List not found at {list_path}")
        # Try local fallback
        list_path = 'backend/app/data/nse500_list.csv'
        if not os.path.exists(list_path):
             print(f"List not found at {list_path} either.")
             return

    try:
        list_df = pd.read_csv(list_path)
    except Exception as e:
        print(f"Error reading list: {e}")
        return

    symbols = []
    # robust symbol extraction
    if 'Symbol' in list_df.columns:
        symbols = list_df['Symbol'].tolist()
    elif 'symbol' in list_df.columns:
         symbols = list_df['symbol'].tolist()
    else:
         # Fallback to first column
         symbols = list_df.iloc[:, 0].tolist()
         
    print(f"Found {len(symbols)} symbols. Processing ALL of them (User Request).")
    
    # Prioritize user specific stocks
    priority_stocks = ['GPPL.NS', 'KAYNES.NS', 'HEROMOTOCO.NS', 'RELIANCE.NS', 'TCS.NS', 'BSE.NS', 'CDSL.NS', 'SUZLON.NS', 'IDEA.NS', 'YESBANK.NS', 'MCX.NS', 'NBCC.NS', 'HUDCO.NS', 'IRFC.NS', 'RVNL.NS', 'IEX.NS', 'JIOFIN.NS']
    
    processed_dfs = []
    
    # Filter only valid strings
    cleaned_symbols = [str(s).strip() for s in symbols if str(s).strip()]
    
    # Combine priority + subset of others to avoid rate limits/time
    # Combine priority + subset of others to avoid rate limits/time
    target_list = priority_stocks + [s for s in cleaned_symbols if s not in priority_stocks]
    
    # Ensure .NS suffix
    final_list = []
    for s in target_list:
        if not s.upper().endswith('.NS') and not s.upper().endswith('.BO'):
            s = s + '.NS'
        final_list.append(s)
        
    final_list = list(set(final_list)) # dedupe
    
    print(f"Downloading data for {len(final_list)} stocks...")
    
    for i, symbol in enumerate(final_list):
        try:
            print(f"[{i+1}/{len(final_list)}] Downloading {symbol}...", end=' ', flush=True)
            ticker = yf.Ticker(symbol)
            # Fetch 1 year data
            hist = ticker.history(period="6mo")
            
            if hist.empty:
                print("No data.")
                continue
                
            # Reset index to get Date as column
            hist = hist.reset_index()
            
            # Rename columns to standard lowercase
            hist.columns = [c.lower() for c in hist.columns]
            
            # Keep only necessary
            # yfinance returns: Date, Open, High, Low, Close, Volume, Dividends, Stock Splits
            # We strictly need: date, symbol, open, high, low, close, volume
            hist['symbol'] = symbol
            
            # yfinance Date is often datetime with timezone
            hist['date'] = pd.to_datetime(hist['date']).dt.tz_localize(None)
            
            cols_needed = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']
            existing_cols = [c for c in cols_needed if c in hist.columns]
            
            df_cleaned = hist[existing_cols]
            processed_dfs.append(df_cleaned)
            print(f"Done ({len(df_cleaned)} rows)")
            
            # Sleep slightly to be nice to API
            # time.sleep(0.1) 
            
        except Exception as e:
            print(f"Error: {e}")
            
    if not processed_dfs:
        print("No data downloaded successfully.")
        return
        
    df_final = pd.concat(processed_dfs)
    
    # Ensure output dir
    output_path = 'sample_data/nse500_sample.csv'
    os.makedirs('sample_data', exist_ok=True)
    
    if os.path.exists(output_path):
        os.remove(output_path)
        
    df_final.to_csv(output_path, index=False)
    print(f"SUCCESS: Saved {len(df_final)} rows to {output_path}")
    print("Sample:")
    print(df_final.tail())

if __name__ == "__main__":
    main()
