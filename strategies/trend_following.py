#!/usr/bin/env python3
"""
Trend Following Strategy
Simple moving average crossover strategy
"""

import pandas as pd
import numpy as np

class TrendFollowingStrategy:
    def __init__(self, lookback_period=20, entry_threshold=1.0, exit_threshold=0.02, 
                 take_profit=0.04, position_size_pct=1.0):
        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.take_profit = take_profit
        self.position_size_pct = position_size_pct
        
    def generate_signals(self, data):
        """Generate trading signals"""
        df = data.copy()
        
        # Calculate moving averages
        df['sma_fast'] = df['close'].rolling(window=self.lookback_period).mean()
        df['sma_slow'] = df['close'].rolling(window=self.lookback_period * 2).mean()
        
        # Calculate momentum
        df['momentum'] = df['close'].pct_change(self.lookback_period)
        
        # Generate signals
        df['signal'] = 0
        
        # Long entry: fast MA > slow MA and momentum > threshold
        long_condition = (df['sma_fast'] > df['sma_slow']) & (df['momentum'] > self.entry_threshold)
        df.loc[long_condition, 'signal'] = 1
        
        # Short entry: fast MA < slow MA and momentum < -threshold
        short_condition = (df['sma_fast'] < df['sma_slow']) & (df['momentum'] < -self.entry_threshold)
        df.loc[short_condition, 'signal'] = -1
        
        # Exit conditions
        df['exit_signal'] = 0
        
        # Exit long: momentum turns negative
        long_exit = (df['signal'].shift(1) == 1) & (df['momentum'] < -self.exit_threshold)
        df.loc[long_exit, 'exit_signal'] = -1
        
        # Exit short: momentum turns positive
        short_exit = (df['signal'].shift(1) == -1) & (df['momentum'] > self.exit_threshold)
        df.loc[short_exit, 'exit_signal'] = 1
        
        return df[['signal', 'exit_signal']]
    
    def get_position_size(self, current_price, portfolio_value):
        """Calculate position size"""
        return (portfolio_value * self.position_size_pct / 100) / current_price
