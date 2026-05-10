"""
Signal Auditor Service
Verifies past signals against subsequent market data to determine WIN/LOSS outcomes.
"""
from sqlalchemy.orm import Session
from app.db.models import Signal, SignalOutcome, OutcomeType
from app.services import data_provider
from app.core.config import settings
from datetime import datetime, timedelta
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class SignalAuditor:
    def __init__(self, db: Session):
        self.db = db
        self.TAKE_PROFIT_PCT = getattr(settings, 'BACKTEST_DEFAULT_TAKE_PROFIT', 0.04)
        self.STOP_LOSS_PCT = getattr(settings, 'BACKTEST_DEFAULT_STOP_LOSS', 0.02)
        self.MAX_HOLD_DAYS = settings.BACKTEST_HOLD_DAYS

    def audit_signals(self, lookback_days: int = 30):
        """
        Check pending signals found within the last `lookback_days` 
        and determine their outcome.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # 1. Find signals without outcomes
        # We join with SignalOutcome to find nulls (Left Join filter)
        # Or simpler: Query signals not in subquery of outcomes.
        # For efficiency with SQLAlchemy:
        pending_signals = self.db.query(Signal).outerjoin(SignalOutcome).filter(
            SignalOutcome.id == None,
            Signal.timestamp >= cutoff_date,
            Signal.timestamp < datetime.utcnow() - timedelta(days=1) # Must be at least 1 day old
        ).all()
        
        logger.info(f"Found {len(pending_signals)} pending signals to audit.")
        
        # Group by symbol to batch data fetching
        signals_by_symbol = {}
        for sig in pending_signals:
            if sig.symbol not in signals_by_symbol:
                signals_by_symbol[sig.symbol] = []
            signals_by_symbol[sig.symbol].append(sig)
            
        # 2. Process each symbol
        for symbol, signals in signals_by_symbol.items():
            self._audit_symbol_batch(symbol, signals)
            
        self.db.commit()
        logger.info("Audit complete.")

    def _audit_symbol_batch(self, symbol: str, signals: list[Signal]):
        """
        Fetches data once for the symbol and checks all associated signals.
        """
        # We need data from the earliest signal to NOW
        earliest_date = min(s.timestamp for s in signals)
        
        # Fetch Data (Daily resolution is usually sufficient for Swing 4%/2%)
        # For more precision, we'd want Hourly, but YFinance limits history on hourly.
        # Let's stick to 1d for robust history.
        df = data_provider.fetch_ticker_data(symbol, period="3mo", interval="1d")
        
        if df is None or df.empty:
            logger.warning(f"No data found for auditing {symbol}")
            return

        # Ensure datetime is compatible
        if df['date'].dt.tz is None:
             df['date'] = df['date'].dt.tz_localize(None)

        for sig in signals:
            self._evaluate_signal(sig, df)

    def _evaluate_signal(self, signal: Signal, df: pd.DataFrame):
        """
        Simulate the trade for a single signal.
        """
        # Filter dataframe for dates AFTER the signal
        # Signal timestamp might be naive or UTC.
        sig_ts = signal.timestamp
        
        # Get candles after signal
        # We assume entry is at 'Close' of the signal day (or next Open? simplified to Signal Day Close for now)
        # Ideally: Signal is generated After Market Close. Entry is Next Day Open.
        # Let's use Next Day Open for realistic simulation.
        
        # Find index of signal date
        # df['date'] is localized-naive (removed tz). signal.timestamp is UTC usually?
        # Database stores naive usually.
        
        # Logic: Find rows where date > signal.timestamp
        future_candles = df[df['date'] > sig_ts].copy()
        
        if future_candles.empty:
            # Not enough data yet (maybe signal was yesterday and today is holiday)
            return

        # Entry Price: Open of the first candle AFTER signal generated
        entry_candle = future_candles.iloc[0]
        entry_price = float(entry_candle['open'])
        entry_date = entry_candle['date']
        
        # Define Targets
        if signal.signal_type == "BUY":
            tp_price = entry_price * (1 + self.TAKE_PROFIT_PCT)
            sl_price = entry_price * (1 - self.STOP_LOSS_PCT)
        else: # SELL
            tp_price = entry_price * (1 - self.TAKE_PROFIT_PCT)
            sl_price = entry_price * (1 + self.STOP_LOSS_PCT)
            
        outcome = None
        pnl = 0.0
        close_date = None
        
        # Iterate through future candles
        for idx, row in future_candles.iterrows():
            high = row['high']
            low = row['low']
            close = row['close']
            
            # Check Max Hold Time (timeout)
            days_held = (row['date'] - entry_date).days
            if days_held > self.MAX_HOLD_DAYS:
                outcome = OutcomeType.NEUTRAL
                # Force close at current close
                if signal.signal_type == "BUY":
                    pnl = (close - entry_price) / entry_price * 100
                else:
                    pnl = (entry_price - close) / entry_price * 100
                close_date = row['date']
                break

            if signal.signal_type == "BUY":
                # Check Stop Loss first (conservative)
                if low <= sl_price:
                    outcome = OutcomeType.LOSS
                    pnl = -self.STOP_LOSS_PCT * 100
                    close_date = row['date']
                    break
                # Check Take Profit
                if high >= tp_price:
                    outcome = OutcomeType.WIN
                    pnl = self.TAKE_PROFIT_PCT * 100
                    close_date = row['date']
                    break
            
            elif signal.signal_type == "SELL":
                # Check Stop Loss (High > SL)
                if high >= sl_price:
                    outcome = OutcomeType.LOSS
                    pnl = -self.STOP_LOSS_PCT * 100
                    close_date = row['date']
                    break
                # Check Take Profit (Low < TP)
                if low <= tp_price:
                    outcome = OutcomeType.WIN
                    pnl = self.TAKE_PROFIT_PCT * 100
                    close_date = row['date']
                    break
        
        # If loop finishes without hit and without timeout, trade is still OPEN
        if outcome:
            # Save Result
            logger.info(f"Signal Evaluated: {signal.symbol} {signal.signal_type} -> {outcome} ({pnl:.2f}%)")
            result = SignalOutcome(
                signal_id=signal.id,
                outcome=outcome,
                pnl_percent=pnl,
                closed_at=close_date
            )
            self.db.add(result)
            signal.processed = True

