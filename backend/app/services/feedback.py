from sqlalchemy.orm import Session
from app.db.models import Signal, SignalOutcome, AutoTuneEvent, OutcomeType
from datetime import datetime, timedelta
import pandas as pd
import os

class FeedbackService:
    def __init__(self, db: Session):
        self.db = db
        # Defaults
        self.lookahead_days = int(os.getenv("LOOKAHEAD_DAYS", 7))
        self.win_threshold = 0.03
        self.loss_threshold = -0.02
        
    def evaluate_signals(self, data_map: dict[str, pd.DataFrame]):
        """
        Check past signals against 'future' data (which is now available).
        """
        # 1. Find unevaluated signals older than lookahead_days
        cutoff_date = datetime.utcnow() - timedelta(days=self.lookahead_days)
        
        signals = self.db.query(Signal).filter(
            Signal.processed == False,
            Signal.timestamp < cutoff_date
        ).all()
        
        count = 0
        for sig in signals:
            df = data_map.get(sig.symbol)
            if df is None:
                continue
                
            # Find price at signal
            # Assuming sig.timestamp is in data
            # Use nearest date match (as sig timestamp might be exact time, data is daily)
            # data has 'date' col
            
            # Simple approach: exact date match or next available
            # We need the row at sig.timestamp and the row at sig.timestamp + lookahead
            
            sig_date = pd.to_datetime(sig.timestamp).normalize()
            
            # Filter df for dates >= sig_date
            future_df = df[df['date'] >= sig_date].copy()
            future_df.sort_values('date', inplace=True)
            
            if len(future_df) < 2:
                # Not enough data yet
                continue
                
            entry_price = future_df.iloc[0]['close']
            
            # Check Max/Min in next N days or just Nth day return?
            # Prompt: "WIN if price rises >= +3% within lookahead" -> Max High
            
            lookahead_window = future_df.iloc[1:self.lookahead_days+1]
            if lookahead_window.empty:
                continue
                
            max_price = lookahead_window['high'].max()
            min_price = lookahead_window['low'].min()
            
            pnl = 0.0
            outcome = OutcomeType.NEUTRAL.value
            
            if sig.signal_type == "BUY":
                max_ret = (max_price - entry_price) / entry_price
                min_ret = (min_price - entry_price) / entry_price
                
                if max_ret >= self.win_threshold:
                    outcome = OutcomeType.WIN.value
                    pnl = max_ret
                elif min_ret <= self.loss_threshold:
                    outcome = OutcomeType.LOSS.value
                    pnl = min_ret
                else:
                    outcome = OutcomeType.NEUTRAL.value
                    pnl = (lookahead_window.iloc[-1]['close'] - entry_price) / entry_price
            
            elif sig.signal_type == "SELL":
                # Sell: profit if price drops
                max_ret = (entry_price - min_price) / entry_price # Positive
                min_ret = (entry_price - max_price) / entry_price # Negative (price went up)
                
                if max_ret >= self.win_threshold:
                     outcome = OutcomeType.WIN.value
                     pnl = max_ret
                elif min_ret <= self.loss_threshold:
                     outcome = OutcomeType.LOSS.value
                     pnl = min_ret
                else:
                     outcome = OutcomeType.NEUTRAL.value
                     pnl = (entry_price - lookahead_window.iloc[-1]['close']) / entry_price
            
            # Persist Outcome
            res = SignalOutcome(
                signal_id=sig.id,
                outcome=outcome,
                pnl_percent=pnl,
                closed_at=lookahead_window.iloc[-1]['date']
            )
            self.db.add(res)
            sig.processed = True
            count += 1
            
        self.db.commit()
        return count

    def check_auto_tune(self):
        """
        Check rolling accuracy and adjust thresholds if needed.
        """
        # Get last 100 outcomes
        outcomes = self.db.query(SignalOutcome).order_by(SignalOutcome.closed_at.desc()).limit(100).all()
        if len(outcomes) < 20: # Min sample
            return
            
        wins = sum(1 for o in outcomes if o.outcome == OutcomeType.WIN.value)
        total = len(outcomes)
        accuracy = wins / total
        
        target_acc = 0.55
        
        if accuracy < target_acc:
            # Trigger Auto Tune
            self._trigger_tune(accuracy)
            
    def _trigger_tune(self, current_acc: float):
        """
        Adjust thresholds.
        """
        # Get current config (Assuming we store it or default to env)
        # For MVP, we fetch the LATEST AutoTuneEvent to see current state, or env defaults
        
        last_event = self.db.query(AutoTuneEvent).order_by(AutoTuneEvent.timestamp.desc()).first()
        
        current_conf = last_event.new_confidence_threshold if last_event else float(os.getenv("ML_CONFIDENCE_THRESHOLD", 0.65))
        current_vol = last_event.new_volume_multiplier if last_event else float(os.getenv("VOLUME_MULTIPLIER", 1.5))
        
        # Adjust
        new_conf = min(0.9, current_conf + 0.05)
        new_vol = current_vol + 0.25
        
        if new_conf == current_conf and new_vol == current_vol:
            return # Cap reached
            
        event = AutoTuneEvent(
            trigger_reason=f"Accuracy {current_acc:.2f} < 0.55",
            old_confidence_threshold=current_conf,
            new_confidence_threshold=new_conf,
            old_volume_multiplier=current_vol,
            new_volume_multiplier=new_vol
        )
        self.db.add(event)
        self.db.commit()
        print(f"AUTO-TUNE TRIGGERED: Conf {current_conf}->{new_conf}, Vol {current_vol}->{new_vol}")

    def get_current_thresholds(self):
        last_event = self.db.query(AutoTuneEvent).order_by(AutoTuneEvent.timestamp.desc()).first()
        if last_event:
            return last_event.new_confidence_threshold, last_event.new_volume_multiplier
        return float(os.getenv("ML_CONFIDENCE_THRESHOLD", 0.50)), float(os.getenv("VOLUME_MULTIPLIER", 1.5))
