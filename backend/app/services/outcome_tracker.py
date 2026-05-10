"""
Signal Outcome Tracker — the feedback engine.
After N days, fetches actual price and grades each signal.
Feeds outcomes back to ML training pipeline monthly.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import yfinance as yf

from app.db.models import Signal


class OutcomeTracker:

    OUTCOME_WINDOW_DAYS = 15

    def grade_pending_signals(self, db: Session) -> dict:
        """
        Called by APScheduler — runs nightly.
        Grades signals immediately for testing purposes.
        """
        # Remove cutoff_date since window is 0
        
        pending = (
            db.query(Signal)
            .filter(
                Signal.signal_type == 'BUY',
                # Removed timestamp filter to grade all recent signals
                Signal.outcome_pnl_pct == None,
            )
            .limit(500) # Increased to grade backtest quickly
            .all()
        )

        graded_count = 0

        for signal in pending:
            outcome = self._calculate_outcome(signal)
            if outcome:
                signal.outcome_pnl_pct = outcome['pnl_pct']
                signal.outcome_grade = outcome['grade']
                signal.outcome_exit_price = outcome['exit_price']
                signal.outcome_graded_at = datetime.utcnow()
                graded_count += 1

        db.commit()
        return {'signals_graded': graded_count}

    def _calculate_outcome(self, signal) -> dict:
        """Fetch actual price N days after signal and calculate P&L."""
        try:
            sym = signal.symbol
            if not sym.endswith(".NS") and not sym.endswith(".BO"):
                sym = f"{sym}.NS"
            ticker = yf.Ticker(sym)

            start = signal.timestamp.strftime('%Y-%m-%d')
            history = ticker.history(start=start, period='30d')

            if len(history) < 1:  # At least 1 day needed
                return None

            entry_price = float(history['Open'].iloc[0]) # Use first day open
            exit_idx = min(self.OUTCOME_WINDOW_DAYS, len(history) - 1)
            exit_price = float(history['Close'].iloc[exit_idx])
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            if pnl_pct >= 8:
                grade = 'A'
            elif pnl_pct >= 3:
                grade = 'B'
            elif pnl_pct >= 0:
                grade = 'C'
            elif pnl_pct >= -3:
                grade = 'D'
            else:
                grade = 'F'

            return {
                'entry_price': round(entry_price, 2),
                'exit_price': round(exit_price, 2),
                'pnl_pct': round(pnl_pct, 2),
                'grade': grade,
            }
        except Exception:
            return None

    def export_training_dataset(self, db: Session, min_samples: int = 200) -> pd.DataFrame:
        """Exports graded signals for ML retraining."""
        graded = (
            db.query(Signal)
            .filter(Signal.outcome_grade != None, Signal.signal_type == 'BUY')
            .all()
        )

        if len(graded) < min_samples:
            return None

        rows = []
        for s in graded:
            rows.append({
                'symbol': s.symbol,
                'confidence': s.confidence,
                'volume_ratio': getattr(s, 'volume_ratio', None),
                'atr_ratio': getattr(s, 'atr_ratio', None),
                'market_regime': getattr(s, 'market_regime', None),
                'outcome_pnl_pct': s.outcome_pnl_pct,
                'outcome_grade': s.outcome_grade,
                'is_winner': 1 if s.outcome_pnl_pct and s.outcome_pnl_pct > 0 else 0,
            })

        return pd.DataFrame(rows)
