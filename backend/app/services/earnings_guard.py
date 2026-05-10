"""
Earnings Calendar Filter.
Prevents entering positions within 10 trading days of quarterly results.
"""

import pandas as pd
from datetime import datetime
import yfinance as yf


class EarningsGuard:

    DANGER_DAYS = 10

    def check_earnings_risk(self, symbol: str) -> dict:
        """Check if a symbol has earnings within DANGER_DAYS trading days."""
        try:
            sym = symbol
            if not sym.endswith(".NS") and not sym.endswith(".BO"):
                sym = f"{sym}.NS"
            ticker = yf.Ticker(sym)
            calendar = ticker.calendar

            if calendar is None or (hasattr(calendar, 'empty') and calendar.empty):
                return self._no_data_response(symbol)

            if 'Earnings Date' in calendar.index:
                earnings_dates = calendar.loc['Earnings Date']
                now = pd.Timestamp.now()

                if hasattr(earnings_dates, '__iter__'):
                    future_dates = [pd.Timestamp(d) for d in earnings_dates if pd.Timestamp(d) > now]
                    if not future_dates:
                        return self._no_data_response(symbol)
                    next_earnings = min(future_dates)
                else:
                    next_earnings = pd.Timestamp(earnings_dates)
                    if next_earnings <= now:
                        return self._no_data_response(symbol)

                days_until = self._count_trading_days(now, next_earnings)
                is_risky = days_until <= self.DANGER_DAYS

                return {
                    'earnings_risk': is_risky,
                    'next_earnings_date': next_earnings.strftime('%Y-%m-%d'),
                    'trading_days_until_earnings': days_until,
                    'recommendation': (
                        f"⚠️ EARNINGS IN {days_until} DAYS — High binary risk, consider skipping"
                        if is_risky else
                        f"✅ Earnings {days_until} days away — Safe entry window"
                    ),
                }
        except Exception:
            pass

        return self._no_data_response(symbol)

    def _count_trading_days(self, start: pd.Timestamp, end: pd.Timestamp) -> int:
        return len(pd.bdate_range(start, end))

    def _no_data_response(self, symbol: str) -> dict:
        return {
            'earnings_risk': False,
            'next_earnings_date': None,
            'trading_days_until_earnings': 999,
            'recommendation': "Earnings data unavailable — proceed with caution",
        }
