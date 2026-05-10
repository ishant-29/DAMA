"""
Market Regime Detector — classifies current market environment.
Signals are only taken in favorable regimes.
This is the highest-ROI single filter for preventing drawdowns.
"""

import pandas as pd
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import yfinance as yf


class MarketRegime(str, Enum):
    BULL = "BULL"
    RESISTANCE = "RESISTANCE"
    NEUTRAL = "NEUTRAL"
    BEAR = "BEAR"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


@dataclass
class RegimeResult:
    regime: MarketRegime
    nifty_above_ema50: bool
    india_vix: float
    nifty_return_20d: float
    min_confidence_threshold: float
    allow_buy_signals: bool
    allow_sell_signals: bool
    regime_description: str
    fii_net_flow: Optional[float] = None


class MarketRegimeDetector:

    VIX_DANGER = 25.0

    THRESHOLDS = {
        MarketRegime.BULL: 0.65,
        MarketRegime.RESISTANCE: 0.75,
        MarketRegime.NEUTRAL: 0.80,
        MarketRegime.BEAR: 0.90,
        MarketRegime.HIGH_VOLATILITY: 0.95,
    }

    def detect(self) -> RegimeResult:
        """Main method — detects current market regime."""
        nifty_data = self._fetch_nifty()
        vix_data = self._fetch_vix()

        if nifty_data is None:
            return self._fallback_regime()

        nifty_close = nifty_data['Close']
        
        # Calculate moving averages
        ema10 = nifty_close.ewm(span=10, adjust=False).mean()
        ema20 = nifty_close.ewm(span=20, adjust=False).mean()
        ma50 = nifty_close.ewm(span=50, adjust=False).mean()
        
        current_close = float(nifty_close.iloc[-1])
        c_ema10 = float(ema10.iloc[-1])
        c_ema20 = float(ema20.iloc[-1])
        c_ma50 = float(ma50.iloc[-1])

        above_10 = current_close > c_ema10
        above_20 = current_close > c_ema20
        above_50 = current_close > c_ma50

        below_10 = current_close < c_ema10
        below_20 = current_close < c_ema20
        below_50 = current_close < c_ma50

        nifty_above_ema50 = above_50 # using 50 MA for legacy fields
        nifty_return_20d = float(nifty_close.pct_change(20).iloc[-1]) * 100
        india_vix = float(vix_data['Close'].iloc[-1]) if vix_data is not None else 16.0

        # --- Regime Classification ---
        if below_10 and below_20 and below_50:
            regime = MarketRegime.BEAR
        elif above_10 and above_20 and below_50:
            regime = MarketRegime.RESISTANCE
        elif above_10 and above_20 and above_50:
            regime = MarketRegime.BULL
        else:
            regime = MarketRegime.NEUTRAL

        descriptions = {
            MarketRegime.BULL: "Bull Market Detected",
            MarketRegime.RESISTANCE: "Market in Recovery / Resistance Zone",
            MarketRegime.NEUTRAL: "Neutral Market Detected",
            MarketRegime.BEAR: "Bear Market Detected",
            MarketRegime.HIGH_VOLATILITY: "Danger Zone",
        }

        return RegimeResult(
            regime=regime,
            nifty_above_ema50=nifty_above_ema50,
            india_vix=india_vix,
            nifty_return_20d=round(nifty_return_20d, 2),
            min_confidence_threshold=self.THRESHOLDS[regime],
            allow_buy_signals=regime in [MarketRegime.BULL, MarketRegime.RESISTANCE, MarketRegime.NEUTRAL],
            allow_sell_signals=regime != MarketRegime.HIGH_VOLATILITY,
            regime_description=descriptions[regime],
        )

    def _fetch_nifty(self) -> Optional[pd.DataFrame]:
        try:
            ticker = yf.Ticker("^NSEI")
            return ticker.history(period="6mo")
        except Exception:
            return None

    def _fetch_vix(self) -> Optional[pd.DataFrame]:
        try:
            ticker = yf.Ticker("^INDIAVIX")
            return ticker.history(period="5d")
        except Exception:
            return None

    def _fallback_regime(self) -> RegimeResult:
        """Safe fallback if data unavailable."""
        return RegimeResult(
            regime=MarketRegime.NEUTRAL,
            nifty_above_ema50=True,
            india_vix=18.0,
            nifty_return_20d=0.0,
            min_confidence_threshold=0.75,
            allow_buy_signals=True,
            allow_sell_signals=True,
            regime_description="Data unavailable — using conservative neutral regime",
        )
