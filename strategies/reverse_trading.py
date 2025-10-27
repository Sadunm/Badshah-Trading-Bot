#!/usr/bin/env python3
"""
Reverse Trading Strategy (Mean Reversion)
Trading against the trend using support/resistance and RSI
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def reverse_trading_strategy(data: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Reverse trading (mean reversion) strategy implementation
    
    Strategy Logic:
    - Price near support/resistance levels
    - RSI oversold/overbought conditions
    - Fade the trend
    """
    
    try:
        # Extract parameters
        rsi_period = params.get('rsi_period', 14)
        support_lookback = params.get('support_lookback', 50)
        threshold_pct = params.get('threshold_pct', 0.01)  # 1%
        
        # Calculate indicators
        data = data.copy()
        
        # RSI calculation
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        # Support and resistance levels
        data['support'] = data['low'].rolling(window=support_lookback).min()
        data['resistance'] = data['high'].rolling(window=support_lookback).max()
        
        # Price position relative to support/resistance
        data['price_near_support'] = (
            data['close'] <= data['support'] * (1 + threshold_pct)
        )
        data['price_near_resistance'] = (
            data['close'] >= data['resistance'] * (1 - threshold_pct)
        )
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy signal: Price near support + RSI oversold
        buy_condition = (
            data['price_near_support'] &
            (data['rsi'] < 30) &
            (data['rsi'].shift(1) >= 30)  # RSI crossing from above
        )
        
        # Sell signal: Price near resistance + RSI overbought
        sell_condition = (
            data['price_near_resistance'] &
            (data['rsi'] > 70) &
            (data['rsi'].shift(1) <= 70)  # RSI crossing from below
        )
        
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # Remove consecutive signals
        signals = _remove_consecutive_signals(signals)
        
        logger.info(f"Reverse trading strategy generated {signals[signals != 0].count()} signals")
        return signals
        
    except Exception as e:
        logger.error(f"Error in reverse trading strategy: {e}")
        return pd.Series(0, index=data.index)

def _remove_consecutive_signals(signals: pd.Series) -> pd.Series:
    """Remove consecutive signals of the same type"""
    result = signals.copy()
    
    for i in range(1, len(result)):
        if result.iloc[i] == result.iloc[i-1] and result.iloc[i] != 0:
            result.iloc[i] = 0
    
    return result

# Strategy parameters for optimization
REVERSE_TRADING_PARAMS = {
    'rsi_period': {'min': 9, 'max': 21, 'default': 14},
    'support_lookback': {'min': 20, 'max': 80, 'default': 50},
    'threshold_pct': {'min': 0.005, 'max': 0.02, 'default': 0.01}
}

# Risk management parameters
REVERSE_TRADING_RISK = {
    'position_size_pct': 0.02,  # 2% of capital per trade
    'stop_loss_atr_mult': 1.0,  # ATR * 1.0 stop loss
    'take_profit_atr_mult': 1.5, # ATR * 1.5 take profit
    'max_position_time': 24     # Max hours in position
}
