#!/usr/bin/env python3
"""
Momentum Trading Strategy
Following trends using MACD/ROC and volume confirmation
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def momentum_strategy(data: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Momentum trading strategy implementation
    
    Strategy Logic:
    - MACD or ROC momentum signals
    - Volume surge confirmation
    - Trend following approach
    """
    
    try:
        # Extract parameters
        roc_period = params.get('roc_period', 10)
        volume_mult = params.get('volume_mult', 1.5)
        momentum_threshold = params.get('momentum_threshold', 0.01)  # 1%
        
        # Calculate indicators
        data = data.copy()
        
        # Rate of Change (ROC)
        data['roc'] = data['close'].pct_change(roc_period)
        
        # MACD
        ema_fast = data['close'].ewm(span=12).mean()
        ema_slow = data['close'].ewm(span=26).mean()
        data['macd'] = ema_fast - ema_slow
        data['macd_signal'] = data['macd'].ewm(span=9).mean()
        data['macd_histogram'] = data['macd'] - data['macd_signal']
        
        # Volume indicators
        data['vol_ma'] = data['volume'].rolling(window=20).mean()
        # 🔥 BUG FIX: Safe division - avoid division by zero!
        data['vol_ratio'] = np.where(data['vol_ma'] > 0, data['volume'] / data['vol_ma'], 1.0)
        
        # Momentum indicators
        data['momentum'] = data['close'] / data['close'].shift(5) - 1
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy signal: Strong momentum + volume confirmation
        buy_condition = (
            (data['roc'] > momentum_threshold) &
            (data['macd'] > data['macd_signal']) &
            (data['macd_histogram'] > data['macd_histogram'].shift(1)) &
            (data['vol_ratio'] > volume_mult) &
            (data['momentum'] > 0)
        )
        
        # Sell signal: Weak momentum + volume confirmation
        sell_condition = (
            (data['roc'] < -momentum_threshold) &
            (data['macd'] < data['macd_signal']) &
            (data['macd_histogram'] < data['macd_histogram'].shift(1)) &
            (data['vol_ratio'] > volume_mult) &
            (data['momentum'] < 0)
        )
        
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # Remove consecutive signals
        signals = _remove_consecutive_signals(signals)
        
        logger.info(f"Momentum strategy generated {signals[signals != 0].count()} signals")
        return signals
        
    except Exception as e:
        logger.error(f"Error in momentum strategy: {e}")
        return pd.Series(0, index=data.index)

def _remove_consecutive_signals(signals: pd.Series) -> pd.Series:
    """Remove consecutive signals of the same type"""
    result = signals.copy()
    
    for i in range(1, len(result)):
        if result.iloc[i] == result.iloc[i-1] and result.iloc[i] != 0:
            result.iloc[i] = 0
    
    return result

# Strategy parameters for optimization
MOMENTUM_PARAMS = {
    'roc_period': {'min': 5, 'max': 30, 'default': 10},
    'volume_mult': {'min': 1.0, 'max': 2.5, 'default': 1.5},
    'momentum_threshold': {'min': 0.005, 'max': 0.03, 'default': 0.01}
}

# Risk management parameters
MOMENTUM_RISK = {
    'position_size_pct': 0.05,  # 5% of capital per trade
    'stop_loss_atr_mult': 2.0,   # ATR * 2.0 stop loss
    'take_profit_atr_mult': 3.0, # ATR * 3.0 take profit
    'trailing_stop': True        # Use trailing stop
}
