#!/usr/bin/env python3
"""
Golden Cross / Death Cross Strategy
Long-term trend following with EMA crossovers
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def golden_death_cross_strategy(data: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Golden Cross / Death Cross strategy implementation
    
    Strategy Logic:
    - 50 EMA crosses 200 EMA (Golden Cross) → Buy
    - 50 EMA crosses below 200 EMA (Death Cross) → Sell
    - Volume confirmation required
    """
    
    try:
        # Extract parameters
        short_ema = params.get('short_ema', 50)
        long_ema = params.get('long_ema', 200)
        volume_threshold = params.get('volume_threshold', 1.2)
        
        # Calculate indicators
        data = data.copy()
        
        # EMA calculations
        data['ema_short'] = data['close'].ewm(span=short_ema).mean()
        data['ema_long'] = data['close'].ewm(span=long_ema).mean()
        
        # Volume confirmation
        data['vol_ma'] = data['volume'].rolling(window=20).mean()
        data['vol_ratio'] = data['volume'] / data['vol_ma']
        
        # EMA crossover detection
        data['ema_cross_above'] = (
            (data['ema_short'] > data['ema_long']) &
            (data['ema_short'].shift(1) <= data['ema_long'].shift(1))
        )
        data['ema_cross_below'] = (
            (data['ema_short'] < data['ema_long']) &
            (data['ema_short'].shift(1) >= data['ema_long'].shift(1))
        )
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy signal: Golden Cross + volume confirmation
        buy_condition = (
            data['ema_cross_above'] &           # Golden Cross
            (data['vol_ratio'] > volume_threshold)  # Volume confirmation
        )
        
        # Sell signal: Death Cross + volume confirmation
        sell_condition = (
            data['ema_cross_below'] &          # Death Cross
            (data['vol_ratio'] > volume_threshold)  # Volume confirmation
        )
        
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # Remove consecutive signals
        signals = _remove_consecutive_signals(signals)
        
        logger.info(f"Golden/Death Cross strategy generated {signals[signals != 0].count()} signals")
        return signals
        
    except Exception as e:
        logger.error(f"Error in Golden/Death Cross strategy: {e}")
        return pd.Series(0, index=data.index)

def _remove_consecutive_signals(signals: pd.Series) -> pd.Series:
    """Remove consecutive signals of the same type"""
    result = signals.copy()
    
    for i in range(1, len(result)):
        if result.iloc[i] == result.iloc[i-1] and result.iloc[i] != 0:
            result.iloc[i] = 0
    
    return result

# Strategy parameters for optimization
GOLDEN_DEATH_CROSS_PARAMS = {
    'short_ema': {'min': 20, 'max': 100, 'default': 50},
    'long_ema': {'min': 150, 'max': 300, 'default': 200},
    'volume_threshold': {'min': 1.0, 'max': 2.0, 'default': 1.2}
}

# Risk management parameters
GOLDEN_DEATH_CROSS_RISK = {
    'position_size_pct': 0.1,   # 10% of capital per trade
    'stop_loss_pct': 0.05,      # 5% stop loss
    'take_profit_pct': 0.2,     # 20% take profit
    'max_position_time': 365    # Max 1 year in position
}
