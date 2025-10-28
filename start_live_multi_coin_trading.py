# -*- coding: utf-8 -*-
"""
🔥 ULTIMATE HYBRID MULTI-STRATEGY TRADING BOT 🔥
Implements 8+ professional strategies with auto market detection
"""

import os
import sys
import time
import requests
import json
import logging
import numpy as np
import talib
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, jsonify, render_template_string
from collections import defaultdict

# Create logs directory first
os.makedirs('logs', exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/multi_coin_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Binance Testnet API credentials
API_KEY = 'tlA62wL7hb0H6ro0v9rhYcuSManm5gscnBWhNKHq9gamBRj3HJfm1drOECVNzHrk'
SECRET_KEY = '7Lfx9dhbMP1EfiyXl6u3VluGUXZ5g4Bde7jk83uRQVZM9fCKqPojELo4zhe8izu3'

# ============================================================================
# STRATEGY DEFINITIONS
# ============================================================================

STRATEGIES = {
    'SCALPING': {
        'timeframe': '1m',
        'hold_time': 60,  # 1-60 minutes
        'capital_pct': 0.15,  # 15% of capital
        'stop_loss': 0.008,  # 0.8%
        'take_profit': 0.012,  # 1.2%
        'max_positions': 2
    },
    'DAY_TRADING': {
        'timeframe': '5m',
        'hold_time': 480,  # 1-8 hours
        'capital_pct': 0.20,  # 20% of capital
        'stop_loss': 0.015,  # 1.5%
        'take_profit': 0.025,  # 2.5%
        'max_positions': 2
    },
    'SWING_TRADING': {
        'timeframe': '1h',
        'hold_time': 4320,  # 3-7 days
        'capital_pct': 0.25,  # 25% of capital
        'stop_loss': 0.025,  # 2.5%
        'take_profit': 0.06,  # 6%
        'max_positions': 2
    },
    'RANGE_TRADING': {
        'timeframe': '15m',
        'hold_time': 240,  # 4 hours
        'capital_pct': 0.15,  # 15% of capital
        'stop_loss': 0.012,  # 1.2%
        'take_profit': 0.02,  # 2%
        'max_positions': 2
    },
    'MOMENTUM': {
        'timeframe': '5m',
        'hold_time': 360,  # 6 hours
        'capital_pct': 0.15,  # 15% of capital
        'stop_loss': 0.02,  # 2%
        'take_profit': 0.04,  # 4%
        'max_positions': 1
    },
    'POSITION_TRADING': {
        'timeframe': '4h',
        'hold_time': 20160,  # 2-4 weeks
        'capital_pct': 0.10,  # 10% of capital
        'stop_loss': 0.04,  # 4%
        'take_profit': 0.12,  # 12%
        'max_positions': 1
    }
}

# Coin universe to scan
COIN_UNIVERSE = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 
    'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'DOTUSDT',
    'MATICUSDT', 'LTCUSDT', 'AVAXUSDT', 'LINKUSDT',
    'UNIUSDT', 'ATOMUSDT', 'ETCUSDT', 'XLMUSDT'
]

# ============================================================================
# MAIN TRADING CLASS
# ============================================================================

class UltimateHybridBot:
    def __init__(self, api_key, secret_key, initial_capital=10000):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = 'https://testnet.binance.vision'
        
        # Capital management
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.reserved_capital = 0  # Capital in open positions
        
        # Trading state
        self.positions = {}  # {symbol: {strategy, entry_price, quantity, entry_time, ...}}
        self.trades = []
        self.is_running = True
        
        # Trading costs
        self.fee_rate = 0.0005  # 0.05%
        self.slippage_rate = 0.0002  # 0.02%
        
        # Market data cache
        self.market_data = {}  # {symbol: {price, volatility, volume, ...}}
        self.support_resistance = {}  # {symbol: {support: [], resistance: []}}
        
        # Strategy performance tracking
        self.strategy_stats = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'losses': 0, 
            'profit': 0, 'win_rate': 0
        })
        
        logger.info(f"🔥 ULTIMATE HYBRID BOT INITIALIZED")
        logger.info(f"💰 Capital: ${initial_capital:.2f}")
        logger.info(f"📊 Strategies: {len(STRATEGIES)}")
        logger.info(f"🪙 Coins: {len(COIN_UNIVERSE)}")
        logger.info(f"✅ Multi-Strategy | Multi-Timeframe | Multi-Coin")
        
    # ========================================================================
    # MARKET DATA METHODS
    # ========================================================================
    
    def get_current_price(self, symbol):
        """Get current price for a symbol"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/ticker/price",
                params={'symbol': symbol},
                timeout=10
            )
            if response.status_code == 200:
                return float(response.json()['price'])
            return None
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def get_klines(self, symbol, interval='5m', limit=200):
        """Get candlestick data"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/klines",
                params={
                    'symbol': symbol,
                    'interval': interval,
                    'limit': limit
                },
                timeout=10
            )
            if response.status_code == 200:
                klines = response.json()
                closes = np.array([float(k[4]) for k in klines])
                highs = np.array([float(k[2]) for k in klines])
                lows = np.array([float(k[3]) for k in klines])
                volumes = np.array([float(k[5]) for k in klines])
                opens = np.array([float(k[1]) for k in klines])
                return closes, highs, lows, volumes, opens
            return None, None, None, None, None
        except Exception as e:
            logger.error(f"Error getting klines for {symbol}: {e}")
            return None, None, None, None, None
    
    def calculate_indicators(self, closes, highs, lows, volumes):
        """Calculate all technical indicators"""
        try:
            if len(closes) < 200:
                return None
                
            indicators = {}
            
            # RSI
            indicators['rsi'] = talib.RSI(closes, timeperiod=14)[-1]
            
            # EMAs
            indicators['ema_9'] = talib.EMA(closes, timeperiod=9)[-1]
            indicators['ema_21'] = talib.EMA(closes, timeperiod=21)[-1]
            indicators['ema_50'] = talib.EMA(closes, timeperiod=50)[-1]
            indicators['ema_200'] = talib.EMA(closes, timeperiod=200)[-1]
            
            # MACDs
            macd, signal, hist = talib.MACD(closes)
            indicators['macd'] = macd[-1]
            indicators['macd_signal'] = signal[-1]
            indicators['macd_hist'] = hist[-1]
            
            # Bollinger Bands
            upper, middle, lower = talib.BBANDS(closes)
            indicators['bb_upper'] = upper[-1]
            indicators['bb_middle'] = middle[-1]
            indicators['bb_lower'] = lower[-1]
            
            # ATR (volatility)
            atr = talib.ATR(highs, lows, closes, timeperiod=14)
            indicators['atr'] = atr[-1]
            indicators['atr_pct'] = (atr[-1] / closes[-1]) * 100
            
            # Volume
            indicators['volume_avg'] = np.mean(volumes[-20:])
            indicators['volume_current'] = volumes[-1]
            indicators['volume_ratio'] = volumes[-1] / np.mean(volumes[-20:])
            
            # Momentum
            indicators['momentum_3'] = (closes[-1] - closes[-3]) / closes[-3] * 100
            indicators['momentum_10'] = (closes[-1] - closes[-10]) / closes[-10] * 100
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return None
    
    def detect_support_resistance(self, highs, lows, closes, window=20):
        """Detect support and resistance levels"""
        try:
            levels = []
            
            # Find local maxima (resistance) and minima (support)
            for i in range(window, len(closes) - window):
                # Check if it's a peak (resistance)
                if highs[i] == max(highs[i-window:i+window]):
                    levels.append(('resistance', highs[i]))
                
                # Check if it's a trough (support)
                if lows[i] == min(lows[i-window:i+window]):
                    levels.append(('support', lows[i]))
            
            # Cluster nearby levels
            support = []
            resistance = []
            
            for level_type, price in levels:
                if level_type == 'support':
                    if not support or abs(price - support[-1]) / support[-1] > 0.01:
                        support.append(price)
                else:
                    if not resistance or abs(price - resistance[-1]) / resistance[-1] > 0.01:
                        resistance.append(price)
            
            return {
                'support': sorted(support)[-3:],  # Last 3 support levels
                'resistance': sorted(resistance)[-3:]  # Last 3 resistance levels
            }
            
        except Exception as e:
            logger.error(f"Error detecting S/R: {e}")
            return {'support': [], 'resistance': []}
    
    def detect_golden_death_cross(self, ema_50, ema_200, prev_ema_50, prev_ema_200):
        """Detect Golden Cross and Death Cross"""
        # Golden Cross: 50 EMA crosses above 200 EMA
        if prev_ema_50 <= prev_ema_200 and ema_50 > ema_200:
            return 'GOLDEN_CROSS'
        
        # Death Cross: 50 EMA crosses below 200 EMA
        if prev_ema_50 >= prev_ema_200 and ema_50 < ema_200:
            return 'DEATH_CROSS'
        
        return None
    
    def scan_market(self):
        """Scan all coins and rank by opportunity"""
        logger.info(f"\n{'='*70}")
        logger.info(f"🔍 SCANNING {len(COIN_UNIVERSE)} COINS...")
        logger.info(f"{'='*70}")
        
        opportunities = []
        
        for symbol in COIN_UNIVERSE:
            try:
                # Get data
                closes, highs, lows, volumes, opens = self.get_klines(symbol, '5m', 200)
                if closes is None:
                    continue
                
                # Calculate indicators
                indicators = self.calculate_indicators(closes, highs, lows, volumes)
                if indicators is None:
                    continue
                
                # Detect S/R levels
                sr_levels = self.detect_support_resistance(highs, lows, closes)
                
                # Calculate opportunity score
                score = self.calculate_opportunity_score(closes[-1], indicators, sr_levels)
                
                # Store market data
                self.market_data[symbol] = {
                    'price': closes[-1],
                    'indicators': indicators,
                    'sr_levels': sr_levels,
                    'score': score
                }
                
                opportunities.append((symbol, score, indicators))
                
                logger.info(f"✓ {symbol}: Score={score:.2f}, RSI={indicators['rsi']:.1f}, Vol={indicators['atr_pct']:.2f}%")
                
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by score
        opportunities.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"\n🏆 TOP 5 OPPORTUNITIES:")
        for i, (symbol, score, ind) in enumerate(opportunities[:5], 1):
            logger.info(f"{i}. {symbol} - Score: {score:.2f}")
        
        return opportunities
    
    def calculate_opportunity_score(self, price, indicators, sr_levels):
        """Calculate opportunity score for a coin"""
        score = 50  # Base score
        
        try:
            # Volatility bonus (higher volatility = more opportunities)
            if indicators['atr_pct'] > 2.0:
                score += 20
            elif indicators['atr_pct'] > 1.0:
                score += 10
            
            # Volume bonus
            if indicators['volume_ratio'] > 1.5:
                score += 15
            elif indicators['volume_ratio'] > 1.2:
                score += 10
            
            # Trend strength
            if indicators['ema_9'] > indicators['ema_21'] > indicators['ema_50']:
                score += 15  # Strong uptrend
            elif indicators['ema_9'] < indicators['ema_21'] < indicators['ema_50']:
                score += 10  # Downtrend (can short/fade)
            
            # RSI opportunities
            if indicators['rsi'] < 30:
                score += 15  # Oversold
            elif indicators['rsi'] > 70:
                score += 15  # Overbought
            elif 40 <= indicators['rsi'] <= 60:
                score += 5  # Neutral (ranging)
            
            # MACD
            if indicators['macd'] > indicators['macd_signal']:
                score += 10  # Bullish
            
            # Support/Resistance proximity
            support = sr_levels.get('support', [])
            resistance = sr_levels.get('resistance', [])
            
            if support:
                dist_to_support = min([abs(price - s) / price for s in support])
                if dist_to_support < 0.01:  # Within 1% of support
                    score += 10
            
            if resistance:
                dist_to_resistance = min([abs(price - r) / price for r in resistance])
                if dist_to_resistance < 0.01:  # Within 1% of resistance
                    score += 10
            
            return min(score, 100)  # Cap at 100
            
        except Exception as e:
            logger.error(f"Error calculating score: {e}")
            return 50
    
    # ========================================================================
    # STRATEGY SIGNAL GENERATORS
    # ========================================================================
    
    def generate_scalping_signal(self, symbol, data):
        """SCALPING: Quick 1-60min trades on volatility"""
        ind = data['indicators']
        price = data['price']
        
        # High volatility required
        if ind['atr_pct'] < 1.5:
            return None
        
        # Quick momentum signals
        if ind['rsi'] < 45 and ind['momentum_3'] < -0.5:
            return {'action': 'BUY', 'reason': 'Scalping Dip', 'confidence': 0.7}
        
        if ind['rsi'] > 55 and ind['momentum_3'] > 0.5:
            return {'action': 'SELL', 'reason': 'Scalping Pump', 'confidence': 0.7}
        
        return None
    
    def generate_day_trading_signal(self, symbol, data):
        """DAY TRADING: 1-8 hour holds on volatility"""
        ind = data['indicators']
        
        # Moderate volatility
        if ind['atr_pct'] < 1.0:
            return None
        
        # Trend + RSI
        if ind['ema_9'] > ind['ema_21'] and ind['rsi'] < 50:
            return {'action': 'BUY', 'reason': 'Day Trade Uptrend Dip', 'confidence': 0.75}
        
        if ind['ema_9'] < ind['ema_21'] and ind['rsi'] > 50:
            return {'action': 'SELL', 'reason': 'Day Trade Downtrend Rally', 'confidence': 0.75}
        
        return None
    
    def generate_swing_trading_signal(self, symbol, data):
        """SWING TRADING: 3-7 day holds on trends"""
        ind = data['indicators']
        sr = data['sr_levels']
        price = data['price']
        
        # Strong trend required
        uptrend = ind['ema_9'] > ind['ema_21'] > ind['ema_50']
        downtrend = ind['ema_9'] < ind['ema_21'] < ind['ema_50']
        
        # Buy dips in uptrend
        if uptrend and ind['rsi'] < 45:
            return {'action': 'BUY', 'reason': 'Swing Buy Uptrend Dip', 'confidence': 0.85}
        
        # Near support in uptrend
        if uptrend and sr['support']:
            if min([abs(price - s) / price for s in sr['support']]) < 0.015:
                return {'action': 'BUY', 'reason': 'Swing Buy Support', 'confidence': 0.8}
        
        # Sell rallies in downtrend
        if downtrend and ind['rsi'] > 55:
            return {'action': 'SELL', 'reason': 'Swing Sell Downtrend Rally', 'confidence': 0.8}
        
        return None
    
    def generate_range_trading_signal(self, symbol, data):
        """RANGE TRADING: Buy support, sell resistance"""
        ind = data['indicators']
        sr = data['sr_levels']
        price = data['price']
        
        # Ranging market (low trend strength)
        if abs(ind['ema_9'] - ind['ema_21']) / ind['ema_21'] > 0.02:
            return None  # Too trendy
        
        # Near support
        if sr['support']:
            dist_to_support = min([abs(price - s) / price for s in sr['support']])
            if dist_to_support < 0.01 and ind['rsi'] < 45:
                return {'action': 'BUY', 'reason': 'Range Bottom', 'confidence': 0.75}
        
        # Near resistance
        if sr['resistance']:
            dist_to_resistance = min([abs(price - r) / price for r in sr['resistance']])
            if dist_to_resistance < 0.01 and ind['rsi'] > 55:
                return {'action': 'SELL', 'reason': 'Range Top', 'confidence': 0.75}
        
        return None
    
    def generate_momentum_signal(self, symbol, data):
        """MOMENTUM: Ride strong trends"""
        ind = data['indicators']
        
        # Strong momentum required
        if abs(ind['momentum_10']) < 3.0:
            return None
        
        # Bullish momentum
        if ind['momentum_10'] > 3.0 and ind['macd'] > ind['macd_signal'] and ind['rsi'] < 65:
            return {'action': 'BUY', 'reason': 'Strong Momentum Up', 'confidence': 0.8}
        
        # Bearish momentum
        if ind['momentum_10'] < -3.0 and ind['macd'] < ind['macd_signal'] and ind['rsi'] > 35:
            return {'action': 'SELL', 'reason': 'Strong Momentum Down', 'confidence': 0.8}
        
        return None
    
    def generate_position_trading_signal(self, symbol, data):
        """POSITION TRADING: Long-term holds on major trends"""
        ind = data['indicators']
        
        # Golden Cross (very bullish)
        if ind['ema_50'] > ind['ema_200'] and ind['rsi'] < 55:
            return {'action': 'BUY', 'reason': 'Golden Cross Zone', 'confidence': 0.9}
        
        # Death Cross (very bearish)
        if ind['ema_50'] < ind['ema_200'] and ind['rsi'] > 45:
            return {'action': 'SELL', 'reason': 'Death Cross Zone', 'confidence': 0.85}
        
        return None
    
    # ========================================================================
    # POSITION MANAGEMENT
    # ========================================================================
    
    def calculate_position_size(self, symbol, strategy_name, price):
        """Calculate position size for a strategy"""
        try:
            strategy = STRATEGIES[strategy_name]
            
            # Available capital for this strategy
            available_capital = self.current_capital - self.reserved_capital
            strategy_capital = self.initial_capital * strategy['capital_pct']
            
            # Use smaller of the two
            capital_to_use = min(available_capital, strategy_capital)
            
            # Position value
            position_value = capital_to_use / strategy['max_positions']
            
            # Add fees
            total_cost = position_value * (1 + self.fee_rate + self.slippage_rate)
            
            if total_cost > available_capital:
                return 0
            
            # Calculate quantity
            quantity = position_value / price
            
            # Round based on price
            if price > 1000:
                quantity = round(quantity, 4)
            elif price > 100:
                quantity = round(quantity, 3)
            elif price > 1:
                quantity = round(quantity, 2)
            else:
                quantity = round(quantity, 1)
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0
    
    def open_position(self, symbol, strategy_name, action, price, reason, confidence):
        """Open a new position"""
        try:
            # Check if already have position
            position_key = f"{symbol}_{strategy_name}"
            if position_key in self.positions:
                return False
            
            # Check max positions for strategy
            strategy_positions = [p for p in self.positions.values() if p['strategy'] == strategy_name]
            if len(strategy_positions) >= STRATEGIES[strategy_name]['max_positions']:
                return False
            
            # Calculate position size
            quantity = self.calculate_position_size(symbol, strategy_name, price)
            if quantity <= 0:
                return False
            
            # Execute order
            strategy = STRATEGIES[strategy_name]
            exec_price = price * (1 + self.slippage_rate) if action == 'BUY' else price * (1 - self.slippage_rate)
            position_value = quantity * exec_price
            fee = position_value * self.fee_rate
            total_cost = position_value + fee
            
            # Deduct from capital
            self.current_capital -= total_cost
            self.reserved_capital += position_value
            
            # Create position
            self.positions[position_key] = {
                'symbol': symbol,
                'strategy': strategy_name,
                'action': action,
                'quantity': quantity,
                'entry_price': exec_price,
                'entry_time': datetime.now(),
                'stop_loss': exec_price * (1 - strategy['stop_loss']) if action == 'BUY' else exec_price * (1 + strategy['stop_loss']),
                'take_profit': exec_price * (1 + strategy['take_profit']) if action == 'BUY' else exec_price * (1 - strategy['take_profit']),
                'reason': reason,
                'confidence': confidence
            }
            
            # Log trade
            trade = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'strategy': strategy_name,
                'action': action,
                'quantity': quantity,
                'price': exec_price,
                'fee': fee,
                'reason': reason
            }
            self.trades.append(trade)
            
            logger.info(f"✅ OPENED {action} | {symbol} | {strategy_name} | {quantity:.4f} @ ${exec_price:.2f} | {reason}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return False
    
    def close_position(self, position_key, current_price, reason):
        """Close an existing position"""
        try:
            position = self.positions[position_key]
            symbol = position['symbol']
            strategy_name = position['strategy']
            
            # Execute close
            exec_price = current_price * (1 - self.slippage_rate) if position['action'] == 'BUY' else current_price * (1 + self.slippage_rate)
            position_value = position['quantity'] * exec_price
            fee = position_value * self.fee_rate
            proceeds = position_value - fee
            
            # Calculate P&L
            if position['action'] == 'BUY':
                pnl = proceeds - (position['quantity'] * position['entry_price'])
            else:
                pnl = (position['quantity'] * position['entry_price']) - proceeds
            
            pnl_pct = (pnl / (position['quantity'] * position['entry_price'])) * 100
            
            # Update capital
            self.current_capital += proceeds
            self.reserved_capital -= (position['quantity'] * position['entry_price'])
            
            # Update strategy stats
            self.strategy_stats[strategy_name]['trades'] += 1
            self.strategy_stats[strategy_name]['profit'] += pnl
            if pnl > 0:
                self.strategy_stats[strategy_name]['wins'] += 1
            else:
                self.strategy_stats[strategy_name]['losses'] += 1
            
            wins = self.strategy_stats[strategy_name]['wins']
            total = self.strategy_stats[strategy_name]['trades']
            self.strategy_stats[strategy_name]['win_rate'] = (wins / total * 100) if total > 0 else 0
            
            # Log close
            trade = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'strategy': strategy_name,
                'action': 'CLOSE',
                'quantity': position['quantity'],
                'price': exec_price,
                'fee': fee,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'reason': reason
            }
            self.trades.append(trade)
            
            hold_time = (datetime.now() - position['entry_time']).total_seconds() / 60
            
            emoji = "🎉" if pnl > 0 else "❌"
            logger.info(f"{emoji} CLOSED | {symbol} | {strategy_name} | PnL: ${pnl:.2f} ({pnl_pct:+.2f}%) | Hold: {hold_time:.0f}min | {reason}")
            
            # Remove position
            del self.positions[position_key]
            
            return True
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
    
    def manage_positions(self):
        """Check and manage all open positions"""
        positions_to_close = []
        
        for position_key, position in self.positions.items():
            try:
                symbol = position['symbol']
                strategy_name = position['strategy']
                strategy = STRATEGIES[strategy_name]
                
                # Get current price
                current_price = self.get_current_price(symbol)
                if current_price is None:
                    continue
                
                # Check stop loss
                if position['action'] == 'BUY':
                    if current_price <= position['stop_loss']:
                        positions_to_close.append((position_key, current_price, 'Stop Loss'))
                        continue
                    if current_price >= position['take_profit']:
                        positions_to_close.append((position_key, current_price, 'Take Profit'))
                        continue
                else:
                    if current_price >= position['stop_loss']:
                        positions_to_close.append((position_key, current_price, 'Stop Loss'))
                        continue
                    if current_price <= position['take_profit']:
                        positions_to_close.append((position_key, current_price, 'Take Profit'))
                        continue
                
                # Check time-based exit
                hold_time = (datetime.now() - position['entry_time']).total_seconds() / 60
                if hold_time > strategy['hold_time'] * 1.5:  # 1.5x max hold time
                    positions_to_close.append((position_key, current_price, 'Time Limit'))
                
            except Exception as e:
                logger.error(f"Error managing position {position_key}: {e}")
        
        # Close positions
        for position_key, price, reason in positions_to_close:
            self.close_position(position_key, price, reason)
    
    # ========================================================================
    # MAIN TRADING LOOP
    # ========================================================================
    
    def run_trading_cycle(self):
        """Main trading logic"""
        try:
            # Step 1: Manage existing positions
            self.manage_positions()
            
            # Step 2: Scan market for opportunities
            opportunities = self.scan_market()
            
            # Step 3: Generate signals for each strategy
            logger.info(f"\n{'='*70}")
            logger.info(f"🎯 GENERATING SIGNALS...")
            logger.info(f"{'='*70}")
            
            for symbol, score, _ in opportunities[:8]:  # Top 8 coins
                if symbol not in self.market_data:
                    continue
                
                data = self.market_data[symbol]
                
                # Try each strategy
                strategies_to_try = [
                    ('SCALPING', self.generate_scalping_signal),
                    ('DAY_TRADING', self.generate_day_trading_signal),
                    ('SWING_TRADING', self.generate_swing_trading_signal),
                    ('RANGE_TRADING', self.generate_range_trading_signal),
                    ('MOMENTUM', self.generate_momentum_signal),
                    ('POSITION_TRADING', self.generate_position_trading_signal)
                ]
                
                for strategy_name, signal_func in strategies_to_try:
                    signal = signal_func(symbol, data)
                    
                    if signal:
                        # Try to open position
                        success = self.open_position(
                            symbol, 
                            strategy_name, 
                            signal['action'], 
                            data['price'],
                            signal['reason'],
                            signal['confidence']
                        )
                        
                        if success:
                            break  # Only one strategy per coin per cycle
            
            # Step 4: Print status
            self.print_status()
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
    
    def print_status(self):
        """Print current status"""
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 STATUS REPORT")
        logger.info(f"{'='*70}")
        logger.info(f"💰 Capital: ${self.current_capital:.2f} | Reserved: ${self.reserved_capital:.2f}")
        logger.info(f"📈 P&L: ${self.current_capital + self.reserved_capital - self.initial_capital:.2f}")
        logger.info(f"📊 Open Positions: {len(self.positions)}")
        logger.info(f"📝 Total Trades: {len(self.trades)}")
        
        if self.positions:
            logger.info(f"\n🎯 OPEN POSITIONS:")
            for key, pos in self.positions.items():
                current_price = self.get_current_price(pos['symbol'])
                if current_price:
                    if pos['action'] == 'BUY':
                        pnl_pct = (current_price - pos['entry_price']) / pos['entry_price'] * 100
                    else:
                        pnl_pct = (pos['entry_price'] - current_price) / pos['entry_price'] * 100
                    
                    hold_time = (datetime.now() - pos['entry_time']).total_seconds() / 60
                    logger.info(f"  {pos['symbol']} | {pos['strategy']} | {pos['action']} | PnL: {pnl_pct:+.2f}% | Hold: {hold_time:.0f}min")
        
        if self.strategy_stats:
            logger.info(f"\n📊 STRATEGY PERFORMANCE:")
            for strategy, stats in self.strategy_stats.items():
                if stats['trades'] > 0:
                    logger.info(f"  {strategy}: {stats['trades']} trades | Win Rate: {stats['win_rate']:.1f}% | Profit: ${stats['profit']:.2f}")
    
    def start_trading(self):
        """Start the trading bot"""
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 ULTIMATE HYBRID BOT STARTING...")
        logger.info(f"{'='*70}\n")
        
        cycle = 0
        
        while self.is_running:
            try:
                cycle += 1
                logger.info(f"\n{'#'*70}")
                logger.info(f"🔄 CYCLE #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'#'*70}")
                
                self.run_trading_cycle()
                
                # Wait 2 minutes
                logger.info(f"\n⏳ Waiting 2 minutes until next cycle...\n")
                time.sleep(120)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Stopping bot...")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)

# ============================================================================
# FLASK WEB SERVER (Dashboard)
# ============================================================================

app = Flask(__name__)
trading_bot = None
trading_stats = {
    'start_time': datetime.now(),
    'total_trades': 0,
    'win_rate': 0,
    'total_pnl': 0,
    'current_capital': 10000
}

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/stats')
def get_stats():
    """Get trading statistics"""
    global trading_bot, trading_stats
    
    if trading_bot:
        wins = sum(1 for t in trading_bot.trades if t.get('pnl', 0) > 0)
        total = len([t for t in trading_bot.trades if 'pnl' in t])
        
        trading_stats = {
            'start_time': trading_stats['start_time'].isoformat(),
            'total_trades': len(trading_bot.trades),
            'closed_trades': total,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'total_pnl': trading_bot.current_capital + trading_bot.reserved_capital - trading_bot.initial_capital,
            'current_capital': trading_bot.current_capital,
            'reserved_capital': trading_bot.reserved_capital,
            'open_positions': len(trading_bot.positions),
            'strategy_stats': dict(trading_bot.strategy_stats)
        }
    
    return jsonify(trading_stats)

@app.route('/dashboard')
def dashboard():
    """Dashboard HTML page"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ultimate Hybrid Trading Bot</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #fff;
                padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { 
                text-align: center; 
                font-size: 2.5em; 
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .subtitle {
                text-align: center;
                font-size: 1.2em;
                margin-bottom: 30px;
                opacity: 0.9;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 25px;
                border: 1px solid rgba(255,255,255,0.2);
                transition: transform 0.3s;
            }
            .stat-card:hover { transform: translateY(-5px); }
            .stat-label {
                font-size: 0.9em;
                opacity: 0.8;
                margin-bottom: 10px;
            }
            .stat-value {
                font-size: 2em;
                font-weight: bold;
            }
            .positive { color: #4ade80; }
            .negative { color: #f87171; }
            .strategy-stats {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 25px;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .strategy-item {
                display: flex;
                justify-content: space-between;
                padding: 15px;
                margin: 10px 0;
                background: rgba(255,255,255,0.05);
                border-radius: 10px;
            }
            .last-update {
                text-align: center;
                margin-top: 20px;
                opacity: 0.7;
                font-size: 0.9em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 Ultimate Hybrid Trading Bot</h1>
            <div class="subtitle">Multi-Strategy | Multi-Timeframe | Multi-Coin</div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Trades</div>
                    <div class="stat-value" id="total-trades">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Win Rate</div>
                    <div class="stat-value" id="win-rate">0%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total P&L</div>
                    <div class="stat-value" id="total-pnl">$0.00</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Open Positions</div>
                    <div class="stat-value" id="open-positions">0</div>
                </div>
            </div>
            
            <div class="strategy-stats">
                <h2 style="margin-bottom: 20px;">📊 Strategy Performance</h2>
                <div id="strategy-list"></div>
            </div>
            
            <div class="last-update">Last updated: <span id="last-update">-</span></div>
        </div>
        
        <script>
            function updateStats() {
                fetch('/api/stats')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('total-trades').textContent = data.total_trades;
                        document.getElementById('win-rate').textContent = data.win_rate.toFixed(1) + '%';
                        
                        const pnl = data.total_pnl;
                        const pnlEl = document.getElementById('total-pnl');
                        pnlEl.textContent = '$' + pnl.toFixed(2);
                        pnlEl.className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');
                        
                        document.getElementById('open-positions').textContent = data.open_positions;
                        
                        // Strategy stats
                        const strategyList = document.getElementById('strategy-list');
                        strategyList.innerHTML = '';
                        
                        for (const [name, stats] of Object.entries(data.strategy_stats || {})) {
                            if (stats.trades > 0) {
                                const div = document.createElement('div');
                                div.className = 'strategy-item';
                                div.innerHTML = `
                                    <div>
                                        <strong>${name}</strong><br>
                                        <small>${stats.trades} trades | Win Rate: ${stats.win_rate.toFixed(1)}%</small>
                                    </div>
                                    <div class="${stats.profit >= 0 ? 'positive' : 'negative'}">
                                        $${stats.profit.toFixed(2)}
                                    </div>
                                `;
                                strategyList.appendChild(div);
                            }
                        }
                        
                        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                    })
                    .catch(err => console.error('Error:', err));
            }
            
            updateStats();
            setInterval(updateStats, 5000);
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

def run_flask():
    """Run Flask server"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    try:
        # Test API connection
        logger.info("Testing Binance API connection...")
        test_url = 'https://testnet.binance.vision/api/v3/ping'
        response = requests.get(test_url, timeout=10)
        if response.status_code == 200:
            logger.info("✅ API connection successful!")
        else:
            logger.warning("⚠️ API connection issue, but continuing...")
        
        # Create bot instance
        trading_bot = UltimateHybridBot(API_KEY, SECRET_KEY, initial_capital=10000)
        
        # Start Flask server in background
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("✅ Flask server started")
        
        # Start trading
        trading_bot.start_trading()
        
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
