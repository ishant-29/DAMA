"""Debug the DAMA evaluator to understand why no signals are generated."""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import yfinance as yf
import joblib

# Fetch data
symbol = 'RELIANCE'
t = yf.Ticker(f'{symbol}.NS')
df = t.history(period='6mo')
df.reset_index(inplace=True)
df.columns = [c.lower() for c in df.columns]
if 'date' in df.columns:
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)

print(f"Data rows: {len(df)}")

# Calculate indicators
df['ema_10'] = df['close'].ewm(span=10, adjust=False).mean()
df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
high, low, close = df['high'], df['low'], df['close']
prev_close = close.shift(1)
tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
df['atr_14'] = tr.ewm(alpha=1/14, adjust=False).mean()
df['atr_normalized'] = (df['atr_14'] / df['close']) * 100

# Calculate Darvas
lookback = 5
n = len(df)
darvas_high = np.full(n, np.nan)
darvas_low = np.full(n, np.nan)
darvas_breakout = np.zeros(n, dtype=bool)
darvas_breakdown = np.zeros(n, dtype=bool)
highs = df['high'].values
lows = df['low'].values
closes = df['close'].values
box_top = np.nan
for i in range(lookback, n):
    if np.isnan(box_top):
        box_top = highs[i-lookback:i].max()
        box_bottom = lows[i-lookback:i].min()
    darvas_high[i] = box_top
    darvas_low[i] = box_bottom
    if closes[i] > box_top:
        darvas_breakout[i] = True
        box_top = np.nan
    elif closes[i] < lows[i-lookback:i].min():
        darvas_breakdown[i] = True
        box_top = np.nan

df['darvas_high'] = pd.Series(darvas_high).ffill()
df['darvas_low'] = pd.Series(darvas_low).ffill()
df['darvas_breakout'] = darvas_breakout
df['darvas_breakdown'] = darvas_breakdown

# Check eligibility for multiple days
cutoff = datetime.now() - timedelta(days=90)
eligible_days = []

for i in range(60, len(df)):
    row = df.iloc[i]
    if row['date'] < cutoff:
        continue
    
    # ATR check
    if row['atr_normalized'] > 5.0:
        continue
    
    # BUY conditions
    is_above_ema10 = row['close'] > row['ema_10']
    is_breakout = bool(row['darvas_breakout'])
    is_holding_above = row['close'] >= row['darvas_high'] if not pd.isna(row['darvas_high']) else False
    
    if is_above_ema10 and (is_breakout or is_holding_above):
        eligible_days.append({
            'date': row['date'],
            'close': row['close'],
            'ema_10': row['ema_10'],
            'darvas_high': row['darvas_high'],
            'breakout': is_breakout,
            'holding': is_holding_above,
            'eligibility': 'BUY_ELIGIBLE'
        })
    
    # SELL conditions
    is_below_ema50 = row['close'] < row['ema_50']
    is_breakdown = bool(row['darvas_breakdown'])
    
    if is_below_ema50 and is_breakdown:
        eligible_days.append({
            'date': row['date'],
            'close': row['close'],
            'ema_50': row['ema_50'],
            'eligibility': 'SELL_ELIGIBLE'
        })

print(f"\nEligible days found: {len(eligible_days)}")
for day in eligible_days[:10]:
    print(day)

# Check ML threshold
print("\n--- ML Model Check ---")
artifacts_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'artifacts')
models = [f for f in os.listdir(artifacts_dir) if f.endswith('.pkl')]
print(f"Available models: {models}")
if models:
    models.sort(reverse=True)
    model_path = os.path.join(artifacts_dir, models[0])
    print(f"Using: {models[0]}")
    
    model = joblib.load(model_path)
    print(f"Model type: {type(model)}")
    
    # Get features for one eligible day
    if eligible_days:
        idx = 60
        test_df = df.iloc[:idx+1].copy()
        features = pd.DataFrame()
        features['ema_10'] = test_df['ema_10']
        features['ema_50'] = test_df['ema_50']
        features['price_ema_dist_10'] = (test_df['close'] - test_df['ema_10']) / test_df['ema_10']
        features['price_ema_dist_50'] = (test_df['close'] - test_df['ema_50']) / test_df['ema_50']
        features['darvas_breakout'] = test_df['darvas_breakout'].astype(int)
        features['darvas_breakdown'] = test_df['darvas_breakdown'].astype(int)
        features['atr_14'] = test_df['atr_14']
        features['atr_normalized'] = test_df['atr_14'] / test_df['close']
        features['volume_ratio'] = test_df['volume'] / test_df['volume'].rolling(20).mean()
        features = features.dropna()
        
        if not features.empty:
            X = features.iloc[[-1]]
            print(f"\nFeatures: {X.columns.tolist()}")
            
            if hasattr(model, 'feature_names_in_'):
                expected = list(model.feature_names_in_)
                print(f"Model expects: {expected}")
                for col in expected:
                    if col not in X.columns:
                        X[col] = 0
                X = X[expected]
            
            try:
                prob = model.predict_proba(X)
                print(f"Prediction probabilities: {prob}")
                print(f"Class 1 probability: {prob[0][1]}")
            except Exception as e:
                print(f"Error: {e}")
