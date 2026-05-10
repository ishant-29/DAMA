"""
Backtesting API endpoints - includes advanced features
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.backtester import Backtester
from app.services.multi_timeframe import get_mtf_analyzer
from app.services import data_provider
from app.db.models import Signal
from datetime import datetime, timedelta
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
import logging

from app.core.config import settings
from app.auth import get_current_user, User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run")
async def run_backtest(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    initial_capital: float = Query(settings.BACKTEST_DEFAULT_INITIAL_CAPITAL, description="Initial capital"),
    position_size_pct: float = Query(settings.BACKTEST_DEFAULT_POSITION_SIZE, description="Position size as % of capital"),
    stop_loss_pct: float = Query(settings.BACKTEST_DEFAULT_STOP_LOSS, description="Stop loss percentage"),
    take_profit_pct: float = Query(settings.BACKTEST_DEFAULT_TAKE_PROFIT, description="Take profit percentage"),
    use_slippage: bool = Query(False, description="Include slippage modeling"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run backtest on historical signals with optional slippage modeling."""
    try:
        signals = db.query(Signal).filter(
            Signal.timestamp >= datetime.strptime(start_date, '%Y-%m-%d'),
            Signal.timestamp <= datetime.strptime(end_date, '%Y-%m-%d')
        ).all()
        
        if not signals:
            raise HTTPException(status_code=404, detail="No signals found in date range")
        
        signal_dicts = [{
            'symbol': s.symbol,
            'signal_type': s.signal_type,
            'timestamp': s.timestamp.isoformat(),
            'confidence': s.confidence
        } for s in signals]
        
        symbols = list(set(s.symbol for s in signals))
        historical_data = {}
        
        def fetch_one_symbol(symbol: str):
            df = data_provider.fetch_ticker_data(symbol, period=settings.BACKTEST_DATA_PERIOD)
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
                if 'date' not in df.columns:
                    df = df.reset_index()
                    df.columns = [c.lower() for c in df.columns]
                return symbol, df
            return symbol, None

        with ThreadPoolExecutor(max_workers=settings.DATA_FETCH_WORKERS) as executor:
            results_list = list(executor.map(fetch_one_symbol, symbols))
        historical_data = {sym: df for sym, df in results_list if df is not None}
        
        backtester = Backtester(
            initial_capital=initial_capital,
            position_size_pct=position_size_pct
        )
        
        if use_slippage:
            results = backtester.run_backtest_with_slippage(
                signals=signal_dicts,
                historical_data=historical_data,
                start_date=start_date,
                end_date=end_date,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct
            )
        else:
            results = backtester.run_backtest(
                signals=signal_dicts,
                historical_data=historical_data,
                start_date=start_date,
                end_date=end_date,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct
            )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/symbol/{symbol}")
async def backtest_symbol(
    symbol: str,
    days: int = Query(365, ge=90, le=730, description="Backtest period in days"),
    use_slippage: bool = Query(False, description="Include slippage modeling"),
    current_user: User = Depends(get_current_user),
):
    """Run backtest on a single symbol with advanced metrics."""
    try:
        backtester = Backtester()
        
        if use_slippage:
            report = backtester.run_with_slippage(symbol, days)
        else:
            report = backtester.run(symbol, days)
        
        return {
            'report': {
                'symbol': report.symbol,
                'period_days': report.period_days,
                'total_trades': report.total_trades,
                'win_rate': report.win_rate,
                'avg_return_pct': report.avg_return_pct,
                'max_drawdown_pct': report.max_drawdown_pct,
                'profit_factor': report.profit_factor,
                'sharpe_ratio': report.sharpe_ratio,
                'sortino_ratio': report.sortino_ratio,
                'calmar_ratio': report.calmar_ratio,
                'best_trade_pct': report.best_trade_pct,
                'worst_trade_pct': report.worst_trade_pct,
            },
            'trades': report.trades[:20],  # Limit to 20 trades for response size
        }
    except Exception as e:
        logger.error(f"Symbol backtest error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbol/{symbol}/monte-carlo")
async def monte_carlo_simulation(
    symbol: str,
    days: int = Query(365, ge=90, le=730),
    simulations: int = Query(1000, ge=100, le=10000),
    initial_capital: float = Query(100000, ge=10000),
    position_size_pct: float = Query(0.10, ge=0.01, le=0.5),
    current_user: User = Depends(get_current_user),
):
    """Run Monte Carlo simulation on symbol backtest results."""
    try:
        backtester = Backtester()
        report = backtester.run(symbol, days)
        
        if not report.trades:
            raise HTTPException(status_code=400, detail="No trades generated for Monte Carlo simulation")
        
        # Import TradeResult
        from app.services.backtester import TradeResult
        trade_results = [TradeResult(**t) for t in report.trades]
        
        mc_result = backtester.run_monte_carlo(
            trades=trade_results,
            num_simulations=simulations,
            initial_capital=initial_capital,
            position_size_pct=position_size_pct,
        )
        
        return {
            'symbol': symbol,
            'backtest_summary': {
                'total_trades': report.total_trades,
                'win_rate': report.win_rate,
                'avg_return_pct': report.avg_return_pct,
            },
            'monte_carlo': {
                'num_simulations': mc_result.num_simulations,
                'median_return': mc_result.median_return,
                'percentile_5': mc_result.percentile_5,
                'percentile_95': mc_result.percentile_95,
                'probability_of_ruin': mc_result.probability_of_ruin,
                'best_case_return': mc_result.best_case_return,
                'worst_case_return': mc_result.worst_case_return,
            },
            'interpretation': _interpret_mc_results(mc_result),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Monte Carlo error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _interpret_mc_results(mc_result) -> dict:
    """Interpret Monte Carlo results for trading insights."""
    interpretation = {
        'risk_level': 'UNKNOWN',
        'recommendation': '',
    }
    
    if mc_result.probability_of_ruin > 20:
        interpretation['risk_level'] = 'HIGH'
        interpretation['recommendation'] = 'Strategy has significant risk of catastrophic loss. Consider reducing position size.'
    elif mc_result.probability_of_ruin > 5:
        interpretation['risk_level'] = 'MEDIUM'
        interpretation['recommendation'] = 'Moderate risk of ruin. Monitor closely and consider position sizing adjustments.'
    else:
        interpretation['risk_level'] = 'LOW'
        interpretation['recommendation'] = 'Strategy shows acceptable risk levels.'
    
    if mc_result.percentile_5 < -30:
        interpretation['worst_case_warning'] = 'In worst 5% of scenarios, losses exceed 30%'
    
    return interpretation


@router.get("/symbol/{symbol}/multi-timeframe")
async def multi_timeframe_analysis(
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """Get multi-timeframe analysis for trend confirmation."""
    try:
        analyzer = get_mtf_analyzer()
        result = analyzer.get_multi_timeframe_analysis(symbol)
        aligned = analyzer.get_aligned_signals(symbol)
        
        return {
            'analysis': result,
            'signal': aligned,
        }
    except Exception as e:
        logger.error(f"Multi-timeframe error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/walk-forward/{symbol}")
async def walk_forward_analysis(
    symbol: str,
    total_days: int = Query(730, ge=365, le=1825),
    train_days: int = Query(365, ge=180),
    test_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
):
    """Run walk-forward analysis to validate strategy robustness."""
    try:
        backtester = Backtester()
        result = backtester.walk_forward(
            symbol=symbol,
            total_days=total_days,
            train_days=train_days,
            test_days=test_days,
        )
        return result
    except Exception as e:
        logger.error(f"Walk-forward error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick", deprecated=True)
async def quick_backtest(
    days: int = Query(30, ge=7, le=365, description="Lookback days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run quick backtest on recent signals"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    return await run_backtest(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        db=db
    )
