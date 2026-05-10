"""
Analytics service for performance tracking and metrics
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Signal, Trade, DailyPerformance
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Performance analytics and tracking"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_performance_metrics(self, period_days: int = 30) -> Dict:
        """Get overall performance metrics based on graded signals"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=period_days)
        
        # Get signals graded in the period
        graded_signals = self.db.query(Signal).filter(
            Signal.outcome_pnl_pct.isnot(None),
            Signal.outcome_graded_at >= cutoff_date
        ).all()
        
        if not graded_signals:
            return self._empty_metrics()
        
        # Calculate metrics
        total_closed = len(graded_signals)
        wins = sum(1 for s in graded_signals if s.outcome_pnl_pct > 0)
        losses = sum(1 for s in graded_signals if s.outcome_pnl_pct <= 0)
        
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        # P&L metrics
        total_pnl = sum(s.outcome_pnl_pct for s in graded_signals)
        
        win_sum = sum(s.outcome_pnl_pct for s in graded_signals if s.outcome_pnl_pct > 0)
        loss_sum = sum(s.outcome_pnl_pct for s in graded_signals if s.outcome_pnl_pct <= 0)
        
        avg_win = win_sum / wins if wins > 0 else 0
        avg_loss = loss_sum / losses if losses > 0 else 0
        
        return {
            'period_days': period_days,
            'total_signals': total_closed,
            'win_rate': round(win_rate, 2),
            'wins': wins,
            'losses': losses,
            'total_return_pct': round(total_pnl, 2),
            'avg_win_pct': round(avg_win, 2),
            'avg_loss_pct': round(avg_loss, 2),
            'profit_factor': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0
        }
    
    def get_confidence_calibration(self) -> List[Dict]:
        """Check if confidence scores match actual outcomes"""
        # Join Trade with Signal to get confidence
        query = self.db.query(
            Signal.confidence,
            Trade.pnl_percent
        ).join(Trade, Trade.signal_id == Signal.id).filter(
            Trade.status.in_(['CLOSED', 'EXPIRED'])
        ).all()
        
        if not query:
            return []
        
        # Bucket by confidence ranges
        buckets = {
            '0.6-0.7': {'total': 0, 'wins': 0},
            '0.7-0.8': {'total': 0, 'wins': 0},
            '0.8-0.9': {'total': 0, 'wins': 0},
            '0.9-1.0': {'total': 0, 'wins': 0}
        }
        
        for conf, pnl in query:
            if not conf: continue
            
            if conf < 0.7:
                bucket = '0.6-0.7'
            elif conf < 0.8:
                bucket = '0.7-0.8'
            elif conf < 0.9:
                bucket = '0.8-0.9'
            else:
                bucket = '0.9-1.0'
            
            buckets[bucket]['total'] += 1
            if (pnl or 0) > 0:
                buckets[bucket]['wins'] += 1
        
        # Calculate win rates
        calibration = []
        for bucket_name, data in buckets.items():
            if data['total'] > 0:
                calibration.append({
                    'confidence_range': bucket_name,
                    'actual_win_rate': round(data['wins'] / data['total'] * 100, 2),
                    'sample_size': data['total']
                })
        
        return calibration
    
    def get_sector_performance(self, period_days: int = 30) -> List[Dict]:
        """Get performance broken down by sector based on graded signals"""
        from app.services.sector import SectorService
        
        # Initialize Sector Service (loads map)
        sector_service = SectorService()
        sector_map = sector_service.sector_map
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=period_days)
        
        # Get signals graded in the period
        graded_signals = self.db.query(Signal).filter(
            Signal.outcome_pnl_pct.isnot(None),
            Signal.outcome_graded_at >= cutoff_date
        ).all()
        
        if not graded_signals:
            return []
            
        # Aggregate by Sector
        sector_stats = {} # { sector_name: { wins, total, pnl_sum } }
        
        for signal in graded_signals:
            # Resolve sector
            sec = sector_map.get(signal.symbol, "Unknown")
            
            if sec not in sector_stats:
                sector_stats[sec] = {'wins': 0, 'total': 0, 'pnl_sum': 0.0}
            
            stats = sector_stats[sec]
            stats['total'] += 1
            stats['pnl_sum'] += signal.outcome_pnl_pct
            
            if signal.outcome_pnl_pct > 0:
                stats['wins'] += 1
        
        # Format Results
        results = []
        for sec, stats in sector_stats.items():
            total = stats['total']
            win_rate = (stats['wins'] / total * 100) if total > 0 else 0
            avg_return = stats['pnl_sum'] / total if total > 0 else 0
            
            results.append({
                'sector': sec,
                'total_trades': total,
                'win_rate': round(win_rate, 2),
                'avg_return_pct': round(avg_return, 2)
            })
            
        # Sort by Win Rate desc
        results.sort(key=lambda x: x['win_rate'], reverse=True)
        
        return results
    
    def get_signal_type_performance(self, period_days: int = 30) -> Dict:
        """Compare BUY vs SELL signal performance"""
        # In this system, we only have BUY signals that become Trades.
        # SELL signals are just Exit events for Trades.
        # So "Signal Type Performance" is really just "BUY Performance".
        # However, if we want to distinguish between long and short trades (if shorts existed),
        # we'd filter. But DAMA usually does Long only?
        # The prompt says "Current signal types: BUY / SELL / HOLD".
        # But `PerformanceEngine` logic creates creates trade on BUY.
        # So essentially all trades are Longs initiated by BUY.
        
        # We can just return the overall stats as BUY stats.
        metrics = self.get_performance_metrics(period_days)
        
        return {
            'BUY': {
                'total': metrics['total_signals'],
                'win_rate': metrics['win_rate'],
                'avg_return_pct': metrics['avg_win_pct'] # Approximation or use true avg return
            },
            'SELL': {
                'total': 0,
                'win_rate': 0,
                'avg_return_pct': 0
            }
        }

    def get_system_performance(self, period_days: int = 30, initial_capital: float = 10000.0) -> Dict:
        """
        Calculate system-wide performance metrics including CAGR and Equity Curve.
        Assumes 10% position sizing per theoretical trade.
        """
        from app.core.config import settings
        
        # Fetch ALL graded signals sorted by exit date (graded date)
        signals = self.db.query(Signal).filter(
            Signal.outcome_pnl_pct.isnot(None),
            Signal.outcome_graded_at.isnot(None)
        ).order_by(Signal.outcome_graded_at.asc()).all()
        
        if not signals:
            return {
                "cagr": 0.0,
                "max_drawdown": 0.0,
                "total_return": 0.0,
                "equity_curve": []
            }
            
        # Simulation
        current_equity = initial_capital
        equity_curve = [{"date": signals[0].outcome_graded_at - timedelta(days=1), "equity": initial_capital}]
        peak_equity = initial_capital
        max_drawdown = 0.0
        
        # Group signals by date to handle same-day exits
        from collections import defaultdict
        signals_by_date = defaultdict(list)
        for s in signals:
            if s.outcome_graded_at:
                signals_by_date[s.outcome_graded_at.date()].append(s)
                
        sorted_dates = sorted(signals_by_date.keys())
        
        for d in sorted_dates:
            for s in signals_by_date[d]:
                # Position Size logic
                position_amt = current_equity * getattr(settings, 'BACKTEST_DEFAULT_POSITION_SIZE', 0.1)
                trade_pnl_amt = position_amt * (s.outcome_pnl_pct / 100.0)
                current_equity += trade_pnl_amt
                
            # Track Equity Curve
            equity_curve.append({
                "date": d,
                "equity": round(current_equity, 2)
            })
            
            # Track Drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
            
            dd = (peak_equity - current_equity) / peak_equity
            if dd > max_drawdown:
                max_drawdown = dd
                
        # Calculate CAGR
        if len(signals) > 1:
            start_date = signals[0].outcome_graded_at
            end_date = signals[-1].outcome_graded_at
            days = max(1, (end_date - start_date).days)
            years = days / 365.25
            
            if years >= 1.0:
                cagr = ((current_equity / initial_capital) ** (1 / years)) - 1
            else:
                # If less than a year, don't annualize (prevents astronomical numbers)
                cagr = (current_equity - initial_capital) / initial_capital
        else:
            cagr = 0.0
            
        total_return_pct = round(((current_equity - initial_capital) / initial_capital) * 100, 2)

        return {
            "cagr": round(cagr * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "total_return": total_return_pct,
            "equity_curve": equity_curve,
            "final_equity": round(current_equity, 2)
        }

    def get_pnl_distribution(self, period_days: int = 30) -> List[Dict]:
        """Get distribution of graded Signal PnL percentages"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=period_days)
        
        signals = self.db.query(Signal).filter(
            Signal.outcome_pnl_pct.isnot(None),
            Signal.outcome_graded_at >= cutoff_date
        ).all()
        
        if not signals:
            return []
            
        # Buckets: [-12, -8), [-8, -4), [-4, 0), [0, 4), [4, 8), [8, 12), [12+]
        buckets = {
            'Deep Loss (<-8%)': 0,
            'Mid Loss (-8% to -4%)': 0,
            'Small Loss (-4% to 0%)': 0,
            'Small Win (0% to 4%)': 0,
            'Mid Win (4% to 8%)': 0,
            'Large Win (8% to 12%)': 0,
            'Extreme Win (>12%)': 0
        }
        
        for s in signals:
            pnl = s.outcome_pnl_pct
            if pnl < -8:
                buckets['Deep Loss (<-8%)'] += 1
            elif pnl < -4:
                buckets['Mid Loss (-8% to -4%)'] += 1
            elif pnl < 0:
                buckets['Small Loss (-4% to 0%)'] += 1
            elif pnl < 4:
                buckets['Small Win (0% to 4%)'] += 1
            elif pnl < 8:
                buckets['Mid Win (4% to 8%)'] += 1
            elif pnl < 12:
                buckets['Large Win (8% to 12%)'] += 1
            else:
                buckets['Extreme Win (>12%)'] += 1
                
        return [{"range": k, "count": v} for k, v in buckets.items()]

    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure"""
        return {
            'total_signals': 0,
            'win_rate': 0,
            'wins': 0,
            'losses': 0,
            'total_return_pct': 0,
            'avg_win_pct': 0,
            'avg_loss_pct': 0,
            'profit_factor': 0
        }
