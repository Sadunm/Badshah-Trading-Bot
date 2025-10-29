#!/usr/bin/env python3
"""
Range Trading Strategy
Trading within support/resistance bands
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def range_trading_strategy(data: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Range trading strategy implementation
    
    Strategy Logic:
    - Identify support and resistance levels
    - Buy near support, sell near resistance
    - Avoid breakouts
    """
    
    try:
        # Extract parameters
        lookback = params.get('lookback', 50)
        band_tolerance_pct = params.get('band_tolerance_pct', 0.01)  # 1%
        
        # Calculate indicators
        data = data.copy()
        
        # Support and resistance levels
        data['support'] = data['low'].rolling(window=lookback).min()
        data['resistance'] = data['high'].rolling(window=lookback).max()
        data['range_size'] = data['resistance'] - data['support']
        
        # Price position within range
        data['price_position'] = (data['close'] - data['support']) / data['range_size']
        
        # Volume confirmation
        data['vol_ma'] = data['volume'].rolling(window=20).mean()
        # 🔥 BUG FIX: Safe division - avoid division by zero!
        data['vol_ratio'] = np.where(data['vol_ma'] > 0, data['volume'] / data['vol_ma'], 1.0)
        
        # Range validation (avoid trending markets)
        data['range_stability'] = data['range_size'].rolling(window=10).std()
        data['is_ranging'] = data['range_stability'] < (data['range_size'].mean() * 0.1)
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy signal: Price near support + in ranging market
        buy_condition = (
            (data['price_position'] < band_tolerance_pct) &  # Near support
            data['is_ranging'] &                            # In ranging market
            (data['vol_ratio'] > 0.8) &                    # Volume confirmation
            (data['close'] < data['close'].shift(1))        # Recent decline
        )
        
        # Sell signal: Price near resistance + in ranging market
        sell_condition = (
            (data['price_position'] > (1 - band_tolerance_pct)) &  # Near resistance
            data['is_ranging'] &                                   # In ranging market
            (data['vol_ratio'] > 0.8) &                           # Volume confirmation
            (data['close'] > data['close'].shift(1))              # Recent rise
        )
        
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # Remove consecutive signals
        signals = _remove_consecutive_signals(signals)
        
        logger.info(f"Range trading strategy generated {signals[signals != 0].count()} signals")
        return signals
        
    except Exception as e:
        logger.error(f"Error in range trading strategy: {e}")
        return pd.Series(0, index=data.index)

def _remove_consecutive_signals(signals: pd.Series) -> pd.Series:
    """Remove consecutive signals of the same type"""
    result = signals.copy()
    
    for i in range(1, len(result)):
        if result.iloc[i] == result.iloc[i-1] and result.iloc[i] != 0:
            result.iloc[i] = 0
    
    return result

# Strategy parameters for optimization
RANGE_TRADING_PARAMS = {
    'lookback': {'min': 20, 'max': 120, 'default': 50},
    'band_tolerance_pct': {'min': 0.005, 'max': 0.02, 'default': 0.01}
}

# Risk management parameters
RANGE_TRADING_RISK = {
    'position_size_pct': 0.02,  # 2% of capital per trade
    'stop_loss_pct': 0.02,      # 2% stop loss
    'take_profit_pct': 0.03,    # 3% take profit
    'max_range_trades': 5       # Max trades per range
}
