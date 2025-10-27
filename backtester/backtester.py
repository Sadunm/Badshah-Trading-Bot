#!/usr/bin/env python3
"""
Vectorized Backtester
Realistic trading simulation with fees, slippage, and exchange rules
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable
import logging
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from .utils import ExchangeUtils, calculate_atr, validate_trade_signals
from .metrics import PerformanceMetrics

logger = logging.getLogger(__name__)

class VectorizedBacktester:
    """Vectorized backtester with realistic trading simulation"""
    
    def __init__(self, 
                 initial_capital: float = 10000.0,
                 maker_fee: float = 0.0005,
                 taker_fee: float = 0.001,
                 slippage_pct: float = 0.0005,
                 min_notional: float = 10.0,
                 step_size: float = 0.00001,
                 tick_size: float = 0.01):
        
        self.initial_capital = initial_capital
        self.exchange_utils = ExchangeUtils(
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            slippage_pct=slippage_pct,
            min_notional=min_notional,
            step_size=step_size,
            tick_size=tick_size
        )
        self.metrics_calculator = PerformanceMetrics()
        
        # Trading state
        self.current_capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        
    def backtest_strategy(self, 
                         data: pd.DataFrame,
                         strategy_func: Callable,
                         strategy_params: Dict,
                         symbol: str = "BTCUSDT") -> Dict:
        """
        Backtest a trading strategy
        
        Args:
            data: OHLCV data with columns ['open', 'high', 'low', 'close', 'volume']
            strategy_func: Strategy function that generates signals
            strategy_params: Strategy parameters
            symbol: Trading symbol
            
        Returns:
            Dict with backtest results and metrics
        """
        
        try:
            logger.info(f"Starting backtest for {symbol}")
            logger.info(f"Data shape: {data.shape}")
            logger.info(f"Date range: {data.index[0]} to {data.index[-1]}")
            
            # Reset state
            self._reset_state()
            
            # Generate signals
            signals = strategy_func(data, strategy_params)
            
            # Validate signals
            if not validate_trade_signals(signals):
                logger.warning("Invalid signals detected")
                return self._create_error_result("Invalid signals")
            
            # Simulate trades
            self._simulate_trades(data, signals, symbol)
            
            # Calculate metrics - ensure equity curve matches data length
            if len(self.equity_curve) == 0:
                self.equity_curve = [self.initial_capital]
            
            # Pad equity curve to match data length
            while len(self.equity_curve) < len(data):
                self.equity_curve.append(self.equity_curve[-1])
            
            # Truncate if too long
            if len(self.equity_curve) > len(data):
                self.equity_curve = self.equity_curve[:len(data)]
            
            equity_curve = pd.Series(self.equity_curve, index=data.index)
            metrics = self.metrics_calculator.calculate_comprehensive_metrics(
                equity_curve, self.trades
            )
            
            # Validate metrics
            validation = self.metrics_calculator.validate_metrics(metrics)
            
            result = {
                'symbol': symbol,
                'strategy_params': strategy_params,
                'metrics': validation['metrics'],
                'trades': self.trades,
                'equity_curve': equity_curve,
                'validation': validation,
                'data_info': {
                    'start_date': data.index[0],
                    'end_date': data.index[-1],
                    'total_periods': len(data),
                    'data_frequency': self._estimate_frequency(data.index)
                }
            }
            
            logger.info(f"Backtest completed for {symbol}")
            logger.info(f"Total trades: {len(self.trades)}")
            logger.info(f"Total return: {metrics['total_return_pct']:.2f}%")
            logger.info(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
            logger.info(f"Max drawdown: {metrics['max_drawdown_pct']:.2f}%")
            
            return result
        
        except Exception as e:
            logger.error(f"Error in backtest: {e}")
            return self._create_error_result(str(e))
    
    def _reset_state(self):
        """Reset backtester state"""
        self.current_capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = [self.initial_capital]
    
    def _simulate_trades(self, data: pd.DataFrame, signals: pd.Series, symbol: str):
        """Simulate trading based on signals"""
        
        position = 0
        entry_price = 0
        entry_time = None
        
        for i, (timestamp, row) in enumerate(data.iterrows()):
            signal = signals.iloc[i] if i < len(signals) else 0
            current_price = row['close']
            
            # Update equity curve (only if we have a position or made a trade)
            if position != 0 or len(self.trades) > 0:
                portfolio_value = self._calculate_portfolio_value(current_price, symbol)
                self.equity_curve.append(portfolio_value)
            
            # Handle signals
            if signal == 1 and position <= 0:  # Buy signal
                if position < 0:  # Close short position
                    self._close_position(entry_price, current_price, entry_time, timestamp, symbol)
                
                # Open long position
                position = 1
                entry_price = current_price
                entry_time = timestamp
                
            elif signal == -1 and position >= 0:  # Sell signal
                if position > 0:  # Close long position
                    self._close_position(entry_price, current_price, entry_time, timestamp, symbol)
                
                # Open short position
                position = -1
                entry_price = current_price
                entry_time = timestamp
    
    def _close_position(self, entry_price: float, exit_price: float, 
                       entry_time: pd.Timestamp, exit_time: pd.Timestamp, symbol: str):
        """Close a position and record trade"""
        
        # Calculate position size
        risk_pct = 0.02  # 2% risk per trade
        quantity, is_valid = self.exchange_utils.get_quantity_for_notional(
            self.current_capital, risk_pct, entry_price
        )
        
        if not is_valid or quantity == 0:
            logger.warning("Invalid quantity for trade")
            return
        
        # Determine trade side
        side = 'BUY' if exit_price > entry_price else 'SELL'
        
        # Calculate trade PnL
        trade_pnl = self.exchange_utils.calculate_trade_pnl(
            entry_price, exit_price, quantity, side
        )
        
        # Update capital
        self.current_capital += trade_pnl['net_pnl']
        
        # Record trade
        trade = {
            'entry_time': entry_time,
            'exit_time': exit_time,
            'entry_price': trade_pnl['effective_entry'],
            'exit_price': trade_pnl['effective_exit'],
            'quantity': quantity,
            'side': side,
            'gross_pnl': trade_pnl['gross_pnl'],
            'total_fees': trade_pnl['total_fees'],
            'net_pnl': trade_pnl['net_pnl'],
            'net_pnl_pct': trade_pnl['net_pnl_pct'],
            'symbol': symbol
        }
        
        self.trades.append(trade)
        
        logger.debug(f"Trade executed: {side} {quantity} {symbol} at {trade_pnl['effective_entry']:.2f}")
    
    def _calculate_portfolio_value(self, current_price: float, symbol: str) -> float:
        """Calculate current portfolio value"""
        return self.current_capital
    
    def _estimate_frequency(self, index: pd.DatetimeIndex) -> str:
        """Estimate data frequency"""
        if len(index) < 2:
            return "unknown"
        
        freq = pd.infer_freq(index)
        if freq:
            return freq
        
        # Manual estimation
        time_diff = (index[1] - index[0]).total_seconds()
        
        if time_diff < 60:
            return "1m"
        elif time_diff < 300:
            return "5m"
        elif time_diff < 900:
            return "15m"
        elif time_diff < 3600:
            return "1h"
        elif time_diff < 86400:
            return "1d"
        else:
            return "unknown"
    
    def _create_error_result(self, error_message: str) -> Dict:
        """Create error result"""
        return {
            'error': error_message,
            'metrics': {
                'total_return_pct': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown_pct': 0.0,
                'total_trades': 0,
                'win_rate_pct': 0.0
            },
            'trades': [],
            'equity_curve': pd.Series([self.initial_capital]),
            'validation': {'is_valid': False, 'issues': [error_message]}
        }

class MultiSymbolBacktester:
    """Backtester for multiple symbols"""
    
    def __init__(self, backtester_config: Dict):
        self.config = backtester_config
        self.results = {}
    
    def backtest_multiple_symbols(self, 
                                 data_dict: Dict[str, pd.DataFrame],
                                 strategy_func: Callable,
                                 strategy_params: Dict) -> Dict:
        """Backtest strategy on multiple symbols"""
        
        results = {}
        
        for symbol, data in data_dict.items():
            logger.info(f"Backtesting {symbol}")
            
            backtester = VectorizedBacktester(**self.config)
            result = backtester.backtest_strategy(data, strategy_func, strategy_params, symbol)
            
            results[symbol] = result
            
            # Log results
            if 'error' not in result:
                metrics = result['metrics']
                logger.info(f"{symbol} Results:")
                logger.info(f"  Total Return: {metrics['total_return_pct']:.2f}%")
                logger.info(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
                logger.info(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
                logger.info(f"  Total Trades: {metrics['total_trades']}")
            else:
                logger.error(f"{symbol} Error: {result['error']}")
        
        return results
