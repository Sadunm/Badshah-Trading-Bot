#!/usr/bin/env python3
"""
Day Trading Strategy
Intraday volatility-based trading with Bollinger Bands
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def day_trading_strategy(data: pd.DataFrame, params: Dict) -> pd.Series:
    """
    Day trading strategy implementation
    
    Strategy Logic:
    - Bollinger Bands breakout entries
    - Volatility-based position sizing
    - Intraday flat by EOD
    """
    
    try:
        # Extract parameters
        bb_period = params.get('bb_period', 20)
        bb_std = params.get('bb_std', 2.0)
        
        # Calculate indicators
        data = data.copy()
        
        # Bollinger Bands
        data['bb_middle'] = data['close'].rolling(window=bb_period).mean()
        bb_std_series = data['close'].rolling(window=bb_period).std()
        data['bb_upper'] = data['bb_middle'] + (bb_std_series * bb_std)
        data['bb_lower'] = data['bb_middle'] - (bb_std_series * bb_std)
        
        # Volatility indicators
        data['volatility'] = data['close'].rolling(window=20).std()
        data['vol_ma'] = data['volume'].rolling(window=20).mean()
        data['vol_ratio'] = data['volume'] / data['vol_ma']
        
        # Price momentum
        data['price_change'] = data['close'] - data['close'].shift(1)
        data['price_change_pct'] = data['price_change'] / data['close'].shift(1)
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy signal: Price breaks above upper BB + volume confirmation
        buy_condition = (
            (data['close'] > data['bb_upper']) &
            (data['close'].shift(1) <= data['bb_upper'].shift(1)) &  # Breakout
            (data['vol_ratio'] > 1.2) &  # Volume confirmation
            (data['price_change_pct'] > 0.005)  # Positive momentum
        )
        
        # Sell signal: Price breaks below lower BB + volume confirmation
        sell_condition = (
            (data['close'] < data['bb_lower']) &
            (data['close'].shift(1) >= data['bb_lower'].shift(1)) &  # Breakdown
            (data['vol_ratio'] > 1.2) &  # Volume confirmation
            (data['price_change_pct'] < -0.005)  # Negative momentum
        )
        
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        # Remove consecutive signals
        signals = _remove_consecutive_signals(signals)
        
        logger.info(f"Day trading strategy generated {signals[signals != 0].count()} signals")
        return signals
        
    except Exception as e:
        logger.error(f"Error in day trading strategy: {e}")
        return pd.Series(0, index=data.index)

def _remove_consecutive_signals(signals: pd.Series) -> pd.Series:
    """Remove consecutive signals of the same type"""
    result = signals.copy()
    
    for i in range(1, len(result)):
        if result.iloc[i] == result.iloc[i-1] and result.iloc[i] != 0:
            result.iloc[i] = 0
    
    return result

# Strategy parameters for optimization
DAY_TRADING_PARAMS = {
    'bb_period': {'min': 20, 'max': 40, 'default': 20},
    'bb_std': {'min': 1.5, 'max': 2.5, 'default': 2.0}
}

# Risk management parameters
DAY_TRADING_RISK = {
    'position_size_pct': 0.03,  # 3% of capital per trade
    'stop_loss_atr_mult': 1.5,   # ATR * 1.5 stop loss
    'take_profit_atr_mult': 2.0, # ATR * 2.0 take profit
    'max_trades_per_day': 10,    # Limit trades per day
    'flat_by_eod': True          # Close all positions by EOD
}
