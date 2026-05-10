"""
Fundamental Analysis Layer.
Fetches P/E, debt/equity, growth metrics from yfinance.
Produces a 0-1 composite score and A-F grade.
"""

import yfinance as yf
import logging

logger = logging.getLogger(__name__)


class FundamentalDataFetcher:

    WEIGHTS = {
        'pe_ratio': 0.20,
        'promoter_holding': 0.25,
        'debt_equity': 0.20,
        'revenue_growth': 0.15,
        'profit_growth': 0.20,
    }

    def fetch(self, symbol: str) -> dict:
        try:
            sym = symbol
            if not sym.endswith(".NS") and not sym.endswith(".BO"):
                sym = f"{sym}.NS"
            ticker = yf.Ticker(sym)
            info = ticker.info or {}
            if not info:
                return self._empty(symbol)

            pe = info.get('trailingPE') or info.get('forwardPE')
            pb = info.get('priceToBook')
            de = info.get('debtToEquity')
            rev_growth = info.get('revenueGrowth')
            earn_growth = info.get('earningsGrowth')
            roe = info.get('returnOnEquity')
            current_ratio = info.get('currentRatio')
            margin = info.get('profitMargins')

            scores = {}

            # P/E
            if pe and pe > 0:
                scores['pe_ratio'] = 1.0 if pe < 15 else 0.7 if pe < 25 else 0.4 if pe < 40 else 0.2
            else:
                scores['pe_ratio'] = 0.5

            # Debt/Equity
            if de is not None:
                d = de / 100 if de > 10 else de
                scores['debt_equity'] = 1.0 if d < 0.3 else 0.7 if d < 0.7 else 0.4 if d < 1.5 else 0.1
            else:
                scores['debt_equity'] = 0.5

            # Revenue Growth
            if rev_growth:
                scores['revenue_growth'] = 1.0 if rev_growth > 0.20 else 0.7 if rev_growth > 0.10 else 0.5 if rev_growth > 0 else 0.2
            else:
                scores['revenue_growth'] = 0.5

            # Earnings Growth
            if earn_growth:
                scores['profit_growth'] = 1.0 if earn_growth > 0.25 else 0.7 if earn_growth > 0.10 else 0.5 if earn_growth > 0 else 0.2
            else:
                scores['profit_growth'] = 0.5

            scores['promoter_holding'] = 0.5  # Placeholder — needs screener.in

            composite = sum(scores.get(k, 0.5) * w for k, w in self.WEIGHTS.items())

            return {
                'symbol': symbol,
                'pe_ratio': round(pe, 2) if pe else None,
                'pb_ratio': round(pb, 2) if pb else None,
                'debt_equity': round(de / 100, 2) if de else None,
                'revenue_growth_pct': round(rev_growth * 100, 1) if rev_growth else None,
                'earnings_growth_pct': round(earn_growth * 100, 1) if earn_growth else None,
                'return_on_equity_pct': round(roe * 100, 1) if roe else None,
                'current_ratio': round(current_ratio, 2) if current_ratio else None,
                'profit_margin_pct': round(margin * 100, 1) if margin else None,
                'fundamental_score': round(composite, 3),
                'fundamental_grade': self._grade(composite),
                'component_scores': scores,
            }

        except Exception as e:
            logger.warning(f"[{symbol}] Fundamental fetch failed: {e}")
            return self._empty(symbol)

    def _grade(self, score: float) -> str:
        if score >= 0.80: return 'A'
        if score >= 0.65: return 'B'
        if score >= 0.50: return 'C'
        if score >= 0.35: return 'D'
        return 'F'

    def _empty(self, symbol: str) -> dict:
        return {
            'symbol': symbol,
            'fundamental_score': 0.5,
            'fundamental_grade': 'C',
            'pe_ratio': None, 'debt_equity': None,
            'revenue_growth_pct': None, 'earnings_growth_pct': None,
        }
