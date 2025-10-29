#!/usr/bin/env python3
"""
Scalping Strategy
High-frequency trading with EMA crossovers and volume confirmation
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def scalping_strategy(data: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Scalping strategy implementation
    
    Strategy Logic:
    - EMA fast crossing EMA slow
    - Volume confirmation (volume > rolling_volume_mean * vol_mult)
    - Quick entries and exits
    """
    
    try:
        # Extract parameters
        ema_fast = params.get('ema_fast', 5)
        ema_slow = params.get('ema_slow', 13)
        vol_mult = params.get('vol_mult', 1.2)
        
        # Calculate indicators
        data = data.copy()
        data['ema_fast'] = data['close'].ewm(span=ema_fast).mean()
        data['ema_slow'] = data['close'].ewm(span=ema_slow).mean()
        data['vol_ma'] = data['volume'].rolling(window=20).mean()
        # 🔥 BUG FIX: Safe division - avoid division by zero!
        data['vol_ratio'] = np.where(data['vol_ma'] > 0, data['volume'] / data['vol_ma'], 1.0)
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy signal: EMA fast crosses above EMA slow + volume confirmation
        buy_condition = (
            (data['ema_fast'] > data['ema_slow']) &
            (data['ema_fast'].shift(1) <= data['ema_slow'].shift(1)) &
            (data['vol_ratio'] > vol_mult)
        )
        
        # Sell signal: EMA fast crosses below EMA slow + volume confirmation
        sell_condition = (
            (data['ema_fast'] < data['ema_slow']) &
            (data['ema_fast'].shift(1) >= data['ema_slow'].shift(1)) &
            (data['vol_ratio'] > vol_mult)
        )
        
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # Remove consecutive signals of same type
        signals = _remove_consecutive_signals(signals)
        
        logger.info(f"Scalping strategy generated {signals[signals != 0].count()} signals")
        return signals
        
    except Exception as e:
        logger.error(f"Error in scalping strategy: {e}")
        return pd.Series(0, index=data.index)

def _remove_consecutive_signals(signals: pd.Series) -> pd.Series:
    """Remove consecutive signals of the same type"""
    result = signals.copy()
    
    for i in range(1, len(result)):
        if result.iloc[i] == result.iloc[i-1] and result.iloc[i] != 0:
            result.iloc[i] = 0
    
    return result

# Strategy parameters for optimization
SCALPING_PARAMS = {
    'ema_fast': {'min': 3, 'max': 8, 'default': 5},
    'ema_slow': {'min': 10, 'max': 20, 'default': 13},
    'vol_mult': {'min': 1.0, 'max': 2.0, 'default': 1.2}
}

# Risk management parameters
SCALPING_RISK = {
    'position_size_pct': 0.05,  # 0.05% of capital per trade
    'stop_loss_pct': 0.1,       # 0.1% stop loss
    'take_profit_pct': 0.1,     # 0.1% take profit
    'max_trades_per_day': 50    # Limit trades per day
}
