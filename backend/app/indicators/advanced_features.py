"""
Advanced feature engineering for NSE Signal Engine.
Adds high-alpha technical and market-context features to the ML pipeline.
"""

import pandas as pd
import numpy as np
from typing import Optional


def calculate_relative_strength(stock_df: pd.DataFrame, nifty_df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    RS = Stock Return / Nifty Return over `period` days.
    RS > 1.0 means stock is outperforming the index — strong buy context.
    """
    stock_return = stock_df['Close'].pct_change(period)
    nifty_return = nifty_df['Close'].pct_change(period)
    rs = stock_return / nifty_return.replace(0, np.nan)
    return rs.fillna(1.0).rename('relative_strength')


def calculate_52w_high_proximity(df: pd.DataFrame) -> pd.Series:
    """
    Proximity to 52-week high as a percentage.
    proximity = (52W_High - Close) / 52W_High
    Values near 0 = trading near highs (breakout zone).
    """
    rolling_high = df['Close'].rolling(window=252, min_periods=50).max()
    proximity = (rolling_high - df['Close']) / rolling_high
    return proximity.fillna(0.5).rename('proximity_52w_high')


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range — measures volatility.
    Used for stop-loss placement and position sizing.
    """
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr.rename('atr_14')


def calculate_atr_ratio(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR as % of price — normalized volatility for cross-stock comparison."""
    atr = calculate_atr(df, period)
    return (atr / df['Close']).rename('atr_ratio')


def calculate_bollinger_width(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Bollinger Band Width = (Upper - Lower) / Middle.
    Low width (squeeze) before breakout = explosive move signal.
    """
    middle = df['Close'].rolling(period).mean()
    std = df['Close'].rolling(period).std()
    upper = middle + 2 * std
    lower = middle - 2 * std
    width = (upper - lower) / middle
    return width.fillna(0).rename('bollinger_width')


def calculate_obv(df: pd.DataFrame) -> pd.Series:
    """
    On-Balance Volume — tracks institutional accumulation.
    Rising OBV + flat price = smart money accumulating quietly.
    """
    direction = np.sign(df['Close'].diff())
    obv = (direction * df['Volume']).fillna(0).cumsum()
    return obv.rename('obv')


def calculate_obv_slope(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """OBV slope over N days — positive slope = accumulation phase."""
    obv = calculate_obv(df)
    slope = obv.diff(period) / period
    return slope.fillna(0).rename('obv_slope')


def calculate_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Today's volume vs N-day average.
    Ratio > 2.5 on a breakout day = institutional participation confirmed.
    """
    avg_volume = df['Volume'].rolling(period).mean()
    ratio = df['Volume'] / avg_volume.replace(0, np.nan)
    return ratio.fillna(1.0).rename('volume_ratio')


def calculate_price_momentum(df: pd.DataFrame) -> pd.DataFrame:
    """Multi-period momentum features."""
    return pd.DataFrame({
        'momentum_5d': df['Close'].pct_change(5),
        'momentum_10d': df['Close'].pct_change(10),
        'momentum_20d': df['Close'].pct_change(20),
        'momentum_60d': df['Close'].pct_change(60),
    }).fillna(0)


def calculate_reward_risk_ratio(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Potential reward (distance to recent high) vs risk (ATR stop distance).
    Only take signals where reward:risk >= 1.5.
    """
    atr = calculate_atr(df, period)
    recent_high = df['High'].rolling(20).max()
    potential_reward = (recent_high - df['Close']).clip(lower=0)
    stop_distance = 2 * atr
    rr_ratio = potential_reward / stop_distance.replace(0, np.nan)
    return rr_ratio.fillna(0).rename('reward_risk_ratio')


def build_full_feature_matrix(
    stock_df: pd.DataFrame,
    nifty_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Master function: builds the complete feature matrix for ML training/inference.
    Call this from signal_engine.py and preprocessor.py.
    """
    features = pd.DataFrame(index=stock_df.index)

    # --- Price action features ---
    features['proximity_52w_high'] = calculate_52w_high_proximity(stock_df)
    features['atr_14'] = calculate_atr(stock_df)
    features['atr_ratio'] = calculate_atr_ratio(stock_df)
    features['bollinger_width'] = calculate_bollinger_width(stock_df)
    features['reward_risk_ratio'] = calculate_reward_risk_ratio(stock_df)

    # --- Volume intelligence ---
    features['volume_ratio'] = calculate_volume_ratio(stock_df)
    features['obv_slope'] = calculate_obv_slope(stock_df)

    # --- Momentum features ---
    momentum = calculate_price_momentum(stock_df)
    features = pd.concat([features, momentum], axis=1)

    # --- Market context (if Nifty data provided) ---
    if nifty_df is not None:
        features['relative_strength'] = calculate_relative_strength(stock_df, nifty_df)
    else:
        features['relative_strength'] = 1.0

    # --- Derived compound features ---
    features['volume_momentum_score'] = features['volume_ratio'] * features['momentum_5d']
    features['breakout_quality'] = (
        features['volume_ratio'].clip(0, 5) / 5 * 0.4 +
        (1 - features['proximity_52w_high'].clip(0, 1)) * 0.3 +
        features['relative_strength'].clip(0, 3) / 3 * 0.3
    )

    return features.fillna(0)
