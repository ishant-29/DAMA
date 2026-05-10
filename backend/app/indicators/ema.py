import pandas as pd

def ema(series: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA) for a series.
    
    Args:
        series: Input pandas Series (e.g., Close prices).
        period: EMA period (span).
        
    Returns:
        pd.Series: EMA values with the same index as the input.
    """
    if series.empty:
        return series
    return series.ewm(span=period, adjust=False).mean()

def ema_df(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    """
    Calculate multiple EMAs for a DataFrame and return them as new columns.
    
    Args:
        df: Input DataFrame containing a 'close' column (case-insensitive check recommended, assuming 'close' or 'Close').
        periods: List of EMA periods to calculate.
        
    Returns:
        pd.DataFrame: DataFrame with new columns named 'ema_{period}'.
    """
    df_out = df.copy()
    
    # helper to find close column
    close_col = None
    for col in ['close', 'Close', 'CLOSE']:
        if col in df_out.columns:
            close_col = col
            break
            
    if not close_col:
        raise ValueError("DataFrame must contain a 'close' column.")
        
    for p in periods:
        df_out[f'ema_{p}'] = ema(df_out[close_col], p)
        
    return df_out
