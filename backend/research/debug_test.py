import yfinance as yf
import pandas as pd
import numpy as np

# Fetch data
t = yf.Ticker('RELIANCE.NS')
df = t.history(period='6mo')
df.reset_index(inplace=True)
df.columns = [c.lower() for c in df.columns]
if 'date' in df.columns:
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)

print(f'Data rows: {len(df)}')

# Calculate EMA
df['ema_10'] = df['close'].ewm(span=10, adjust=False).mean()
df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

# Check conditions
latest = df.iloc[-1]
print(f'Close: {latest["close"]:.2f}')
print(f'EMA10: {latest["ema_10"]:.2f}')
print(f'EMA50: {latest["ema_50"]:.2f}')
print(f'Close > EMA10: {latest["close"] > latest["ema_10"]}')

# Also check the cutoff date
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(days=90)
filtered = df[df['date'] >= cutoff]
print(f'Rows after cutoff: {len(filtered)}')
