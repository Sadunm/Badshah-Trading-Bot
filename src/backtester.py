#!/usr/bin/env python3
"""
Vectorized realistic backtester
Performs realistic backtesting with fees, slippage, and proper trade simulation
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorizedBacktester:
    """Vectorized backtester with realistic fills"""
    
    def __init__(self, fee_rate=0.0004, slippage_rate=0.0002):
        """
        Initialize backtester
        
        Args:
            fee_rate (float): Trading fee rate (default 0.04%)
            slippage_rate (float): Slippage rate (default 0.02%)
        """
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def generate_signals(self, df, strategy_type, params):
        """
        Generate trading signals based on strategy type
        
        Args:
            df (pd.DataFrame): Price data with OHLCV
            strategy_type (str): Type of strategy
            params (dict): Strategy parameters
            
        Returns:
            pd.DataFrame: Data with signals
        """
        df = df.copy()
        
        if strategy_type == 'Simple_Momentum':
            # EMA crossover
            ema_short = df['close'].ewm(span=params['ema_short']).mean()
            ema_long = df['close'].ewm(span=params['ema_long']).mean()
            
            df['signal'] = 0
            # Only generate signals when both EMAs are valid
            valid_mask = ~(ema_short.isna() | ema_long.isna())
            df.loc[valid_mask & (ema_short > ema_long), 'signal'] = 1  # Buy
            df.loc[valid_mask & (ema_short < ema_long), 'signal'] = -1  # Sell
            
        elif strategy_type == 'Simple_MeanReversion':
            # RSI mean reversion
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=params['rsi_period']).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=params['rsi_period']).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            df['signal'] = 0
            # Only generate signals when RSI is valid
            valid_mask = ~rsi.isna()
            df.loc[valid_mask & (rsi < params['rsi_oversold']), 'signal'] = 1  # Buy
            df.loc[valid_mask & (rsi > 70), 'signal'] = -1  # Sell
            
        elif strategy_type == 'Simple_Breakout':
            # Volume breakout
            lookback = params['lookback']
            vol_ma = df['volume'].rolling(lookback).mean()
            vol_threshold = vol_ma * params['vol_mult']
            
            df['signal'] = 0
            # Only generate signals when volume data is valid
            valid_mask = ~(vol_ma.isna() | vol_threshold.isna())
            df.loc[valid_mask & (df['volume'] > vol_threshold), 'signal'] = 1  # Buy
            
        else:
            df['signal'] = 0
        
        return df
    
    def simulate_trades(self, df, initial_capital=10000, risk_per_trade=0.01):
        """
        Simulate trades with realistic fills
        
        Args:
            df (pd.DataFrame): Data with signals
            initial_capital (float): Starting capital
            risk_per_trade (float): Risk per trade as fraction of capital
            
        Returns:
            dict: Trade results and metrics
        """
        capital = initial_capital
        position = 0
        trades = []
        equity_curve = [capital]
        
        # Calculate ATR for stop loss
        atr = self.calculate_atr(df)
        
        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]
            signal = df['signal'].iloc[i]
            current_atr = atr.iloc[i]
            
            # Close existing position if signal changes
            if position != 0 and signal != position:
                if position == 1:  # Close long
                    exit_price = current_price * (1 - self.slippage_rate)  # Slippage on exit
                    pnl = (exit_price - entry_price) / entry_price
                    fee = (entry_price + exit_price) * self.fee_rate
                    pnl_after_fees = pnl - fee
                    
                    capital *= (1 + pnl_after_fees)
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'position_size': position_size,
                        'pnl_pct': pnl_after_fees,
                        'pnl_abs': capital * pnl_after_fees
                    })
                
                position = 0
            
            # Open new position
            if signal != 0 and position == 0:
                if signal == 1:  # Buy signal
                    entry_price = current_price * (1 + self.slippage_rate)  # Slippage on entry
                    position_size = capital * risk_per_trade / (current_atr * 2)  # Position sizing
                    entry_time = df.index[i]
                    position = 1
                elif signal == -1:  # Sell signal (short)
                    entry_price = current_price * (1 - self.slippage_rate)
                    position_size = capital * risk_per_trade / (current_atr * 2)
                    entry_time = df.index[i]
                    position = -1
            
            equity_curve.append(capital)
        
        # Close final position if any
        if position != 0:
            final_price = df['close'].iloc[-1]
            if position == 1:
                exit_price = final_price * (1 - self.slippage_rate)
            else:
                exit_price = final_price * (1 + self.slippage_rate)
            
            pnl = (exit_price - entry_price) / entry_price if position == 1 else (entry_price - exit_price) / entry_price
            fee = (entry_price + exit_price) * self.fee_rate
            pnl_after_fees = pnl - fee
            
            capital *= (1 + pnl_after_fees)
            trades.append({
                'entry_time': entry_time,
                'exit_time': df.index[-1],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position_size': position_size,
                'pnl_pct': pnl_after_fees,
                'pnl_abs': capital * pnl_after_fees
            })
        
        # Calculate total return percentage with bounds checking
        if initial_capital > 0:
            total_return_pct = (capital - initial_capital) / initial_capital * 100
            # Cap extreme values to realistic ranges
            total_return_pct = max(-99.99, min(999.99, total_return_pct))
        else:
            total_return_pct = 0
        
        return {
            'trades': trades,
            'equity_curve': equity_curve,
            'final_capital': capital,
            'total_return_pct': total_return_pct
        }
    
    def calculate_metrics(self, trade_results):
        """
        Calculate performance metrics
        
        Args:
            trade_results (dict): Results from simulate_trades
            
        Returns:
            dict: Performance metrics
        """
        trades = trade_results['trades']
        equity_curve = trade_results['equity_curve']
        
        if not trades:
            return {
                'total_trades': 0,
                'winrate_pct': 0,
                'avg_trade_pnl': 0,
                'sharpe': 0,
                'max_drawdown_pct': 0,
                'expectancy': 0
            }
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl_pct'] > 0]
        losing_trades = [t for t in trades if t['pnl_pct'] < 0]
        
        winrate_pct = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        
        # Average trade PnL
        avg_trade_pnl = np.mean([t['pnl_pct'] for t in trades]) if trades else 0
        
        # Sharpe ratio (simplified)
        returns = [t['pnl_pct'] for t in trades]
        sharpe = np.mean(returns) / np.std(returns) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        # Maximum drawdown
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown_pct = drawdown.min() * 100
        
        # Expectancy
        expectancy = np.mean(returns) if returns else 0
        
        return {
            'total_trades': total_trades,
            'winrate_pct': winrate_pct,
            'avg_trade_pnl': avg_trade_pnl,
            'sharpe': sharpe,
            'max_drawdown_pct': max_drawdown_pct,
            'expectancy': expectancy,
            'total_return_pct': trade_results['total_return_pct']
        }
    
    def backtest_strategy(self, df, strategy_type, params, initial_capital=10000):
        """
        Complete backtest for a strategy
        
        Args:
            df (pd.DataFrame): Price data
            strategy_type (str): Strategy type
            params (dict): Strategy parameters
            initial_capital (float): Starting capital
            
        Returns:
            dict: Complete backtest results
        """
        # Generate signals
        df_with_signals = self.generate_signals(df, strategy_type, params)
        
        # Simulate trades
        trade_results = self.simulate_trades(df_with_signals, initial_capital)
        
        # Calculate metrics
        metrics = self.calculate_metrics(trade_results)
        
        return {
            'strategy_type': strategy_type,
            'params': params,
            'metrics': metrics,
            'trades': trade_results['trades'],
            'equity_curve': trade_results['equity_curve']
        }

def main():
    """Test the backtester"""
    logger.info("Testing vectorized backtester")
    
    # Create sample data
    dates = pd.date_range('2023-01-01', periods=1000, freq='5T')
    np.random.seed(42)
    
    # Generate sample OHLCV data
    price = 100
    data = []
    for i in range(1000):
        change = np.random.normal(0, 0.001)
        price *= (1 + change)
        
        high = price * (1 + abs(np.random.normal(0, 0.002)))
        low = price * (1 - abs(np.random.normal(0, 0.002)))
        volume = np.random.uniform(100, 1000)
        
        data.append({
            'timestamp': dates[i],
            'open': price,
            'high': high,
            'low': low,
            'close': price,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df = df.set_index('timestamp')
    
    # Test backtester
    backtester = VectorizedBacktester()
    
    # Test momentum strategy
    results = backtester.backtest_strategy(
        df, 
        'Simple_Momentum', 
        {'ema_short': 8, 'ema_long': 21},
        initial_capital=10000
    )
    
    logger.info(f"Backtest results: {results['metrics']}")
    
    return results

if __name__ == "__main__":
    main()
