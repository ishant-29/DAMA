"""
Tests for indicator functions (EMA, Darvas)
"""
import pytest
import pandas as pd
import numpy as np
from app.indicators.ema import ema, ema_df
from app.indicators.darvas import darvas_boxes

class TestEMA:
    """Test Exponential Moving Average calculations"""
    
    def test_ema_calculation(self):
        """Test basic EMA calculation"""
        data = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
        result = ema(data, period=5)
        
        assert len(result) == len(data)
        assert not result.isna().all()
        # EMA should be trending up for increasing data
        assert result.iloc[-1] > result.iloc[5]
    
    def test_ema_empty_series(self):
        """Test EMA with empty series"""
        data = pd.Series([])
        result = ema(data, period=10)
        
        assert len(result) == 0
    
    def test_ema_df_with_close_column(self):
        """Test ema_df with valid dataframe"""
        df = pd.DataFrame({
            'close': [100, 101, 102, 103, 104, 105],
            'volume': [1000, 1100, 1200, 1300, 1400, 1500]
        })
        
        result = ema_df(df, periods=[5, 10])
        
        assert 'ema_5' in result.columns
        assert 'ema_10' in result.columns
        assert len(result) == len(df)
    
    def test_ema_df_missing_close_column(self):
        """Test ema_df raises error for missing close column"""
        df = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107]
        })
        
        with pytest.raises(ValueError, match="close"):
            ema_df(df, periods=[10])
    
    def test_ema_df_case_insensitive(self):
        """Test ema_df works with different case"""
        df = pd.DataFrame({
            'Close': [100, 101, 102, 103, 104]
        })
        
        result = ema_df(df, periods=[3])
        assert 'ema_3' in result.columns

class TestDarvas:
    """Test Darvas Box calculations"""
    
    def test_darvas_basic(self):
        """Test basic Darvas box calculation"""
        df = pd.DataFrame({
            'high': [110, 115, 120, 118, 122, 125, 123, 121],
            'low': [100, 105, 110, 112, 115, 118, 116, 114],
            'close': [105, 110, 115, 115, 120, 122, 120, 118]
        })
        
        result = darvas_boxes(df, lookback=3, confirmation=2)
        
        assert 'darvas_high' in result.columns
        assert 'darvas_low' in result.columns
        assert len(result) == len(df)
    
    def test_darvas_empty_dataframe(self):
        """Test Darvas with empty dataframe"""
        df = pd.DataFrame(columns=['high', 'low', 'close'])
        
        result = darvas_boxes(df)
        
        assert 'darvas_high' in result.columns
        assert 'darvas_low' in result.columns
        assert len(result) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
