import pandas as pd
import numpy as np
from app.indicators.ema import ema, ema_df
from app.indicators.darvas import darvas_boxes
from app.indicators.atr import atr, true_range

class Preprocessor:
    def __init__(self):
        pass

    def process_bars(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
        """
        Generate features and targets from raw bars.
        
        Args:
            df: DataFrame with date, open, high, low, close, volume.
            
        Returns:
            X: Feature DataFrame
            y: Target Series (dummy target for now during inference, real target during training)
            feature_list: List of feature names
        """
        data = df.copy()
        data.sort_values('date', inplace=True)
        data.reset_index(drop=True, inplace=True)
        
        # 1. Indicators
        data = ema_df(data, [10, 20, 50])
        data = darvas_boxes(data)
        data['atr'] = atr(data, 14)
        
        # 2. Features
        
        # EMA Deltas & Slopes
        data['ema10_ema20_diff'] = (data['ema_10'] - data['ema_20']) / data['ema_20']
        data['ema10_slope'] = data['ema_10'] / data['ema_10'].shift(1) - 1
        
        # Price relative to EMA
        data['close_ema50_diff'] = (data['close'] - data['ema_50']) / data['ema_50']
        
        # Darvas
        data['darvas_breakout_flag'] = data['darvas_breakout'].astype(int)
        
        # Volume
        data['avg_vol_20'] = data['volume'].rolling(20).mean()
        data['volume_ratio'] = data['volume'] / data['avg_vol_20']
        
        # Volatility
        data['atr_ratio'] = data['atr'] / data['close']
        
        # Rolling Returns
        for r in [1, 3, 7, 14, 30]:
            data[f'ret_{r}d'] = data['close'].pct_change(r)
            
        # Drop NaNs
        data.dropna(inplace=True)
        
        # Feature selection
        features = [
            'ema10_ema20_diff', 'ema10_slope', 'close_ema50_diff',
            'darvas_breakout_flag', 'volume_ratio', 'atr_ratio',
            'ret_1d', 'ret_3d', 'ret_7d', 'ret_14d', 'ret_30d'
        ]
        
        # Valid intersection
        valid_features = [f for f in features if f in data.columns]
        
        X = data[valid_features]
        
        # Target (Future 7d return > 3%? for training only. None for inference)
        # We'll just define a placeholder target calculation here that can be used by the trainer
        # Target: 1 if Max return in next 7 days > 3% AND Min return > -2%?
        # Simple target: Close in 7 days > Close now * 1.03
        
        # We return empty y by default, trainer will calculate it.
        y = pd.Series(index=data.index, dtype=float)
        
        return X, y, valid_features

    def calculate_target(self, df: pd.DataFrame, lookahead: int = 7) -> pd.Series:
        """
        Calculate binary target for training.
        Target = 1 if (Close[t+lookahead] / Close[t]) - 1 > 0.03
        """
        # This needs to be done BEFORE dropna in a real pipeline that has access to future data
        # For this minimal version, we assume df has 'close' and full history
        
        future_close = df['close'].shift(-lookahead)
        ret = (future_close / df['close']) - 1
        y = (ret > 0.03).astype(int)
        return y
