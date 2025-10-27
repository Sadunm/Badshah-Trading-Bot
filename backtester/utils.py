#!/usr/bin/env python3
"""
Backtester Utilities
Realistic fee calculation, quantity rounding, and exchange rules
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class ExchangeUtils:
    """Exchange utilities for realistic trading simulation"""
    
    def __init__(self, 
                 maker_fee: float = 0.0005,
                 taker_fee: float = 0.001,
                 slippage_pct: float = 0.0005,
                 min_notional: float = 10.0,
                 step_size: float = 0.00001,
                 tick_size: float = 0.01):
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage_pct = slippage_pct
        self.min_notional = min_notional
        self.step_size = step_size
        self.tick_size = tick_size
    
    def get_quantity_for_notional(self, 
                                 capital: float, 
                                 risk_pct: float, 
                                 price: float, 
                                 step_size: Optional[float] = None,
                                 min_notional: Optional[float] = None) -> Tuple[float, bool]:
        """
        Calculate quantity for given notional with exchange rules
        
        Returns:
            Tuple[quantity, is_valid]
        """
        try:
            step_size = step_size or self.step_size
            min_notional = min_notional or self.min_notional
            
            # Calculate raw quantity
            raw_qty = (capital * risk_pct) / price
            
            # Round down to step size
            quantity = np.floor(raw_qty / step_size) * step_size
            
            # Check minimum notional
            if quantity * price < min_notional:
                logger.warning(f"Quantity {quantity} * price {price} = {quantity * price} < min_notional {min_notional}")
                return 0.0, False
            
            return quantity, True
            
        except Exception as e:
            logger.error(f"Error calculating quantity: {e}")
            return 0.0, False
    
    def calculate_fees(self, 
                      quantity: float, 
                      price: float, 
                      is_maker: bool = False) -> float:
        """Calculate trading fees"""
        notional = quantity * price
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        return notional * fee_rate
    
    def calculate_slippage(self, 
                          quantity: float, 
                          price: float, 
                          avg_daily_volume: float = 1000000) -> float:
        """
        Calculate realistic slippage based on order size and market impact
        slippage = base_slippage + market_impact
        """
        notional = quantity * price
        
        # Base slippage
        base_slippage = self.slippage_pct
        
        # Market impact (larger orders = more slippage)
        market_impact = 0.5 * (notional / avg_daily_volume)
        
        total_slippage = base_slippage + market_impact
        
        return min(total_slippage, 0.01)  # Cap at 1%
    
    def apply_slippage(self, 
                      price: float, 
                      quantity: float, 
                      side: str,
                      avg_daily_volume: float = 1000000) -> float:
        """Apply slippage to price based on order side and size"""
        slippage_pct = self.calculate_slippage(quantity, price, avg_daily_volume)
        
        if side.upper() == 'BUY':
            return price * (1 + slippage_pct)
        else:  # SELL
            return price * (1 - slippage_pct)
    
    def calculate_trade_pnl(self, 
                           entry_price: float,
                           exit_price: float,
                           quantity: float,
                           side: str,
                           is_maker_entry: bool = False,
                           is_maker_exit: bool = False) -> Dict:
        """Calculate complete trade PnL with fees and slippage"""
        
        # Apply slippage
        effective_entry = self.apply_slippage(entry_price, quantity, side)
        effective_exit = self.apply_slippage(exit_price, quantity, 'SELL' if side == 'BUY' else 'BUY')
        
        # Calculate gross PnL
        if side.upper() == 'BUY':
            gross_pnl = (effective_exit - effective_entry) * quantity
        else:  # SELL
            gross_pnl = (effective_entry - effective_exit) * quantity
        
        # Calculate fees
        entry_fee = self.calculate_fees(quantity, effective_entry, is_maker_entry)
        exit_fee = self.calculate_fees(quantity, effective_exit, is_maker_exit)
        total_fees = entry_fee + exit_fee
        
        # Net PnL
        net_pnl = gross_pnl - total_fees
        net_pnl_pct = net_pnl / (effective_entry * quantity)
        
        return {
            'gross_pnl': gross_pnl,
            'total_fees': total_fees,
            'net_pnl': net_pnl,
            'net_pnl_pct': net_pnl_pct,
            'effective_entry': effective_entry,
            'effective_exit': effective_exit,
            'entry_fee': entry_fee,
            'exit_fee': exit_fee
        }

def calculate_atr(high: pd.Series, 
                 low: pd.Series, 
                 close: pd.Series, 
                 period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    
    return atr

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return prices.ewm(span=period).mean()

def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    return prices.rolling(window=period).mean()

def calculate_bollinger_bands(prices: pd.Series, 
                             period: int = 20, 
                             std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands"""
    sma = calculate_sma(prices, period)
    std = prices.rolling(window=period).std()
    
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return upper, sma, lower

def calculate_macd(prices: pd.Series, 
                   fast: int = 12, 
                   slow: int = 26, 
                   signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD indicator"""
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    
    macd = ema_fast - ema_slow
    signal_line = calculate_ema(macd, signal)
    histogram = macd - signal_line
    
    return macd, signal_line, histogram

def calculate_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate volume ratio vs moving average"""
    vol_ma = volume.rolling(window=period).mean()
    return volume / vol_ma

def validate_trade_signals(signals: pd.Series) -> bool:
    """Validate trade signals for basic sanity"""
    if signals.empty:
        return False
    
    # Check for valid signal values (0, 1, -1)
    valid_signals = signals.isin([0, 1, -1])
    if not valid_signals.all():
        logger.warning("Invalid signal values detected")
        return False
    
    # Check for reasonable signal frequency (not too many signals)
    signal_count = (signals != 0).sum()
    total_periods = len(signals)
    signal_ratio = signal_count / total_periods
    
    if signal_ratio > 0.5:  # More than 50% signals
        logger.warning(f"Too many signals: {signal_ratio:.2%}")
        return False
    
    return True

def round_to_tick_size(price: float, tick_size: float) -> float:
    """Round price to exchange tick size"""
    return round(price / tick_size) * tick_size

def round_to_step_size(quantity: float, step_size: float) -> float:
    """Round quantity to exchange step size"""
    return round(quantity / step_size) * step_size
