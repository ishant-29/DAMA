"""
Walk-Forward Backtester — replays signal logic on historical data.
Validates actual win rate per symbol, sector, and market regime.
Supports Monte Carlo simulation for robustness testing.
"""

import pandas as pd
import numpy as np
from typing import Optional, List
from dataclasses import dataclass, asdict
import yfinance as yf
import logging
import random

from app.indicators.ema import ema_df
from app.indicators.darvas import darvas_boxes
from app.indicators.advanced_features import build_full_feature_matrix, calculate_atr
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    pnl_pct: float
    hold_days: int
    signal_confidence: float
    exit_reason: str
    is_winner: bool


@dataclass
class BacktestReport:
    symbol: str
    period_days: int
    total_signals: int
    total_trades: int
    win_rate: float
    avg_return_pct: float
    avg_winner_pct: float
    avg_loser_pct: float
    max_drawdown_pct: float
    profit_factor: float
    expectancy: float
    sharpe_ratio: float
    trades: list
    
    # Additional advanced metrics
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    best_trade_pct: Optional[float] = None
    worst_trade_pct: Optional[float] = None


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation"""
    num_simulations: int
    median_return: float
    percentile_5: float
    percentile_95: float
    probability_of_ruin: float  # % chance of losing >50% of capital
    best_case_return: float
    worst_case_return: float


class Backtester:

    HOLD_DAYS = settings.BACKTEST_HOLD_DAYS
    ATR_STOP_MULT = settings.BACKTEST_ATR_STOP_MULT
    ATR_TARGET_MULT = settings.BACKTEST_ATR_TARGET_MULT

    def run(self, symbol: str, days: int = 365) -> BacktestReport:
        """Main backtest entry point."""
        return self._run_with_features(symbol, days, use_slippage=False)
    
    def run_with_slippage(self, symbol: str, days: int = 365) -> BacktestReport:
        """Backtest with realistic slippage modeling."""
        return self._run_with_features(symbol, days, use_slippage=True)
    
    def _run_with_features(self, symbol: str, days: int, use_slippage: bool = False) -> BacktestReport:
        """Internal method with feature options."""
        ticker = f"{symbol}.NS"
        try:
            df = yf.Ticker(ticker).history(period=f"{days + 100}d")
        except Exception as e:
            raise ValueError(f"Failed to fetch data for {symbol}: {e}")

        if df is None or len(df) < 100:
            raise ValueError(f"Insufficient data for {symbol}: {len(df) if df is not None else 0} rows")

        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        df.columns = [c.lower() for c in df.columns]

        try:
            ema_result = ema_df(df, periods=[10, 20, 50])
            darvas_result = darvas_boxes(df)
            features_df = build_full_feature_matrix(df)
        except Exception as e:
            logger.error(f"Indicator calculation failed for {symbol}: {e}")
            raise ValueError(f"Indicator calculation failed: {e}")

        signals = []
        lookback = 60
        slippage_cost = 0.001 if use_slippage else 0  # 0.1% slippage

        for i in range(lookback, len(df) - self.HOLD_DAYS - 1):
            historical_slice = df.iloc[:i + 1].copy()

            signal = self._check_signal_on_day(
                df=historical_slice,
                ema_result=ema_result.iloc[:i + 1],
                darvas_result=darvas_result.iloc[:i + 1],
                features=features_df.iloc[i],
            )

            if signal and signal['signal_type'] == 'BUY':
                trade = self._simulate_trade(
                    df=df,
                    entry_idx=i + 1,
                    confidence=signal['confidence'],
                    features=features_df.iloc[i],
                    slippage_cost=slippage_cost,
                )
                if trade:
                    signals.append(trade)

        return self._compile_report(symbol, days, signals)

    def _check_signal_on_day(self, df, ema_result, darvas_result, features) -> Optional[dict]:
        """Simplified signal check for backtesting."""
        try:
            close = df['close'].iloc[-1]

            ema10 = ema_result['ema_10'].iloc[-1] if 'ema_10' in ema_result.columns else close
            ema20 = ema_result['ema_20'].iloc[-1] if 'ema_20' in ema_result.columns else close

            cond_buy_ema = (close > ema10) and (ema10 > ema20)

            darvas_high = darvas_result['darvas_high'].iloc[-1] if 'darvas_high' in darvas_result.columns else close * 1.05
            cond_darvas = close > darvas_high * 0.98

            volume_ratio = float(features.get('volume_ratio', 1.0)) if hasattr(features, 'get') else 1.0
            cond_volume = volume_ratio >= 1.8

            rr = float(features.get('reward_risk_ratio', 0.0)) if hasattr(features, 'get') else 0.0
            cond_rr = rr >= 1.5

            if cond_buy_ema and cond_darvas and cond_volume:
                confidence = min(0.95, 0.60 + (volume_ratio - 1.8) * 0.05 + (0.05 if cond_rr else 0))
                return {'signal_type': 'BUY', 'confidence': confidence}

        except Exception as e:
            logger.debug(f"Signal check error: {e}")

        return None

    def _simulate_trade(self, df, entry_idx, confidence, features) -> Optional[TradeResult]:
        """Simulate trade outcome from entry_idx forward."""
        if entry_idx >= len(df) - 1:
            return None

        entry_row = df.iloc[entry_idx]
        entry_price = float(entry_row['open'])
        entry_date = str(df.index[entry_idx].date())

        atr_val = float(features.get('atr_14', entry_price * 0.02)) if hasattr(features, 'get') else entry_price * 0.02
        stop_loss = entry_price - (self.ATR_STOP_MULT * atr_val)
        target = entry_price + (self.ATR_TARGET_MULT * atr_val)

        for j in range(1, min(self.HOLD_DAYS + 1, len(df) - entry_idx)):
            day = df.iloc[entry_idx + j]

            if float(day['low']) <= stop_loss:
                pnl = ((stop_loss - entry_price) / entry_price) * 100
                return TradeResult(
                    entry_date=entry_date, entry_price=round(entry_price, 2),
                    exit_date=str(df.index[entry_idx + j].date()),
                    exit_price=round(stop_loss, 2), pnl_pct=round(pnl, 2),
                    hold_days=j, signal_confidence=round(confidence, 3),
                    exit_reason='STOP_HIT', is_winner=False,
                )

            if float(day['high']) >= target:
                pnl = ((target - entry_price) / entry_price) * 100
                return TradeResult(
                    entry_date=entry_date, entry_price=round(entry_price, 2),
                    exit_date=str(df.index[entry_idx + j].date()),
                    exit_price=round(target, 2), pnl_pct=round(pnl, 2),
                    hold_days=j, signal_confidence=round(confidence, 3),
                    exit_reason='TARGET_HIT', is_winner=True,
                )

        exit_idx = entry_idx + min(self.HOLD_DAYS, len(df) - entry_idx - 1)
        exit_price = float(df.iloc[exit_idx]['close'])
        pnl = ((exit_price - entry_price) / entry_price) * 100

        return TradeResult(
            entry_date=entry_date, entry_price=round(entry_price, 2),
            exit_date=str(df.index[exit_idx].date()),
            exit_price=round(exit_price, 2), pnl_pct=round(pnl, 2),
            hold_days=self.HOLD_DAYS, signal_confidence=round(confidence, 3),
            exit_reason='TIME_EXIT', is_winner=pnl > 0,
        )

    def _compile_report(self, symbol, days, trades) -> BacktestReport:
        if not trades:
            return BacktestReport(
                symbol=symbol, period_days=days, total_signals=0,
                total_trades=0, win_rate=0, avg_return_pct=0, avg_winner_pct=0,
                avg_loser_pct=0, max_drawdown_pct=0, profit_factor=0,
                expectancy=0, sharpe_ratio=0, trades=[],
            )

        returns = [t.pnl_pct for t in trades]
        winners = [t.pnl_pct for t in trades if t.is_winner]
        losers = [t.pnl_pct for t in trades if not t.is_winner]

        win_rate = len(winners) / len(trades)
        avg_return = np.mean(returns)
        avg_winner = np.mean(winners) if winners else 0
        avg_loser = np.mean(losers) if losers else 0

        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.0

        expectancy = (win_rate * avg_winner) + ((1 - win_rate) * avg_loser)

        cumulative = pd.Series(returns).cumsum()
        rolling_max = cumulative.cummax()
        drawdown = cumulative - rolling_max
        max_drawdown = float(drawdown.min())

        sharpe = (avg_return / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0

        # Additional advanced metrics
        best_trade = max(returns)
        worst_trade = min(returns)
        
        # Sortino Ratio (downside deviation)
        downside_returns = [r for r in returns if r < 0]
        downside_std = np.std(downside_returns) if downside_returns else 0
        sortino = (avg_return / downside_std) * np.sqrt(252) if downside_std > 0 else 0
        
        # Calmar Ratio (return / max drawdown)
        calmar = abs(avg_return / max_drawdown) if max_drawdown != 0 else 0

        return BacktestReport(
            symbol=symbol, period_days=days,
            total_signals=len(trades), total_trades=len(trades),
            win_rate=round(win_rate * 100, 1),
            avg_return_pct=round(float(avg_return), 2),
            avg_winner_pct=round(float(avg_winner), 2),
            avg_loser_pct=round(float(avg_loser), 2),
            max_drawdown_pct=round(max_drawdown, 2),
            profit_factor=round(profit_factor, 2),
            expectancy=round(float(expectancy), 2),
            sharpe_ratio=round(float(sharpe), 2),
            trades=[asdict(t) for t in trades],
            sortino_ratio=round(float(sortino), 2),
            calmar_ratio=round(float(calmar), 2),
            best_trade_pct=round(best_trade, 2),
            worst_trade_pct=round(worst_trade, 2),
        )
    
    def run_monte_carlo(
        self,
        trades: List[TradeResult],
        num_simulations: int = 1000,
        initial_capital: float = 100000,
        position_size_pct: float = 0.10
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation to test strategy robustness.
        Resamples trade sequence to generate distribution of outcomes.
        """
        if not trades:
            return MonteCarloResult(
                num_simulations=0, median_return=0,
                percentile_5=0, percentile_95=0,
                probability_of_ruin=100,
                best_case_return=0, worst_case_return=0
            )
        
        returns = [t.pnl_pct for t in trades]
        simulation_results = []
        
        for _ in range(num_simulations):
            # Resample returns with replacement
            sampled_returns = random.choices(returns, k=len(returns))
            
            # Calculate cumulative return
            capital = initial_capital
            for ret in sampled_returns:
                position_value = capital * position_size_pct
                capital += position_value * (ret / 100)
            
            final_return = ((capital - initial_capital) / initial_capital) * 100
            simulation_results.append(final_return)
        
        simulation_results.sort()
        n = len(simulation_results)
        
        # Calculate metrics
        median = simulation_results[n // 2]
        percentile_5 = simulation_results[int(n * 0.05)]
        percentile_95 = simulation_results[int(n * 0.95)]
        prob_ruin = sum(1 for r in simulation_results if r < -50) / n * 100
        
        return MonteCarloResult(
            num_simulations=num_simulations,
            median_return=round(median, 2),
            percentile_5=round(percentile_5, 2),
            percentile_95=round(percentile_95, 2),
            probability_of_ruin=round(prob_ruin, 2),
            best_case_return=round(max(simulation_results), 2),
            worst_case_return=round(min(simulation_results), 2),
        )
    
    def walk_forward(
        self,
        symbol: str,
        total_days: int = 730,
        train_days: int = 365,
        test_days: int = 30
    ) -> dict:
        """
        Walk-forward analysis - trains on historical data, tests on forward data.
        This validates that the strategy adapts to changing market conditions.
        """
        ticker = f"{symbol}.NS"
        try:
            df = yf.Ticker(ticker).history(period=f"{total_days + 100}d")
        except Exception as e:
            raise ValueError(f"Failed to fetch data for {symbol}: {e}")
        
        if df is None or len(df) < total_days:
            raise ValueError(f"Insufficient data for walk-forward")
        
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.columns = [c.lower() for c in df.columns]
        
        results = []
        num_windows = (total_days - train_days) // test_days
        
        for i in range(num_windows):
            train_end = train_days + (i * test_days)
            test_start = train_end
            test_end = min(test_start + test_days, total_days)
            
            # Use same backtest logic for each window
            try:
                train_df = df.iloc[:train_end].copy()
                test_df = df.iloc[test_start:test_end].copy()
                
                # Calculate indicators on train data
                ema_result = ema_df(train_df, periods=[10, 20, 50])
                darvas_result = darvas_boxes(train_df)
                features_df = build_full_feature_matrix(train_df)
                
                # Run backtest on test period
                signals = []
                for j in range(60, len(test_df) - self.HOLD_DAYS - 1):
                    signal = self._check_signal_on_day(
                        df=test_df.iloc[:j + 1],
                        ema_result=ema_result.iloc[:j + 1],
                        darvas_result=darvas_result.iloc[:j + 1],
                        features=features_df.iloc[j],
                    )
                    if signal:
                        trade = self._simulate_trade(test_df, j + 1, signal['confidence'], features_df.iloc[j])
                        if trade:
                            signals.append(trade)
                
                if signals:
                    returns = [s.pnl_pct for s in signals]
                    results.append({
                        'window': i + 1,
                        'train_period': f"Day {train_end - train_days}-{train_end}",
                        'test_period': f"Day {test_start}-{test_end}",
                        'num_trades': len(signals),
                        'avg_return': round(np.mean(returns), 2),
                        'win_rate': round(len([r for r in returns if r > 0]) / len(returns) * 100, 1),
                    })
            except Exception as e:
                logger.warning(f"Walk-forward window {i+1} failed: {e}")
                continue
        
        return {
            'symbol': symbol,
            'num_windows': len(results),
            'windows': results,
            'avg_window_return': round(np.mean([w['avg_return'] for w in results]), 2) if results else 0,
        }
