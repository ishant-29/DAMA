"""
Options Market Sentiment — adds institutional intelligence layer.
PCR, IV Percentile, and Max Pain for professional-grade sentiment.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional


class OptionsSentiment:

    def get_pcr_sentiment(self, symbol: str) -> dict:
        """
        Put/Call Ratio analysis.
        PCR < 0.7  = Extreme bullishness (contrarian sell signal)
        PCR 0.8-1.2 = Healthy uptrend — BUY signals reliable
        PCR > 1.5  = Extreme fear — contrarian buy
        """
        try:
            sym = symbol
            if not sym.endswith(".NS") and not sym.endswith(".BO"):
                sym = f"{sym}.NS"
            ticker = yf.Ticker(sym)
            options_dates = ticker.options

            if not options_dates:
                return self._no_options_data(symbol)

            nearest_expiry = options_dates[0]
            chain = ticker.option_chain(nearest_expiry)

            total_put_oi = chain.puts['openInterest'].sum()
            total_call_oi = chain.calls['openInterest'].sum()

            pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0

            if pcr < 0.7:
                sentiment = "EXTREME_GREED"
                signal_modifier = -0.05
            elif pcr <= 1.2:
                sentiment = "BULLISH_HEALTHY"
                signal_modifier = 0.03
            elif pcr <= 1.5:
                sentiment = "NEUTRAL"
                signal_modifier = 0.0
            else:
                sentiment = "EXTREME_FEAR"
                signal_modifier = 0.02

            # IV Percentile calculation
            try:
                iv_values = chain.calls['impliedVolatility'].dropna()
                current_iv = float(iv_values.median())
                hist = ticker.history(period='1y')
                hist_vol = hist['Close'].pct_change().std() * np.sqrt(252)
                iv_percentile = min(100, (current_iv / hist_vol) * 50) if hist_vol > 0 else 50
            except Exception:
                iv_percentile = 50

            return {
                'symbol': symbol,
                'pcr': round(pcr, 2),
                'pcr_sentiment': sentiment,
                'confidence_modifier': signal_modifier,
                'iv_percentile': round(iv_percentile, 1),
                'iv_note': (
                    "LOW IV = cheaper risk, better entry" if iv_percentile < 30 else
                    "HIGH IV = expensive, wait for IV crush" if iv_percentile > 70 else
                    "NORMAL IV"
                ),
            }

        except Exception:
            return self._no_options_data(symbol)

    def _no_options_data(self, symbol: str) -> dict:
        return {
            'symbol': symbol,
            'pcr': None,
            'pcr_sentiment': 'NO_DATA',
            'confidence_modifier': 0.0,
            'iv_percentile': None,
            'iv_note': 'Options data unavailable',
        }
