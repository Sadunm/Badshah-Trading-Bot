#!/usr/bin/env python3
"""
Fading Strategy
Trading against large moves with exhaustion confirmation
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def fading_strategy(data: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Fading strategy implementation
    
    Strategy Logic:
    - After large candles, fade the move
    - Volume exhaustion confirmation
    - Counter-trend approach
    """
    
    try:
        # Extract parameters
        candle_multiplier = params.get('candle_multiplier', 2.5)
        vol_ratio = params.get('vol_ratio', 0.7)
        
        # Calculate indicators
        data = data.copy()
        
        # ATR for volatility measurement
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift(1))
        low_close = np.abs(data['low'] - data['close'].shift(1))
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        data['atr'] = true_range.rolling(window=14).mean()
        
        # Large candle detection
        data['candle_size'] = data['high'] - data['low']
        data['large_candle'] = data['candle_size'] > (data['atr'] * candle_multiplier)
        
        # Volume analysis
        data['vol_ma'] = data['volume'].rolling(window=20).mean()
        # 🔥 BUG FIX: Safe division - avoid division by zero!
        data['vol_ratio'] = np.where(data['vol_ma'] > 0, data['volume'] / data['vol_ma'], 1.0)
        
        # Price direction
        data['price_change'] = data['close'] - data['close'].shift(1)
        data['price_change_pct'] = data['price_change'] / data['close'].shift(1)
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy signal: Large down candle + volume exhaustion
        buy_condition = (
            data['large_candle'] &
            (data['price_change_pct'] < -0.01) &  # Down move > 1%
            (data['vol_ratio'] < vol_ratio) &     # Volume exhaustion
            (data['close'] < data['open'])        # Red candle
        )
        
        # Sell signal: Large up candle + volume exhaustion
        sell_condition = (
            data['large_candle'] &
            (data['price_change_pct'] > 0.01) &   # Up move > 1%
            (data['vol_ratio'] < vol_ratio) &     # Volume exhaustion
            (data['close'] > data['open'])        # Green candle
        )
        
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # Remove consecutive signals
        signals = _remove_consecutive_signals(signals)
        
        logger.info(f"Fading strategy generated {signals[signals != 0].count()} signals")
        return signals
        
    except Exception as e:
        logger.error(f"Error in fading strategy: {e}")
        return pd.Series(0, index=data.index)

def _remove_consecutive_signals(signals: pd.Series) -> pd.Series:
    """Remove consecutive signals of the same type"""
    result = signals.copy()
    
    for i in range(1, len(result)):
        if result.iloc[i] == result.iloc[i-1] and result.iloc[i] != 0:
            result.iloc[i] = 0
    
    return result

# Strategy parameters for optimization
FADING_PARAMS = {
    'candle_multiplier': {'min': 1.5, 'max': 4.0, 'default': 2.5},
    'vol_ratio': {'min': 0.5, 'max': 0.9, 'default': 0.7}
}

# Risk management parameters
FADING_RISK = {
    'position_size_pct': 0.01,  # 1% of capital per trade (small allocation)
    'stop_loss_atr_mult': 3.0,   # Wide stop loss
    'take_profit_atr_mult': 1.5, # Quick take profit
    'max_risk_per_day': 0.05     # Max 5% risk per day
}
