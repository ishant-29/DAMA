"""
Multi-timeframe analysis service.
Provides trend confirmation across multiple timeframes (daily, weekly, monthly).
"""
import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, List
import yfinance as yf

from app.indicators.ema import ema_df
from app.indicators.darvas import darvas_boxes
from app.core.config import settings

logger = logging.getLogger(__name__)


class TimeFrame(str):
    """Supported timeframes"""
    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"


class MultiTimeframeAnalyzer:
    """
    Analyzes symbol across multiple timeframes for robust signal confirmation.
    """
    
    def __init__(self):
        self.lookback_days = {
            TimeFrame.DAILY: 365,
            TimeFrame.WEEKLY: 52 * 3,  # 3 years of weekly data
            TimeFrame.MONTHLY: 12 * 5,  # 5 years of monthly data
        }
    
    def fetch_data(self, symbol: str, timeframe: TimeFrame, lookback: int = None) -> Optional[pd.DataFrame]:
        """Fetch historical data for a specific timeframe."""
        try:
            lookback = lookback or self.lookback_days.get(timeframe, 365)
            ticker = yf.Ticker(f"{symbol}.NS")
            df = ticker.history(period=f"{lookback}d", interval=timeframe.value)
            
            if df is None or df.empty:
                return None
            
            df.index = pd.to_datetime(df.index)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            df.columns = [c.lower() for c in df.columns]
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch {timeframe.value} data for {symbol}: {e}")
            return None
    
    def analyze_timeframe(self, df: pd.DataFrame) -> Dict:
        """Analyze a single timeframe and return trend indicators."""
        if df is None or len(df) < 20:
            return {'valid': False, 'error': 'Insufficient data'}
        
        try:
            # Calculate indicators
            df = ema_df(df, periods=[10, 20, 50])
            df = darvas_boxes(df)
            
            latest = df.iloc[-1]
            
            # Trend detection
            close = latest.get('close', 0)
            ema_10 = latest.get('ema_10', close)
            ema_20 = latest.get('ema_20', close)
            ema_50 = latest.get('ema_50', close)
            
            # Trend strength score
            trend_score = 0
            if close > ema_10:
                trend_score += 1
            if ema_10 > ema_20:
                trend_score += 1
            if ema_20 > ema_50:
                trend_score += 1
            
            # Determine trend direction
            if trend_score >= 2:
                direction = "BULLISH"
            elif trend_score <= 1:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"
            
            # Darvas box status
            darvas_breakout = latest.get('darvas_breakout', False)
            darvas_high = latest.get('darvas_high', close * 1.05)
            
            is_trending = bool(darvas_breakout) or (close >= darvas_high * 0.98)
            
            # Momentum
            if len(df) >= 5:
                recent_change = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]) * 100
            else:
                recent_change = 0
            
            return {
                'valid': True,
                'direction': direction,
                'trend_score': trend_score,
                'is_trending': is_trending,
                'ema_10': round(ema_10, 2),
                'ema_20': round(ema_20, 2),
                'ema_50': round(ema_50, 2),
                'close': round(close, 2),
                'recent_change_pct': round(recent_change, 2),
                'darvas_breakout': darvas_breakout,
            }
            
        except Exception as e:
            logger.error(f"Error analyzing timeframe: {e}")
            return {'valid': False, 'error': str(e)}
    
    def get_multi_timeframe_analysis(self, symbol: str) -> Dict:
        """
        Get comprehensive analysis across all timeframes.
        Returns trend confirmation signals.
        """
        result = {
            'symbol': symbol,
            'timeframes': {},
            'confirmation': None,
            'overall_trend': None,
            'confidence': 0.0,
        }
        
        timeframes = [TimeFrame.DAILY, TimeFrame.WEEKLY, TimeFrame.MONTHLY]
        trend_scores = []
        
        for tf in timeframes:
            df = self.fetch_data(symbol, tf)
            analysis = self.analyze_timeframe(df)
            result['timeframes'][tf.value] = analysis
            
            if analysis.get('valid'):
                if analysis['direction'] == 'BULLISH':
                    trend_scores.append(1)
                elif analysis['direction'] == 'BEARISH':
                    trend_scores.append(-1)
                # NEUTRAL adds 0
        
        # Calculate confirmation
        if trend_scores:
            avg_trend = sum(trend_scores) / len(trend_scores)
            
            if avg_trend >= 0.5:
                result['overall_trend'] = "STRONG_BULLISH"
                result['confirmation'] = "CONFIRMED"
                result['confidence'] = min(0.95, 0.6 + (avg_trend * 0.2))
            elif avg_trend > 0:
                result['overall_trend'] = "BULLISH"
                result['confirmation'] = "WEAK_CONFIRMATION"
                result['confidence'] = 0.5 + (avg_trend * 0.2)
            elif avg_trend <= -0.5:
                result['overall_trend'] = "STRONG_BEARISH"
                result['confirmation'] = "CONFIRMED"
                result['confidence'] = min(0.95, 0.6 + (abs(avg_trend) * 0.2))
            elif avg_trend < 0:
                result['overall_trend'] = "BEARISH"
                result['confirmation'] = "WEAK_CONFIRMATION"
                result['confidence'] = 0.5 + (abs(avg_trend) * 0.2)
            else:
                result['overall_trend'] = "NEUTRAL"
                result['confirmation'] = "NO_CONFIRMATION"
                result['confidence'] = 0.3
        
        return result
    
    def get_aligned_signals(self, symbol: str) -> Optional[Dict]:
        """
        Get trading signal when all timeframes align.
        Returns BUY/SELL/NEUTRAL based on multi-timeframe confirmation.
        """
        analysis = self.get_multi_timeframe_analysis(symbol)
        
        if not analysis.get('timeframes'):
            return None
        
        # Check for alignment
        valid_timeframes = [
            tf for tf, data in analysis['timeframes'].items()
            if data.get('valid')
        ]
        
        if len(valid_timeframes) < 2:
            return {
                'signal': 'NEUTRAL',
                'reason': 'Insufficient timeframe data',
                'confidence': 0.0,
            }
        
        trend = analysis['overall_trend']
        confidence = analysis['confidence']
        
        if trend in ['STRONG_BULLISH', 'BULLISH']:
            return {
                'signal': 'BUY',
                'reason': f'Multi-timeframe {trend} confirmation',
                'confidence': round(confidence, 2),
                'timeframes': valid_timeframes,
                'details': analysis,
            }
        elif trend in ['STRONG_BEARISH', 'BEARISH']:
            return {
                'signal': 'SELL',
                'reason': f'Multi-timeframe {trend} confirmation',
                'confidence': round(confidence, 2),
                'timeframes': valid_timeframes,
                'details': analysis,
            }
        else:
            return {
                'signal': 'NEUTRAL',
                'reason': 'No clear multi-timeframe trend',
                'confidence': round(confidence, 2),
                'timeframes': valid_timeframes,
                'details': analysis,
            }


# Singleton instance
_mtf_analyzer: Optional[MultiTimeframeAnalyzer] = None


def get_mtf_analyzer() -> MultiTimeframeAnalyzer:
    """Get or create the multi-timeframe analyzer singleton."""
    global _mtf_analyzer
    if _mtf_analyzer is None:
        _mtf_analyzer = MultiTimeframeAnalyzer()
    return _mtf_analyzer