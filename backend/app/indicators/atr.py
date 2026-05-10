import pandas as pd
import numpy as np

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    Args:
        df: DataFrame with 'high', 'low', 'close'.
        period: ATR period.
        
    Returns:
        pd.Series: ATR values.
    """
    cols = {c.lower(): c for c in df.columns}
    high = df[cols['high']]
    low = df[cols['low']]
    close = df[cols['close']]
    
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Wilder's Smoothing
    return tr.ewm(alpha=1/period, adjust=False).mean()

def true_range(df: pd.DataFrame) -> pd.Series:
    cols = {c.lower(): c for c in df.columns}
    high = df[cols['high']]
    low = df[cols['low']]
    close = df[cols['close']]
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
