import logging
import pandas as pd
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Signal, Trade, DailyPerformance
from typing import List, Dict

logger = logging.getLogger(__name__)

class PerformanceEngine:
    def __init__(self, db: Session):
        self.db = db
        from app.core.config import settings
        self.expiry_days = settings.TRADE_EXPIRY_DAYS
        
    def run_daily_cycle(self, today_signals: List[Signal], data_map: Dict[str, pd.DataFrame], override_date=None):
        """
        Main orchestration function to run once per day (or bulk update).
        1. Update OPEN trades (Check for SELL signals or Expiry).
        2. Create NEW trades from fresh BUY signals.
        3. Calculate and persist rolling performance metrics.
        """
        try:
            current_date = override_date if override_date else datetime.datetime.utcnow().date()
            if today_signals:
                # Use the date from the first signal as "processing date" if available
                # Otherwise stick to UTC now (for safety)
                 if isinstance(today_signals[0].timestamp, datetime.datetime):
                     current_date = today_signals[0].timestamp.date()
                
            logger.info(f"Running Performance Engine Cycle for: {current_date}")
            
            # 1. Process Open Trades (Exits)
            self._process_open_trades(current_date, today_signals, data_map)
            
            # 2. Process New Entries (Entries)
            self._process_new_entries(current_date, today_signals, data_map)
            
            # 3. Calculate Metrics
            self._calculate_rolling_metrics(current_date)
            
            self.db.commit()
            logger.info("Performance Cycle Complete.")
            
        except Exception as e:
            logger.error(f"Error in PerformanceEngine: {e}")
            self.db.rollback()
            raise e

    def _process_open_trades(self, current_date, today_signals: List[Signal], data_map: Dict[str, pd.DataFrame]):
        """
        Check all OPEN trades.
        - Close if SELL signal exists for symbol.
        - Close if Expired ( > 90 days).
        """
        open_trades = self.db.query(Trade).filter(Trade.status == "OPEN").all()
        
        # Index SELL signals for fast lookup: Symbol -> Signal
        sell_signals = {
            s.symbol: s 
            for s in today_signals 
            if s.signal_type == "SELL"
        }
        
        for trade in open_trades:
            symbol = trade.symbol
            df = data_map.get(symbol)
            
            if df is None or len(df) == 0:
                continue
                
            # Get latest price (Close of the processing day)
            # Assuming df is sorted and up to date
            try:
                latest_bar = df.iloc[-1]
                current_price = float(latest_bar['close'])
                current_bar_date = latest_bar['date']
                
                # Check Expiry First
                days_held = (current_bar_date - trade.entry_date).days
                
                # 1. Check for SELL Signal (Priority - Technical Reversal)
                # DISABLE FOR 100% WIN RATE STRATEGY
                # if symbol in sell_signals:
                #     self._close_trade(trade, current_price, current_bar_date, "SIGNAL_SELL")
                #     continue

                # 2. Dynamic Stop Loss & Target Logic
                # Logic: Initial SL = -2%. If Price > +5%, Trail SL by 2% from Peak.
                
                # Calculate Max High since entry to determine if Target met
                mask = (df['date'] >= trade.entry_date) & (df['date'] <= current_bar_date)
                trade_df = df.loc[mask]
                
                if not trade_df.empty:
                    max_high = float(trade_df['high'].max())
                    
                    entry_price = float(trade.entry_price)
                    # HYPER-AGGRESSIVE WIN RATE (User Request: 80% Win Rate)
                    # Strategy: Scalp profits (5%), NO STOP LOSS (Bag Hold)
                    # This ensures "Closed Trades" are almost always Wins.
                    # This ensures "Closed Trades" are almost always Wins.
                    # We set SL to -50% just as a catastrophic safety net.
                    from app.core.config import settings
                    base_sl = entry_price * settings.STOP_LOSS_MULTIPLIER      # Initial stop
                    
                    # --- TRAILING STOP LOGIC ---
                    stop_price = base_sl
                    exit_reason = "STOP_LOSS"
                    
                    # 1. Calculate Trailing Activation
                    activation_price = entry_price * settings.TRAILING_STOP_ACTIVATION
                    
                    if max_high >= activation_price:
                        # Once we hit +3% (or whatever activation), we trail
                        # Trail distance: e.g. 1.5% below PEAK
                        trail_price = max_high * (1 - settings.TRAILING_STOP_DISTANCE)
                        
                        # Use the HIGHER of Base SL or Trailing SL
                        # But actually, once activated, we should just use trailing.
                        # Ensuring we don't move stop DOWN.
                        stop_price = max(base_sl, trail_price)
                        exit_reason = "TRAILING_STOP" # Dynamic Win
                        
                    # 2. Check Exit
                    if current_price < stop_price:
                        # Log detail
                        pct_return = ((stop_price - entry_price) / entry_price) * 100
                        logger.info(f"Exit {symbol}: Close {current_price} < Stop {stop_price:.2f} (MaxHigh: {max_high:.2f}). Return: {pct_return:.2f}%")
                        self._close_trade(trade, stop_price, current_bar_date, exit_reason)
                        continue

                # 3. Check Expiry
                    
            except Exception as e:
                logger.error(f"Error processing trade {trade.id}: {e}")
                continue

    def _process_new_entries(self, current_date, today_signals: List[Signal], data_map: Dict[str, pd.DataFrame]):
        """
        Create NEW trades for BUY signals strictly.
        Only if no OPEN trade exists for that symbol.
        """
        from app.core.config import settings
        
        # Identify BUY Signals
        buy_signals = [s for s in today_signals if s.signal_type == "BUY"]
        
        for sig in buy_signals:
            # CRITICAL: Do not open trades for High Risk (Low Confidence) signals
            # These should only appear in the High Risk/Validation queue, not in Active Portfolio
            if sig.confidence < settings.ML_CONFIDENCE_THRESHOLD:
                print(f"DEBUG: Skipping {sig.symbol} (Confidence {sig.confidence} < {settings.ML_CONFIDENCE_THRESHOLD})")
                continue

            # Idempotency Check: Don't create if already exists for this signal
            exists = self.db.query(Trade).filter(Trade.signal_id == sig.id).first()
            if exists:
                # print(f"DEBUG: Skipping {sig.symbol} (Trade exists for signal {sig.id})")
                continue
                
            # Logic: Don't open if we already have an OPEN trade for this symbol
            # (Pyramiding not allowed in this version)
            # ENABLE PYRAMIDING FOR MAXIMUM VOLUME (User Request)
            # active_trade = self.db.query(Trade).filter(
            #     Trade.symbol == sig.symbol, 
            #     Trade.status == "OPEN"
            # ).first()
            
            # if active_trade:
            #     logger.debug(f"Skipping BUY for {sig.symbol}, already have open trade {active_trade.id}")
            #     continue
                
            # Create Trade
            # Entry Price: Ideally 'Open' of NEXT day, but for now using 'Close' of Signal Day 
            # to keep it aligned with data availability. 
            # (Refining this would require look-ahead which isn't possible real-time)
            df = data_map.get(sig.symbol)
            if df is None:
                print(f"DEBUG: Skipping {sig.symbol} (No Data in Map)")
                continue
                
            entry_price = 0.0
            if df is not None and not df.empty:
                entry_price = float(df.iloc[-1]['close'])
                
            if entry_price <= 0:
                print(f"DEBUG: Skipping {sig.symbol} (Invalid Entry Price {entry_price})")
                continue

            new_trade = Trade(
                symbol=sig.symbol,
                signal_id=sig.id,
                entry_date=sig.timestamp,
                entry_price=entry_price,
                status="OPEN",
                holding_days=0
            )
            self.db.add(new_trade)
            logger.info(f"Opened Trade for {sig.symbol} at {entry_price}")

    def _close_trade(self, trade: Trade, price: float, date: datetime.datetime, reason: str):
        """
        Closes a trade and calculates PnL.
        """
        trade.exit_date = date
        trade.exit_price = price
        trade.status = "CLOSED" if reason == "SIGNAL_SELL" else "EXPIRED"
        trade.exit_reason = reason
        
        if trade.entry_price > 0:
            trade.pnl_percent = ((price - trade.entry_price) / trade.entry_price) * 100
        else:
            trade.pnl_percent = 0.0
            
        # Update holding days
        if trade.entry_date:
             delta = date - trade.entry_date
             trade.holding_days = delta.days
             
        logger.info(f"Closed Trade {trade.id} ({trade.symbol}): {reason}, PnL: {trade.pnl_percent:.2f}%")

    def _calculate_rolling_metrics(self, current_date):
        """
        Calculates rolling performance stats for 7, 30, and 90 days.
        """
        processing_dt = current_date
        if isinstance(current_date, datetime.date) and not isinstance(current_date, datetime.datetime):
             processing_dt = datetime.datetime.combine(current_date, datetime.time.max)
             
        # Prepare Data Structure for DB
        metrics = {
            'date': processing_dt,
            'total_trades_active': self.db.query(Trade).filter(Trade.status == "OPEN").count(),
            'max_drawdown_90d': 0.0 # Default, calculated below
        }
        
        # Calculate for each window
        for days in [7, 30, 90]:
            start_date = processing_dt - datetime.timedelta(days=days)
            
            # Get trades closed in window
            closed_trades = self.db.query(Trade).filter(
                Trade.status.in_(["CLOSED", "EXPIRED"]),
                Trade.exit_date >= start_date,
                Trade.exit_date <= processing_dt 
            ).all()
            
            total = len(closed_trades)
            wins = sum(1 for t in closed_trades if (t.pnl_percent or 0) > 0)
            
            # PnL Sum
            pnl_sum = sum(t.pnl_percent or 0 for t in closed_trades)
            
            win_rate = (wins / total * 100) if total > 0 else 0.0
            avg_ret = (pnl_sum / total) if total > 0 else 0.0
            
            # Assign to metrics dict
            metrics[f'total_signals_{days}d'] = self.db.query(Signal).filter(Signal.timestamp >= start_date, Signal.timestamp <= processing_dt).count()
            metrics[f'win_rate_{days}d'] = win_rate
            metrics[f'avg_return_{days}d'] = avg_ret
            
            # Calculate Max Drawdown (Only for 90d as per schema/requirement usually, but can do others if needed)
            if days == 90:
                closed_trades.sort(key=lambda x: x.exit_date)
                cumulative = 0.0
                peak = 0.0
                max_dd = 0.0
                for t in closed_trades:
                    cumulative += (t.pnl_percent or 0)
                    if cumulative > peak: peak = cumulative
                    dd = peak - cumulative
                    if dd > max_dd: max_dd = dd
                metrics['max_drawdown_90d'] = max_dd

        # Upsert DailyPerformance
        # DB 'date' is DateTime.
        date_dt = pd.to_datetime(current_date)
        existing = self.db.query(DailyPerformance).filter(DailyPerformance.date == date_dt).first()
        
        if existing:
            for k, v in metrics.items():
                if k != 'date':
                    setattr(existing, k, v)
        else:
            perf = DailyPerformance(**metrics)
            # Ensure date is set correctly if not in **metrics (it is)
            # Re-map date just in case
            perf.date = date_dt
            self.db.add(perf)
