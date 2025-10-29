#!/usr/bin/env python3
"""
Buy Dips Strategy
Buying on significant price declines with market breadth check
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def buy_dips_strategy(data: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Buy dips strategy implementation
    
    Strategy Logic:
    - Significant price decline detection
    - RSI oversold confirmation
    - Scale-in purchasing approach
    """
    
    try:
        # Extract parameters
        dip_pct = params.get('dip_pct', 0.05)  # 5% dip
        lookback_window = params.get('lookback_window', 10)
        rsi_oversold = params.get('rsi_oversold', 30)
        
        # Calculate indicators
        data = data.copy()
        
        # RSI calculation
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        # Price decline detection
        data['price_high'] = data['close'].rolling(window=lookback_window).max()
        data['price_decline'] = (data['price_high'] - data['close']) / data['price_high']
        
        # Volume confirmation
        data['vol_ma'] = data['volume'].rolling(window=20).mean()
        # 🔥 BUG FIX: Safe division - avoid division by zero!
        data['vol_ratio'] = np.where(data['vol_ma'] > 0, data['volume'] / data['vol_ma'], 1.0)
        
        # Generate signals (only buy signals for dip buying)
        signals = pd.Series(0, index=data.index)
        
        # Buy signal: Significant dip + RSI oversold + volume confirmation
        buy_condition = (
            (data['price_decline'] > dip_pct) &  # Significant dip
            (data['rsi'] < rsi_oversold) &      # RSI oversold
            (data['vol_ratio'] > 1.1) &         # Volume confirmation
            (data['close'] < data['close'].shift(1))  # Recent decline
        )
        
        signals[buy_condition] = 1
        
        # Remove consecutive signals
        signals = _remove_consecutive_signals(signals)
        
        logger.info(f"Buy dips strategy generated {signals[signals != 0].count()} signals")
        return signals
        
    except Exception as e:
        logger.error(f"Error in buy dips strategy: {e}")
        return pd.Series(0, index=data.index)

def _remove_consecutive_signals(signals: pd.Series) -> pd.Series:
    """Remove consecutive signals of the same type"""
    result = signals.copy()
    
    for i in range(1, len(result)):
        if result.iloc[i] == result.iloc[i-1] and result.iloc[i] != 0:
            result.iloc[i] = 0
    
    return result

# Strategy parameters for optimization
BUY_DIPS_PARAMS = {
    'dip_pct': {'min': 0.03, 'max': 0.15, 'default': 0.05},
    'lookback_window': {'min': 5, 'max': 30, 'default': 10},
    'rsi_oversold': {'min': 20, 'max': 40, 'default': 30}
}

# Risk management parameters
BUY_DIPS_RISK = {
    'position_size_pct': 0.1,   # 10% of capital per trade
    'scale_in_levels': 3,       # 3 scale-in levels
    'scale_in_pct': 0.02,       # 2% between scale-in levels
    'stop_loss_pct': 0.1,       # 10% stop loss
    'take_profit_pct': 0.2      # 20% take profit
}
