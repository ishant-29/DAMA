"""
Paper Trading Engine — simulates live trading without real money.
Automatically opens positions when BUY signals fire,
monitors stop/target levels, and closes positions automatically.
"""

import yfinance as yf
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.db.models import (
    PaperPortfolio, PaperTrade, PaperPerformanceSnapshot,
    TradeStatus, Signal
)
from app.services.position_sizer import KellyCriterionSizer
from app.core.config import settings

logger = logging.getLogger(__name__)


class PaperTradingEngine:

    MAX_POSITIONS = settings.PAPER_MAX_POSITIONS
    MAX_DRAWDOWN_HALT = settings.PAPER_MAX_DRAWDOWN_HALT
    DEFAULT_CAPITAL = settings.PAPER_DEFAULT_CAPITAL

    def __init__(self):
        self.sizer = KellyCriterionSizer()
        self._price_cache = {} # {symbol: (price, timestamp)}
        self.cache_duration = timedelta(minutes=5)

    # ── Portfolio Management ──────────────────────────

    def create_portfolio(
        self, db: Session, name: str = "Paper Portfolio", capital: float = None
    ) -> PaperPortfolio:
        portfolio = PaperPortfolio(
            name=name,
            initial_capital=capital or self.DEFAULT_CAPITAL,
            current_cash=capital or self.DEFAULT_CAPITAL,
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
        logger.info(f"Created paper portfolio '{name}' with ₹{portfolio.initial_capital:,.0f}")
        return portfolio

    def get_active_portfolio(self, db: Session) -> Optional[PaperPortfolio]:
        return (
            db.query(PaperPortfolio)
            .filter(PaperPortfolio.is_active == True)
            .first()
        )

    # ── Trade Execution ───────────────────────────────

    def open_trade_from_signal(self, signal: Signal, db: Session, custom_quantity: Optional[int] = None) -> Optional[PaperTrade]:
        portfolio = self.get_active_portfolio(db)
        if not portfolio:
            logger.warning("No active paper portfolio found")
            return None

        # Only apply hard limits if no custom quantity is provided
        if not custom_quantity:
            open_count = (
                db.query(PaperTrade)
                .filter(
                    PaperTrade.portfolio_id == portfolio.id,
                    PaperTrade.status == TradeStatus.OPEN,
                )
                .count()
            )
            if open_count >= self.MAX_POSITIONS:
                logger.info(f"[{signal.symbol}] Skipped — max positions reached")
                return None

            # Drawdown halt
            drawdown = ((portfolio.total_value - portfolio.initial_capital) / portfolio.initial_capital) * 100
            if drawdown <= -self.MAX_DRAWDOWN_HALT:
                logger.warning(f"Portfolio drawdown {drawdown:.1f}% — halting new entries")
                return None

        current_price = self._get_current_price(signal.symbol)
        if not current_price:
            return None

        if custom_quantity:
            quantity = custom_quantity
            actual_cost = quantity * current_price
            if actual_cost > portfolio.current_cash:
                logger.warning(f"Insufficient cash for custom quantity {quantity} of {signal.symbol}")
                return None
            kelly_pct = 0.0 # N/A for custom
        else:
            # Kelly sizing
            kelly_pct = getattr(signal, 'kelly_allocation_pct', 10.0) / 100
            allocated_capital = portfolio.total_value * kelly_pct
            allocated_capital = min(allocated_capital, portfolio.current_cash * 0.95)

            if allocated_capital < 5000:
                return None

            quantity = int(allocated_capital / current_price)
            if quantity == 0:
                return None
            actual_cost = quantity * current_price

        stop_loss = getattr(signal, 'stop_loss', current_price * 0.93) or (current_price * 0.93)
        target_price = getattr(signal, 'target_price', current_price * 1.09) or (current_price * 1.09)
        rr = getattr(signal, 'reward_risk_ratio', 1.5) or 1.5

        trade = PaperTrade(
            portfolio_id=portfolio.id,
            signal_id=signal.id,
            symbol=signal.symbol,
            sector=getattr(signal, 'sector', None),
            entry_date=datetime.utcnow(),
            entry_price=current_price,
            quantity=quantity,
            allocated_capital=actual_cost,
            allocation_pct=round((actual_cost / portfolio.total_value) * 100, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target_price, 2),
            reward_risk_ratio=round(rr, 2),
            signal_confidence=signal.confidence,
            kelly_allocation_pct=round(kelly_pct * 100, 2),
            market_regime=getattr(signal, 'market_regime', None),
            sector_momentum_score=getattr(signal, 'sector_momentum_score', None),
            status=TradeStatus.OPEN,
        )

        portfolio.current_cash -= actual_cost
        db.add(trade)
        db.commit()
        db.refresh(trade)

        logger.info(
            f"[PAPER OPEN] {signal.symbol} | Qty:{quantity} @₹{current_price:.2f} | "
            f"Stop:₹{stop_loss:.2f} Target:₹{target_price:.2f} | ₹{actual_cost:,.0f}"
        )
        return trade

    def manually_close_trade(self, db: Session, trade_id: int) -> Optional[PaperTrade]:
        portfolio = self.get_active_portfolio(db)
        if not portfolio:
            return None
            
        trade = (
            db.query(PaperTrade)
            .filter(
                PaperTrade.id == trade_id,
                PaperTrade.portfolio_id == portfolio.id,
                PaperTrade.status == TradeStatus.OPEN,
            )
            .first()
        )
        
        if not trade:
            return None
        
        current_price = self._get_current_price(trade.symbol)
        if not current_price:
            logger.warning(f"Using stale entry price for {trade.symbol} - price fetch failed")
            # Only use entry price as last resort, but log warning
            # Check if entry price is dangerously stale (more than 24 hours)
            entry_age = (datetime.utcnow() - trade.entry_date).total_seconds() / 3600
            if entry_age > 24:
                logger.error(f"Cannot close trade {trade.symbol} - entry price is {entry_age:.1f} hours old")
                return None
            current_price = trade.entry_price
            # Mark as stale in reason
            reason = "stale_price_fallback"
        else:
            reason = None
            
        days_held = (datetime.utcnow() - trade.entry_date).days
        self._close_trade(trade, portfolio, current_price, TradeStatus.CLOSED_MANUAL, days_held, db, exit_reason=reason)
        
        db.commit()
        self._take_performance_snapshot(portfolio, db)
        return trade

    # ── Daily Monitoring ──────────────────────────────

    def monitor_open_positions(self, db: Session) -> dict:
        portfolio = self.get_active_portfolio(db)
        if not portfolio:
            return {'monitored': 0}

        open_trades = (
            db.query(PaperTrade)
            .filter(
                PaperTrade.portfolio_id == portfolio.id,
                PaperTrade.status == TradeStatus.OPEN,
            )
            .all()
        )

        results = {'checked': len(open_trades), 'closed': 0, 'still_open': 0}

        for trade in open_trades:
            current_price = self._get_current_price(trade.symbol)
            if not current_price:
                continue

            days_held = (datetime.utcnow() - trade.entry_date).days
            closed = False

            if current_price <= trade.stop_loss:
                self._close_trade(trade, portfolio, trade.stop_loss, TradeStatus.CLOSED_STOP, days_held, db)
                closed = True
            elif current_price >= trade.target_price:
                self._close_trade(trade, portfolio, trade.target_price, TradeStatus.CLOSED_TARGET, days_held, db)
                closed = True
            elif days_held >= trade.max_hold_days:
                self._close_trade(trade, portfolio, current_price, TradeStatus.CLOSED_TIME, days_held, db)
                closed = True

            if closed:
                results['closed'] += 1
            else:
                results['still_open'] += 1

        db.commit()
        self._take_performance_snapshot(portfolio, db)
        return results

    def _close_trade(
        self, trade: PaperTrade, portfolio: PaperPortfolio,
        exit_price: float, status: TradeStatus, days_held: int, db: Session,
        exit_reason: str = None
    ):
        proceeds = exit_price * trade.quantity
        pnl_amount = proceeds - trade.allocated_capital
        pnl_pct = (pnl_amount / trade.allocated_capital) * 100

        trade.exit_date = datetime.utcnow()
        trade.exit_price = round(exit_price, 2)
        trade.status = status
        trade.pnl_amount = round(pnl_amount, 2)
        trade.pnl_pct = round(pnl_pct, 2)
        trade.holding_days = days_held
        trade.exit_reason = exit_reason or status.value
        trade.tax_category = "LTCG" if days_held >= 365 else "STCG"

        portfolio.current_cash += proceeds

        emoji = "✅" if pnl_pct > 0 else "❌"
        logger.info(
            f"[PAPER CLOSED] {emoji} {trade.symbol} | "
            f"P&L: ₹{pnl_amount:+,.0f} ({pnl_pct:+.1f}%) | {status.value} | {days_held}d"
        )

    def _take_performance_snapshot(self, portfolio: PaperPortfolio, db: Session):
        open_trades = (
            db.query(PaperTrade)
            .filter(
                PaperTrade.portfolio_id == portfolio.id,
                PaperTrade.status == TradeStatus.OPEN,
            )
            .all()
        )

        total_market_value = portfolio.current_cash
        for t in open_trades:
            price = self._get_current_price(t.symbol)
            total_market_value += (price * t.quantity) if price else t.allocated_capital

        daily_pnl = total_market_value - portfolio.initial_capital
        cumulative_pnl_pct = (daily_pnl / portfolio.initial_capital) * 100

        snapshots = (
            db.query(PaperPerformanceSnapshot)
            .filter(PaperPerformanceSnapshot.portfolio_id == portfolio.id)
            .order_by(PaperPerformanceSnapshot.snapshot_date)
            .all()
        )
        peak_value = max([s.total_value for s in snapshots], default=portfolio.initial_capital)
        peak_value = max(peak_value, total_market_value)
        drawdown_pct = ((total_market_value - peak_value) / peak_value) * 100

        snapshot = PaperPerformanceSnapshot(
            portfolio_id=portfolio.id,
            total_value=round(total_market_value, 2),
            cash=round(portfolio.current_cash, 2),
            invested=round(total_market_value - portfolio.current_cash, 2),
            daily_pnl=round(daily_pnl, 2),
            cumulative_pnl_pct=round(cumulative_pnl_pct, 2),
            open_positions=len(open_trades),
            drawdown_pct=round(drawdown_pct, 2),
        )
        db.add(snapshot)

    def _get_current_price(self, symbol: str) -> Optional[float]:
        # Check cache first
        now = datetime.utcnow()
        if symbol in self._price_cache:
            price, ts = self._price_cache[symbol]
            if now - ts < self.cache_duration:
                return price

        try:
            yf_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="1d")
            if not hist.empty:
                val = float(hist['Close'].iloc[-1])
                self._price_cache[symbol] = (val, now)
                return val
        except Exception:
            pass
        return None

    def _get_bulk_prices(self, symbols: list[str]) -> dict:
        """Fetch multiple prices at once to avoid sequential latency."""
        now = datetime.utcnow()
        results = {}
        to_fetch = []

        # Check cache
        for s in symbols:
            if s in self._price_cache:
                price, ts = self._price_cache[s]
                if now - ts < self.cache_duration:
                    results[s] = price
                else:
                    to_fetch.append(s)
            else:
                to_fetch.append(s)

        if not to_fetch:
            return results

        try:
            yf_symbols = [s if s.endswith(".NS") else f"{s}.NS" for s in to_fetch]
            # yfinance download is faster for multiple symbols
            data = yf.download(yf_symbols, period="1d", group_by="ticker", progress=False)
            
            for s in to_fetch:
                yf_s = s if s.endswith(".NS") else f"{s}.NS"
                try:
                    if len(to_fetch) == 1:
                        val = float(data['Close'].iloc[-1])
                    else:
                        val = float(data[yf_s]['Close'].iloc[-1])
                    
                    if val:
                        self._price_cache[s] = (val, now)
                        results[s] = val
                except:
                    continue
        except Exception as e:
            logger.error(f"Bulk fetch error: {e}")
            
        return results

    # ── Performance Report ────────────────────────────

    def get_performance_report(self, db: Session) -> dict:
        portfolio = self.get_active_portfolio(db)
        if not portfolio:
            return {'error': 'No active portfolio'}

        all_trades = (
            db.query(PaperTrade)
            .filter(PaperTrade.portfolio_id == portfolio.id)
            .all()
        )

        closed = [t for t in all_trades if t.status != TradeStatus.OPEN]
        open_pos = [t for t in all_trades if t.status == TradeStatus.OPEN]
        winners = [t for t in closed if t.pnl_pct and t.pnl_pct > 0]
        losers = [t for t in closed if t.pnl_pct and t.pnl_pct <= 0]

        win_rate = (len(winners) / len(closed) * 100) if closed else 0
        avg_winner = sum(t.pnl_pct for t in winners) / len(winners) if winners else 0
        avg_loser = sum(t.pnl_pct for t in losers) / len(losers) if losers else 0
        realized_total_pnl = sum(t.pnl_amount for t in closed if t.pnl_amount)

        gross_profit = sum(t.pnl_amount for t in winners if t.pnl_amount)
        gross_loss = abs(sum(t.pnl_amount for t in losers if t.pnl_amount) or 1)
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else 99.0

        # Calculate current market value of open positions
        open_pos_market_value = 0
        open_positions_report = []
        
        # Batch fetch prices
        symbols = [t.symbol for t in open_pos]
        prices = self._get_bulk_prices(symbols)
        
        for t in open_pos:
            current_price = prices.get(t.symbol) or t.entry_price
            market_value = current_price * t.quantity
            open_pos_market_value += market_value
            
            pnl_amount = market_value - t.allocated_capital
            pnl_pct = (pnl_amount / t.allocated_capital * 100) if t.allocated_capital else 0
            
            open_positions_report.append({
                'id': t.id,
                'symbol': t.symbol, 
                'sector': t.sector,
                'entry_price': t.entry_price, 
                'current_price': round(current_price, 2),
                'quantity': t.quantity,
                'allocated': t.allocated_capital,
                'market_value': round(market_value, 2),
                'pnl_amount': round(pnl_amount, 2),
                'pnl_pct': round(pnl_pct, 2),
                'stop_loss': t.stop_loss, 
                'target_price': t.target_price,
                'days_held': (datetime.utcnow() - t.entry_date).days,
                'confidence': t.signal_confidence,
            })

        current_portfolio_value = portfolio.current_cash + open_pos_market_value
        total_pnl = current_portfolio_value - portfolio.initial_capital
        total_pnl_pct = (total_pnl / portfolio.initial_capital * 100) if portfolio.initial_capital else 0

        snapshots = (
            db.query(PaperPerformanceSnapshot)
            .filter(PaperPerformanceSnapshot.portfolio_id == portfolio.id)
            .order_by(PaperPerformanceSnapshot.snapshot_date)
            .all()
        )
        equity_curve = [
            {
                'date': s.snapshot_date.strftime('%Y-%m-%d'),
                'value': s.total_value,
                'pnl_pct': s.cumulative_pnl_pct,
                'drawdown': s.drawdown_pct,
            }
            for s in snapshots
        ]
        
        # Calculate proper drawdown for live point
        peak_val = max([s.total_value for s in snapshots], default=portfolio.initial_capital)
        peak_val = max(peak_val, current_portfolio_value)
        live_drawdown = ((current_portfolio_value - peak_val) / peak_val) * 100
        
        equity_curve.append({
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'value': round(current_portfolio_value, 2),
            'pnl_pct': round(total_pnl_pct, 2),
            'drawdown': round(live_drawdown, 2),
        })

        return {
            'portfolio': {
                'name': portfolio.name,
                'initial_capital': portfolio.initial_capital,
                'current_value': round(current_portfolio_value, 2),
                'current_cash': round(portfolio.current_cash, 2),
                'total_pnl': round(total_pnl, 2),
                'total_pnl_pct': round(total_pnl_pct, 2),
            },
            'stats': {
                'total_trades': len(closed),
                'open_positions': len(open_pos),
                'win_rate': round(win_rate, 1),
                'avg_winner_pct': round(avg_winner, 2),
                'avg_loser_pct': round(avg_loser, 2),
                'total_realized_pnl': round(total_pnl, 2),
                'profit_factor': profit_factor,
            },
            'open_positions': open_positions_report,
            'equity_curve': equity_curve,
            'recent_trades': [
                {
                    'symbol': t.symbol,
                    'entry_price': t.entry_price, 'exit_price': t.exit_price,
                    'pnl_pct': t.pnl_pct, 'pnl_amount': t.pnl_amount,
                    'exit_reason': t.exit_reason, 'holding_days': t.holding_days,
                }
                for t in sorted(closed, key=lambda x: x.exit_date or datetime.min, reverse=True)[:10]
            ],
        }
