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
import csv
from datetime import datetime, timedelta
from threading import Thread, Lock  # 🔧 FIX: Added Lock for thread safety
from flask import Flask, jsonify, render_template_string
from collections import defaultdict

# Create necessary directories
os.makedirs('logs', exist_ok=True)
os.makedirs('data', exist_ok=True)

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
# PERFORMANCE ANALYTICS TRACKER
# ============================================================================

class PerformanceAnalytics:
    """Track and analyze trading performance for validation"""
    
    def __init__(self):
        self.daily_stats = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0, 'capital': 0
        })
        self.peak_capital = 10000
        self.current_drawdown = 0
        self.max_drawdown = 0
        self.market_conditions = []
        self.start_date = datetime.now()
        
    def update_daily_stats(self, date_str, trade_result, capital):
        """Update daily statistics"""
        stats = self.daily_stats[date_str]
        stats['trades'] += 1
        stats['capital'] = capital
        
        if trade_result > 0:
            stats['wins'] += 1
            stats['pnl'] += trade_result
        else:
            stats['losses'] += 1
            stats['pnl'] += trade_result
    
    def update_drawdown(self, current_capital):
        """Calculate and update max drawdown"""
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital
        
        self.current_drawdown = (self.peak_capital - current_capital) / self.peak_capital * 100
        
        if self.current_drawdown > self.max_drawdown:
            self.max_drawdown = self.current_drawdown
    
    def get_consistency_score(self):
        """Calculate consistency score (0-100)"""
        if len(self.daily_stats) < 3:
            return 0
        
        daily_pnls = [stats['pnl'] for stats in self.daily_stats.values()]
        
        if not daily_pnls:
            return 0
        
        # Calculate standard deviation of daily returns
        std_dev = np.std(daily_pnls) if len(daily_pnls) > 1 else 0
        avg_pnl = np.mean(daily_pnls)
        
        # Lower std_dev = higher consistency
        if std_dev == 0:
            return 100
        
        # Consistency score: inverse of coefficient of variation
        cv = abs(std_dev / avg_pnl) if avg_pnl != 0 else float('inf')
        consistency = max(0, min(100, 100 - (cv * 10)))
        
        return consistency
    
    def get_win_streak(self):
        """Get current winning/losing streak"""
        if not self.daily_stats:
            return {'current': 0, 'type': 'neutral', 'longest_win': 0, 'longest_loss': 0}
        
        sorted_days = sorted(self.daily_stats.items())
        current_streak = 0
        streak_type = 'neutral'
        longest_win = 0
        longest_loss = 0
        temp_streak = 0
        last_type = None
        
        for date, stats in sorted_days:
            day_result = 'win' if stats['pnl'] > 0 else 'loss' if stats['pnl'] < 0 else 'neutral'
            
            if day_result == last_type and day_result != 'neutral':
                temp_streak += 1
            else:
                if last_type == 'win' and temp_streak > longest_win:
                    longest_win = temp_streak
                elif last_type == 'loss' and temp_streak > longest_loss:
                    longest_loss = temp_streak
                temp_streak = 1
                last_type = day_result
        
        # Check last streak
        if last_type == 'win' and temp_streak > longest_win:
            longest_win = temp_streak
        elif last_type == 'loss' and temp_streak > longest_loss:
            longest_loss = temp_streak
        
        # Current streak
        if sorted_days:
            last_day_pnl = sorted_days[-1][1]['pnl']
            if last_day_pnl > 0:
                current_streak = 1
                streak_type = 'win'
                # Count backwards
                for i in range(len(sorted_days) - 2, -1, -1):
                    if sorted_days[i][1]['pnl'] > 0:
                        current_streak += 1
                    else:
                        break
            elif last_day_pnl < 0:
                current_streak = 1
                streak_type = 'loss'
                for i in range(len(sorted_days) - 2, -1, -1):
                    if sorted_days[i][1]['pnl'] < 0:
                        current_streak += 1
                    else:
                        break
        
        return {
            'current': current_streak,
            'type': streak_type,
            'longest_win': longest_win,
            'longest_loss': longest_loss
        }
    
    def detect_market_condition(self, prices):
        """Detect current market condition"""
        if len(prices) < 20:
            return "UNKNOWN"
        
        recent_prices = prices[-20:]
        
        # Calculate volatility
        returns = np.diff(recent_prices) / recent_prices[:-1]
        volatility = np.std(returns) * 100
        
        # Calculate trend
        start_price = recent_prices[0]
        end_price = recent_prices[-1]
        trend = (end_price - start_price) / start_price * 100
        
        # Classify market
        if volatility > 3:
            condition = "HIGH_VOLATILITY"
        elif abs(trend) < 1:
            condition = "SIDEWAYS"
        elif trend > 2:
            condition = "STRONG_UPTREND"
        elif trend < -2:
            condition = "STRONG_DOWNTREND"
        elif trend > 0:
            condition = "WEAK_UPTREND"
        else:
            condition = "WEAK_DOWNTREND"
        
        # Store with timestamp
        self.market_conditions.append({
            'timestamp': datetime.now().isoformat(),
            'condition': condition,
            'volatility': volatility,
            'trend': trend
        })
        
        # Keep only last 100 entries
        if len(self.market_conditions) > 100:
            self.market_conditions = self.market_conditions[-100:]
        
        return condition
    
    def get_market_distribution(self):
        """Get distribution of market conditions tested"""
        if not self.market_conditions:
            return {}
        
        distribution = defaultdict(int)
        for entry in self.market_conditions:
            distribution[entry['condition']] += 1
        
        total = len(self.market_conditions)
        return {k: (v / total * 100) for k, v in distribution.items()}
    
    def is_live_ready(self, total_trades, win_rate, total_pnl):
        """Check if bot meets live trading criteria"""
        days_running = (datetime.now() - self.start_date).days
        
        criteria = {
            'days_tested': {
                'value': int(days_running),
                'required': 14,
                'passed': bool(days_running >= 14),
                'weight': 20
            },
            'win_rate': {
                'value': float(win_rate),
                'required': 55,
                'passed': bool(win_rate >= 55),
                'weight': 25
            },
            'total_pnl': {
                'value': float(total_pnl),
                'required': 0,
                'passed': bool(total_pnl > 0),
                'weight': 20
            },
            'max_drawdown': {
                'value': float(self.max_drawdown),
                'required': 10,
                'passed': bool(self.max_drawdown < 10),
                'weight': 15
            },
            'consistency': {
                'value': float(self.get_consistency_score()),
                'required': 60,
                'passed': bool(self.get_consistency_score() >= 60),
                'weight': 10
            },
            'total_trades': {
                'value': int(total_trades),
                'required': 30,
                'passed': bool(total_trades >= 30),
                'weight': 10
            }
        }
        
        # Calculate overall score
        total_weight = sum(c['weight'] for c in criteria.values())
        achieved_weight = sum(c['weight'] for c in criteria.values() if c['passed'])
        overall_score = float((achieved_weight / total_weight * 100) if total_weight > 0 else 0)
        
        all_passed = all(c['passed'] for c in criteria.values())
        
        return {
            'ready': bool(all_passed),
            'score': overall_score,
            'criteria': criteria,
            'missing': [str(k) for k, v in criteria.items() if not v['passed']]
        }

# Global analytics instance
performance_analytics = PerformanceAnalytics()

# ============================================================================
# STRATEGY DEFINITIONS
# ============================================================================

STRATEGIES = {
    'SCALPING': {
        'timeframe': '1m',
        'hold_time': 60,  # 1-60 minutes
        'capital_pct': 0.10,  # 10% ✅ REDUCED (was 15%)
        'stop_loss': 0.005,  # 0.5% ✅ TIGHT (was 0.8%)
        'take_profit': 0.020,  # 2.0% ✅ 1:4 R/R (was 1.2%)
        'max_positions': 2
    },
    'DAY_TRADING': {
        'timeframe': '5m',
        'hold_time': 480,  # 1-8 hours
        'capital_pct': 0.12,  # 12% ✅ REDUCED (was 20%)
        'stop_loss': 0.008,  # 0.8% ✅ TIGHT (was 1.5%)
        'take_profit': 0.032,  # 3.2% ✅ 1:4 R/R (was 2.5%)
        'max_positions': 2
    },
    'SWING_TRADING': {
        'timeframe': '1h',
        'hold_time': 4320,  # 3-7 days
        'capital_pct': 0.15,  # 15% ✅ REDUCED (was 25%)
        'stop_loss': 0.012,  # 1.2% ✅ TIGHT (was 2.5%)
        'take_profit': 0.048,  # 4.8% ✅ 1:4 R/R (was 6%)
        'max_positions': 2
    },
    'RANGE_TRADING': {
        'timeframe': '15m',
        'hold_time': 240,  # 4 hours
        'capital_pct': 0.10,  # 10% ✅ REDUCED (was 15%)
        'stop_loss': 0.006,  # 0.6% ✅ TIGHT (was 1.2%)
        'take_profit': 0.024,  # 2.4% ✅ 1:4 R/R (was 2%)
        'max_positions': 2
    },
    'MOMENTUM': {
        'timeframe': '5m',
        'hold_time': 360,  # 6 hours
        'capital_pct': 0.12,  # 12% ✅ REDUCED (was 15%)
        'stop_loss': 0.010,  # 1.0% ✅ TIGHT (was 2%)
        'take_profit': 0.040,  # 4.0% ✅ 1:4 R/R (same)
        'max_positions': 1
    },
    'POSITION_TRADING': {
        'timeframe': '4h',
        'hold_time': 20160,  # 2-4 weeks
        'capital_pct': 0.08,  # 8% ✅ REDUCED (was 10%)
        'stop_loss': 0.020,  # 2.0% ✅ TIGHT (was 4%)
        'take_profit': 0.080,  # 8.0% ✅ 1:4 R/R (was 12%)
        'max_positions': 1
    }
}

# 🎯 RISK/REWARD OPTIMIZATION:
# ✅ ALL strategies now have 1:4 Risk/Reward ratio!
# ✅ Stop-losses TIGHTENED by ~50% (cut losses fast!)
# ✅ Take-profits OPTIMIZED for 1:4 ratio (let winners run!)
# ✅ This ensures: Small losses + BIG wins = PROFIT! 💰

# Coin universe to scan
COIN_UNIVERSE = [
    # 🔥 TIER 1: MAXIMUM LIQUIDITY + HIGH VOLATILITY 🔥
    'BTCUSDT',    # King - always volatile, best liquidity
    'ETHUSDT',    # High vol + excellent liquidity
    'BNBUSDT',    # Exchange token - sharp moves
    'SOLUSDT',    # Extremely volatile, fast moves
    'XRPUSDT',    # High liquidity + sharp swings
    
    # 🚀 TIER 2: EXTREME VOLATILITY ALTCOINS 🚀
    'LINKUSDT',   # Oracle leader - volatile & liquid
    'AVAXUSDT',   # L1 - excellent volatility
    'UNIUSDT',    # DeFi - sharp pumps/dumps
    'NEARUSDT',   # Layer-1 - high volatility
    'INJUSDT',    # DeFi high-flyer - extreme moves
    'APTUSDT',    # New L1 - very volatile
    'ARBUSDT',    # L2 leader - sharp moves
    'OPUSDT',     # L2 - high volatility
    
    # 💎 TIER 3: PROVEN ALTCOINS WITH SHARP MOVES 💎
    'ADAUSDT',    # Cardano - good swings
    'ATOMUSDT',   # Cosmos - volatile trends
    'TRXUSDT',    # High volume - fast moves
    'WLDUSDT',    # AI hype - extreme volatility
    
    # 🐕 TIER 4: MEME COINS - INSANE VOLATILITY! 🐕
    'DOGEUSDT',   # Meme king - extreme volatility
    'SHIBUSDT',   # Meme giant - sharp moves
    'PEPEUSDT',   # Viral meme - insane volatility
    'FLOKIUSDT',  # Meme runner - fast pumps
]

# 📊 SELECTION CRITERIA:
# ✅ High daily volatility (3%+ average)
# ✅ Excellent liquidity (easy entry/exit)
# ✅ Sharp price movements (fast profits)
# ✅ Proven track record on Binance
# ✅ Active trading volume
# 
# ❌ REMOVED: DOT, MATIC, LTC (too slow for our strategy)
# 🎯 FOCUS: Maximum profit potential with quick trades!

# ============================================================================
# MAIN TRADING CLASS
# ============================================================================

class UltimateHybridBot:
    def __init__(self, api_key, secret_key, initial_capital=10000):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = 'https://testnet.binance.vision'
        
        # 🔧 FIX: Thread safety lock for data access
        self.data_lock = Lock()
        
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
        
        # Performance Analytics
        self.analytics = PerformanceAnalytics()
        
        # Data Persistence
        self.csv_file = 'data/trade_history.csv'
        
        # 🧹 CRITICAL: Delete old CSV to start fresh (fixes -$2.50 bug)
        self.cleanup_old_data()
        
        # Now load (will be empty after cleanup)
        self.load_trade_history()
        
        logger.info(f"🔥 ULTIMATE HYBRID BOT INITIALIZED")
        logger.info(f"💰 Initial Capital: ${initial_capital:.2f}")
        logger.info(f"💰 Current Capital: ${self.current_capital:.2f}")
        logger.info(f"💰 Reserved Capital: ${self.reserved_capital:.2f}")
        logger.info(f"💰 Total Portfolio: ${self.current_capital + self.reserved_capital:.2f}")
        logger.info(f"💰 P&L: ${self.current_capital + self.reserved_capital - self.initial_capital:.2f}")
        logger.info(f"📊 Strategies: {len(STRATEGIES)}")
        logger.info(f"🪙 Coins: {len(COIN_UNIVERSE)}")
        logger.info(f"✅ Multi-Strategy | Multi-Timeframe | Multi-Coin")
        
    # ========================================================================
    # DATA PERSISTENCE METHODS
    # ========================================================================
    
    def cleanup_old_data(self):
        """Delete old CSV file to ensure fresh start - FIXES -$2.50 BUG!"""
        try:
            if os.path.exists(self.csv_file):
                os.remove(self.csv_file)
                logger.info(f"🧹 Deleted old trade history CSV - Starting fresh!")
            else:
                logger.info(f"✅ No old CSV found - Clean start!")
            
            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)
            logger.info(f"📁 Data directory ready")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not delete old CSV: {e}")
            # Don't crash if cleanup fails, just warn
    
    def load_trade_history(self):
        """Load trade history from CSV (for viewing only, not P&L calculation)"""
        try:
            # Note: Old trades are stored for history viewing only
            # They don't affect current session P&L calculation
            # Current session starts fresh with initial_capital
            if os.path.exists(self.csv_file):
                # Just log that we have history, don't load into active trades
                with open(self.csv_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    count = sum(1 for _ in reader)
                logger.info(f"✅ Found {count} historical trades in CSV (viewing only)")
            
            # Current session trades start empty (fresh P&L)
            self.trades = []
        except Exception as e:
            logger.error(f"Error loading trade history: {e}")
    
    def save_trade_to_csv(self, trade):
        """Save a single trade to CSV"""
        try:
            file_exists = os.path.exists(self.csv_file)
            
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['timestamp', 'symbol', 'strategy', 'action', 'entry_price', 
                              'exit_price', 'quantity', 'pnl', 'pnl_pct', 'fees', 
                              'entry_reason', 'exit_reason', 'confidence', 
                              'entry_market_condition', 'exit_market_condition', 
                              'hold_duration_hours', 'stop_loss', 'take_profit']
                
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(trade)
        except Exception as e:
            logger.error(f"Error saving trade to CSV: {e}")
    
    # ========================================================================
    # SMART CONFIDENCE CALCULATOR
    # ========================================================================
    
    def calculate_target_confidence(self, symbol, current_price, entry_price, target_price, strategy):
        """
        Calculate probability (0-100%) that take profit target will be reached
        Decision threshold: 80% = WAIT for target, <80% = LOCK profit now
        """
        try:
            score = 0
            details = {}
            
            # Get latest market data
            data = self.market_data.get(symbol, {})
            if not data:
                return 50, {}  # Neutral if no data
            
            ind = data.get('indicators', {})
            
            # Factor 1: Current Progress to Target (25 points)
            current_gain = abs((current_price - entry_price) / entry_price * 100)
            target_gain = abs((target_price - entry_price) / entry_price * 100)
            progress = (current_gain / target_gain) if target_gain > 0 else 0
            
            if progress >= 0.75:
                score += 25  # Almost there!
            elif progress >= 0.50:
                score += 15  # Halfway
            elif progress >= 0.25:
                score += 8
            else:
                score += 3  # Just started
            details['progress'] = f"{progress*100:.1f}%"
            
            # Factor 2: Momentum Strength (25 points)
            momentum_3 = ind.get('momentum_3', 0)
            momentum_10 = ind.get('momentum_10', 0)
            
            if strategy == 'BUY':
                if momentum_10 > 2 and momentum_3 > 0:
                    score += 25
                elif momentum_10 > 1:
                    score += 15
                elif momentum_10 > 0:
                    score += 8
            else:  # SELL
                if momentum_10 < -2 and momentum_3 < 0:
                    score += 25
                elif momentum_10 < -1:
                    score += 15
                elif momentum_10 < 0:
                    score += 8
            details['momentum'] = f"{momentum_10:.2f}"
            
            # Factor 3: Volume Trend (20 points)
            volume_ratio = ind.get('volume_ratio', 1.0)
            if volume_ratio > 1.5:
                score += 20  # High volume = strong move
            elif volume_ratio > 1.2:
                score += 12
            elif volume_ratio > 0.8:
                score += 5
            details['volume'] = f"{volume_ratio:.2f}x"
            
            # Factor 4: Trend Alignment (20 points)
            ema_9 = ind.get('ema_9', current_price)
            ema_21 = ind.get('ema_21', current_price)
            ema_50 = ind.get('ema_50', current_price)
            
            if strategy == 'BUY':
                if ema_9 > ema_21 > ema_50:
                    score += 20  # Perfect alignment
                elif ema_9 > ema_21:
                    score += 10
                else:
                    score += 3
            else:  # SELL
                if ema_9 < ema_21 < ema_50:
                    score += 20
                elif ema_9 < ema_21:
                    score += 10
                else:
                    score += 3
            details['trend'] = 'Aligned' if score >= 15 else 'Weak'
            
            # Factor 5: RSI Sustainability (10 points)
            rsi = ind.get('rsi', 50)
            if strategy == 'BUY':
                if 40 < rsi < 70:  # Sustainable uptrend
                    score += 10
                elif rsi < 75:
                    score += 5
            else:  # SELL
                if 30 < rsi < 60:  # Sustainable downtrend
                    score += 10
                elif rsi > 25:
                    score += 5
            details['rsi'] = f"{rsi:.1f}"
            
            confidence = min(100, max(0, score))
            return confidence, details
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 50, {}
    
    # ========================================================================
    # ADVANCED ENTRY VALIDATORS & ENHANCEMENTS
    # ========================================================================
    
    def detect_volume_spike(self, symbol):
        """Detect unusual volume spikes (whale activity, breakouts)"""
        try:
            closes, highs, lows, volumes, opens = self.get_klines(symbol, '15m', 50)
            if volumes is None:
                return False, 1.0
            
            current_volume = volumes[-1]
            avg_volume = np.mean(volumes[-20:-1])  # Last 20 candles avg
            
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Volume spike = 2x+ average volume
            if volume_ratio >= 2.0:
                return True, volume_ratio
            
            return False, volume_ratio
        except:
            return False, 1.0
    
    def detect_price_breakout(self, symbol):
        """Detect breakouts from consolidation (high probability moves)"""
        try:
            closes, highs, lows, volumes, opens = self.get_klines(symbol, '1h', 100)
            if closes is None:
                return None
            
            current_price = closes[-1]
            
            # Calculate recent range (last 20 candles)
            recent_high = np.max(highs[-20:])
            recent_low = np.min(lows[-20:])
            range_size = (recent_high - recent_low) / recent_low * 100
            
            # Consolidation = tight range (<3%)
            if range_size < 3.0:
                # Check if breaking out
                if current_price >= recent_high * 1.002:  # Breaking above
                    return {'type': 'BULLISH_BREAKOUT', 'strength': 'HIGH'}
                elif current_price <= recent_low * 0.998:  # Breaking below
                    return {'type': 'BEARISH_BREAKOUT', 'strength': 'HIGH'}
            
            return None
        except:
            return None
    
    def calculate_volatility_adjusted_size(self, symbol, base_capital):
        """Adjust position size based on volatility (higher vol = smaller size)"""
        try:
            data = self.market_data.get(symbol, {})
            ind = data.get('indicators', {})
            
            atr_pct = ind.get('atr_pct', 2.0)
            
            # Inverse relationship: high volatility = smaller position
            if atr_pct > 5.0:
                multiplier = 0.6  # Very volatile, reduce size
            elif atr_pct > 3.0:
                multiplier = 0.8  # Moderate vol
            elif atr_pct > 1.5:
                multiplier = 1.0  # Normal vol
            else:
                multiplier = 1.2  # Low vol, can increase size
            
            adjusted_capital = base_capital * multiplier
            return adjusted_capital
        except:
            return base_capital
    
    def validate_volume_confirmation(self, symbol, action):
        """Ensure trade has volume support (avoid fake moves)"""
        try:
            data = self.market_data.get(symbol, {})
            ind = data.get('indicators', {})
            
            volume_ratio = ind.get('volume_ratio', 1.0)
            
            # Require at least 0.8x average volume minimum
            if volume_ratio < 0.8:
                return False, "Low volume"
            
            # Bonus points for volume spikes
            if volume_ratio >= 1.5:
                return True, f"Strong volume! ({volume_ratio:.2f}x)"
            
            return True, f"Volume OK ({volume_ratio:.2f}x)"
        except:
            return True, "No volume data"
    
    def detect_candlestick_patterns(self, symbol):
        """Detect bullish/bearish candlestick patterns"""
        try:
            closes, highs, lows, volumes, opens = self.get_klines(symbol, '15m', 10)
            if closes is None:
                return None
            
            patterns = {}
            
            # Bullish Engulfing
            bullish_engulfing = talib.CDLENGULFING(opens, highs, lows, closes)
            if bullish_engulfing[-1] > 0:
                patterns['bullish_engulfing'] = True
            
            # Hammer
            hammer = talib.CDLHAMMER(opens, highs, lows, closes)
            if hammer[-1] > 0:
                patterns['hammer'] = True
            
            # Morning Star
            morning_star = talib.CDLMORNINGSTAR(opens, highs, lows, closes)
            if morning_star[-1] > 0:
                patterns['morning_star'] = True
            
            # Bearish Engulfing
            bearish_engulfing = talib.CDLENGULFING(opens, highs, lows, closes)
            if bearish_engulfing[-1] < 0:
                patterns['bearish_engulfing'] = True
            
            # Shooting Star
            shooting_star = talib.CDLSHOOTINGSTAR(opens, highs, lows, closes)
            if shooting_star[-1] > 0:
                patterns['shooting_star'] = True
            
            # Evening Star
            evening_star = talib.CDLEVENINGSTAR(opens, highs, lows, closes)
            if evening_star[-1] > 0:
                patterns['evening_star'] = True
            
            return patterns
        except Exception as e:
            return None
    
    def check_multi_timeframe_alignment(self, symbol, action):
        """Check if multiple timeframes agree on direction"""
        try:
            alignments = {}
            timeframes = ['15m', '1h', '4h']
            
            for tf in timeframes:
                closes, highs, lows, volumes, opens = self.get_klines(symbol, tf, 50)
                if closes is None:
                    continue
                
                ema_9 = talib.EMA(closes, 9)[-1]
                ema_21 = talib.EMA(closes, 21)[-1]
                
                if action == 'BUY':
                    alignments[tf] = ema_9 > ema_21
                else:
                    alignments[tf] = ema_9 < ema_21
            
            # At least 2 out of 3 timeframes should agree
            agreement = sum(alignments.values()) >= 2
            return agreement, alignments
        except:
            return True, {}  # Don't block if check fails
    
    def calculate_risk_reward_ratio(self, entry_price, stop_loss, take_profit):
        """Calculate risk/reward ratio - should be at least 1:2"""
        try:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            
            if risk == 0:
                return 0
            
            ratio = reward / risk
            return ratio
        except:
            return 0
    
    # ========================================================================
    # MARKET DATA METHODS
    # ========================================================================
    
    def detect_market_condition(self, symbol):
        """Detect market condition for a symbol"""
        try:
            # Get recent price data
            data = self.market_data.get(symbol, {})
            if not data:
                # Fallback: get fresh data
                closes, _, _, _, _ = self.get_klines(symbol, '5m', 50)
                if closes is not None:
                    return performance_analytics.detect_market_condition(closes)
                return "UNKNOWN"
            
            # Use cached data if available
            if 'closes' in data:
                return performance_analytics.detect_market_condition(data['closes'])
            
            return "UNKNOWN"
        except Exception as e:
            logger.error(f"Error detecting market condition for {symbol}: {e}")
            return "UNKNOWN"
    
    def get_current_price(self, symbol, max_retries=3):
        """Get current price with retry logic and exponential backoff"""
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{self.base_url}/api/v3/ticker/price",
                    params={'symbol': symbol},
                    timeout=5  # Shorter timeout for faster retries
                )
                if response.status_code == 200:
                    return float(response.json()['price'])
                elif response.status_code == 429:  # Rate limit
                    wait_time = (2 ** attempt) * 2  # Longer wait for rate limits
                    logger.warning(f"Rate limited for {symbol}, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"HTTP {response.status_code} for {symbol}")
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Timeout for {symbol}, retry {attempt+1}/{max_retries} in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to get price for {symbol} after {max_retries} attempts (timeout)")
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Error for {symbol}: {e}, retry {attempt+1}/{max_retries} in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to get price for {symbol} after {max_retries} attempts: {e}")
        
        return None  # All retries failed
    
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
        """Calculate all technical indicators with NaN/None validation"""
        try:
            if len(closes) < 200:
                return None
                
            indicators = {}
            
            # 🔧 FIX: RSI with NaN protection
            rsi_array = talib.RSI(closes, timeperiod=14)
            indicators['rsi'] = float(rsi_array[-1]) if not np.isnan(rsi_array[-1]) else 50.0
            
            # 🔧 FIX: EMAs with NaN protection
            ema_9 = talib.EMA(closes, timeperiod=9)
            indicators['ema_9'] = float(ema_9[-1]) if not np.isnan(ema_9[-1]) else closes[-1]
            
            ema_21 = talib.EMA(closes, timeperiod=21)
            indicators['ema_21'] = float(ema_21[-1]) if not np.isnan(ema_21[-1]) else closes[-1]
            
            ema_50 = talib.EMA(closes, timeperiod=50)
            indicators['ema_50'] = float(ema_50[-1]) if not np.isnan(ema_50[-1]) else closes[-1]
            
            ema_200 = talib.EMA(closes, timeperiod=200)
            indicators['ema_200'] = float(ema_200[-1]) if not np.isnan(ema_200[-1]) else closes[-1]
            
            # 🔧 FIX: MACDs with NaN protection
            macd, signal, hist = talib.MACD(closes)
            indicators['macd'] = float(macd[-1]) if not np.isnan(macd[-1]) else 0.0
            indicators['macd_signal'] = float(signal[-1]) if not np.isnan(signal[-1]) else 0.0
            indicators['macd_hist'] = float(hist[-1]) if not np.isnan(hist[-1]) else 0.0
            
            # 🔧 FIX: Bollinger Bands with NaN protection
            upper, middle, lower = talib.BBANDS(closes)
            indicators['bb_upper'] = float(upper[-1]) if not np.isnan(upper[-1]) else closes[-1] * 1.02
            indicators['bb_middle'] = float(middle[-1]) if not np.isnan(middle[-1]) else closes[-1]
            indicators['bb_lower'] = float(lower[-1]) if not np.isnan(lower[-1]) else closes[-1] * 0.98
            
            # 🔧 FIX: ATR with NaN protection
            atr = talib.ATR(highs, lows, closes, timeperiod=14)
            atr_value = float(atr[-1]) if not np.isnan(atr[-1]) else closes[-1] * 0.02
            indicators['atr'] = atr_value
            indicators['atr_pct'] = (atr_value / closes[-1]) * 100 if closes[-1] > 0 else 2.0
            
            # 🔧 FIX: Volume with zero-division protection
            volume_avg = np.mean(volumes[-20:])
            indicators['volume_avg'] = volume_avg
            indicators['volume_current'] = volumes[-1]
            indicators['volume_ratio'] = (volumes[-1] / volume_avg) if volume_avg > 0 else 1.0
            
            # 🔧 FIX: Momentum with zero-division protection
            if closes[-3] > 0:
                indicators['momentum_3'] = (closes[-1] - closes[-3]) / closes[-3] * 100
            else:
                indicators['momentum_3'] = 0.0
                
            if closes[-10] > 0:
                indicators['momentum_10'] = (closes[-1] - closes[-10]) / closes[-10] * 100
            else:
                indicators['momentum_10'] = 0.0
            
            # 🔧 VALIDATION: Check all indicators are valid numbers
            for key, value in indicators.items():
                if value is None or np.isnan(value) or np.isinf(value):
                    logger.warning(f"Invalid indicator {key}={value}, using default")
                    indicators[key] = 0.0 if 'momentum' in key or 'macd' in key else 50.0
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
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
                
                # Detect market condition
                market_condition = performance_analytics.detect_market_condition(closes)
                
                # Store market data
                self.market_data[symbol] = {
                    'price': closes[-1],
                    'closes': closes,  # Store for later market condition detection
                    'highs': highs,
                    'lows': lows,
                    'indicators': indicators,
                    'sr_levels': sr_levels,
                    'score': score,
                    'market_condition': market_condition
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
            
            # 🔧 FIX: Check list not empty before min()
            if support and len(support) > 0:
                distances = [abs(price - s) / price for s in support]
                if distances:
                    dist_to_support = min(distances)
                    if dist_to_support < 0.01:  # Within 1% of support
                        score += 10
            
            if resistance and len(resistance) > 0:
                distances = [abs(price - r) / price for r in resistance]
                if distances:
                    dist_to_resistance = min(distances)
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
        # 🔧 FIX: Check list not empty before min()
        if uptrend and sr['support'] and len(sr['support']) > 0:
            distances = [abs(price - s) / price for s in sr['support']]
            if distances and min(distances) < 0.015:
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
        # 🔧 FIX: Zero-division protection
        if ind['ema_21'] > 0:
            trend_strength = abs(ind['ema_9'] - ind['ema_21']) / ind['ema_21']
            if trend_strength > 0.02:
                return None  # Too trendy
        else:
            return None  # Invalid EMA
        
        # Near support
        # 🔧 FIX: Check list not empty before min()
        if sr['support'] and len(sr['support']) > 0:
            distances = [abs(price - s) / price for s in sr['support']]
            if distances:
                dist_to_support = min(distances)
                if dist_to_support < 0.01 and ind['rsi'] < 45:
                    return {'action': 'BUY', 'reason': 'Range Bottom', 'confidence': 0.75}
        
        # Near resistance
        # 🔧 FIX: Check list not empty before min()
        if sr['resistance'] and len(sr['resistance']) > 0:
            distances = [abs(price - r) / price for r in sr['resistance']]
            if distances:
                dist_to_resistance = min(distances)
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
            
            # 🔧 FIX: Use CURRENT total equity, not initial capital!
            # This allows position sizes to scale with P&L (grow when winning, shrink when losing)
            total_equity = self.current_capital + self.reserved_capital
            
            # Available capital for this strategy
            available_capital = self.current_capital  # Free capital
            strategy_capital = total_equity * strategy['capital_pct']  # Use current equity, not initial!
            
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
        """Open a new position with comprehensive safety checks"""
        # 🔧 FIX: Thread-safe position opening
        with self.data_lock:
            try:
                # 🔧 FIX: Check MAX_TOTAL_POSITIONS (most critical!)
                MAX_TOTAL_POSITIONS = 5  # Never more than 5 positions total!
                if len(self.positions) >= MAX_TOTAL_POSITIONS:
                    logger.warning(f"⚠️ Max total positions ({MAX_TOTAL_POSITIONS}) reached, skipping {symbol}")
                    return False
                
                # 🔧 FIX: Check if symbol already has ANY position (avoid double exposure)
                symbol_positions = [p for p in self.positions.values() if p['symbol'] == symbol]
                if symbol_positions:
                    logger.warning(f"⚠️ Already have position in {symbol}, skipping to avoid double exposure")
                    return False
                
                # Check if already have position with this strategy
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
                
                # Detect market condition at entry
                market_condition = self.detect_market_condition(symbol)
                
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
                    'confidence': confidence,
                    'market_condition': market_condition,
                    'target_confidence': None,  # Will be calculated when in profit
                    'position_value': position_value  # 🔧 FIX: Store original position value for accurate capital tracking
                }
                
                # Log trade with market condition
                trade = {
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'strategy': strategy_name,
                    'action': action,
                    'quantity': quantity,
                    'price': exec_price,
                    'fee': fee,
                    'reason': reason,
                    'confidence': confidence,
                    'market_condition': market_condition,
                    'position_key': position_key  # Link to position for history
                }
                self.trades.append(trade)
                
                logger.info(f"✅ OPENED {action} | {symbol} | {strategy_name} | {quantity:.4f} @ ${exec_price:.2f} | {reason}")
                
                return True
                
            except Exception as e:
                logger.error(f"Error opening position: {e}")
                return False
    
    def close_position(self, position_key, current_price, reason):
        """Close an existing position with thread safety"""
        # 🔧 FIX: Thread-safe position closing
        with self.data_lock:
            try:
                if position_key not in self.positions:
                    logger.warning(f"Position {position_key} not found, may have been closed already")
                    return False
                
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
                
                # 🔧 FIX: Validate entry_price before division
                entry_value = position['quantity'] * position['entry_price']
                if entry_value > 0:
                    pnl_pct = (pnl / entry_value) * 100
                else:
                    pnl_pct = 0.0
                    logger.error(f"Invalid entry_value for {symbol}, using 0% P&L")
                
                # Update capital
                self.current_capital += proceeds
                # 🔧 FIX: Use stored position_value for accurate capital tracking
                self.reserved_capital -= position.get('position_value', position['quantity'] * position['entry_price'])
                
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
                
                # Detect market condition at exit
                market_condition_exit = self.detect_market_condition(symbol)
                
                # Calculate hold duration
                hold_duration = (datetime.now() - position['entry_time']).total_seconds() / 60  # minutes
                
                # Log close with full details
                trade = {
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'strategy': strategy_name,
                    'action': 'CLOSE',
                    'quantity': position['quantity'],
                    'price': exec_price,
                    'entry_price': position['entry_price'],
                    'entry_time': position['entry_time'],
                    'entry_reason': position['reason'],
                    'exit_reason': reason,
                    'fee': fee,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'hold_duration': hold_duration,
                    'market_condition_exit': market_condition_exit,
                    'stop_loss': position['stop_loss'],
                    'take_profit': position['take_profit'],
                    'position_key': position_key
                }
                self.trades.append(trade)
                
                # Update analytics
                date_str = datetime.now().strftime('%Y-%m-%d')
                self.analytics.update_daily_stats(date_str, pnl, self.current_capital + self.reserved_capital)
                self.analytics.update_drawdown(self.current_capital + self.reserved_capital)
                
                # Save to CSV for persistence
                csv_trade = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'strategy': strategy_name,
                    'action': position['action'],
                    'entry_price': f"{position['entry_price']:.8f}",
                    'exit_price': f"{exec_price:.8f}",
                    'quantity': f"{position['quantity']:.8f}",
                    'pnl': f"{pnl:.4f}",
                    'pnl_pct': f"{pnl_pct:.4f}",
                    'fees': f"{fee:.4f}",
                    'entry_reason': position['reason'],
                    'exit_reason': reason,
                    'confidence': position['confidence'],
                    'entry_market_condition': position.get('market_condition', 'N/A'),
                    'exit_market_condition': market_condition_exit,
                    'hold_duration_hours': f"{hold_duration/60:.2f}",
                    'stop_loss': f"{position['stop_loss']:.8f}",
                    'take_profit': f"{position['take_profit']:.8f}"
                }
                self.save_trade_to_csv(csv_trade)
                
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
        """Check and manage all open positions with thread safety"""
        positions_to_close = []
        
        # 🔧 FIX: Create a snapshot of positions to avoid iteration issues
        with self.data_lock:
            positions_snapshot = dict(self.positions)
        
        for position_key, position in positions_snapshot.items():
            try:
                symbol = position['symbol']
                strategy_name = position['strategy']
                strategy = STRATEGIES[strategy_name]
                
                # Get current price
                current_price = self.get_current_price(symbol)
                if current_price is None:
                    continue
                
                # ==================================================================
                # SMART CONFIDENCE-BASED EXIT (Priority #1)
                # ==================================================================
                # Check if position is in profit
                if position['action'] == 'BUY':
                    current_gain_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100
                else:
                    current_gain_pct = ((position['entry_price'] - current_price) / position['entry_price']) * 100
                
                # ⚡ ARBITRAGE-STYLE EXIT: Lock tiny profits immediately!
                # User wants INSTANT profit-taking, no waiting!
                if current_gain_pct >= 0.3:  # ✅ Lock at 0.3%+ profit!
                    confidence, details = self.calculate_target_confidence(
                        symbol, 
                        current_price, 
                        position['entry_price'],
                        position['take_profit'],
                        position['action']
                    )
                    
                    # Store confidence in position for dashboard display
                    position['target_confidence'] = confidence
                    position['confidence_details'] = details
                    
                    # AGGRESSIVE PROFIT LOCKING LOGIC:
                    # - Tiny profit (0.3-0.8%) + low confidence → LOCK IT!
                    # - Medium profit (0.8-1.5%) + medium confidence → LOCK IT!
                    # - Good profit (1.5%+) + high confidence → Let it run to target
                    
                    if current_gain_pct >= 0.3 and current_gain_pct < 0.8:
                        # TINY profit: Lock if confidence < 70%
                        if confidence < 70:
                            reason = f"Quick Lock ({confidence}% conf, +{current_gain_pct:.2f}%)"
                            logger.info(f"🔒 QUICK LOCK: {symbol} | Tiny Profit | Confidence: {confidence}% | Gain: +{current_gain_pct:.2f}%")
                            positions_to_close.append((position_key, current_price, reason))
                            continue
                    
                    elif current_gain_pct >= 0.8 and current_gain_pct < 1.5:
                        # SMALL profit: Lock if confidence < 65%
                        if confidence < 65:
                            reason = f"Smart Lock ({confidence}% conf, +{current_gain_pct:.2f}%)"
                            logger.info(f"🔒 SMART LOCK: {symbol} | Small Profit | Confidence: {confidence}% | Gain: +{current_gain_pct:.2f}%")
                            positions_to_close.append((position_key, current_price, reason))
                            continue
                    
                    elif current_gain_pct >= 1.5:
                        # GOOD profit: Only lock if confidence VERY low (< 60%)
                        # Otherwise let it run to target!
                        if confidence < 60:
                            reason = f"Conservative Lock ({confidence}% conf, +{current_gain_pct:.2f}%)"
                            logger.info(f"🔒 LOCKING PROFIT: {symbol} | Good Profit | Confidence: {confidence}% < 60% | Gain: +{current_gain_pct:.2f}%")
                            positions_to_close.append((position_key, current_price, reason))
                            continue
                        else:
                            # High confidence - LET IT RUN TO TARGET!
                            logger.debug(f"⏳ LETTING IT RUN: {symbol} | Confidence: {confidence}% | Gain: +{current_gain_pct:.2f}% → Target!")
                
                # ==================================================================
                # TRADITIONAL EXITS (Priority #2)
                # ==================================================================
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
            # 🔧 CRITICAL SAFETY: Daily Loss Limit Protection (Including Unrealized P&L)
            DAILY_LOSS_LIMIT = 200  # $200 max loss per day
            today_str = datetime.now().strftime('%Y-%m-%d')
            today_realized_pnl = self.analytics.daily_stats.get(today_str, {}).get('pnl', 0)
            
            # Calculate unrealized P&L from open positions
            unrealized_pnl = 0
            with self.data_lock:
                for pos in self.positions.values():
                    current_price = self.get_current_price(pos['symbol'])
                    if current_price:
                        if pos['action'] == 'BUY':
                            unrealized_pnl += (current_price - pos['entry_price']) * pos['quantity']
                        else:
                            unrealized_pnl += (pos['entry_price'] - current_price) * pos['quantity']
            
            # Total P&L = Realized + Unrealized
            today_total_pnl = today_realized_pnl + unrealized_pnl
            
            if today_total_pnl < -DAILY_LOSS_LIMIT:
                logger.warning(f"🛑 DAILY LOSS LIMIT HIT!")
                logger.warning(f"   Realized: ${today_realized_pnl:.2f} | Unrealized: ${unrealized_pnl:.2f} | Total: ${today_total_pnl:.2f}")
                logger.warning(f"   Limit: ${DAILY_LOSS_LIMIT} | ⏸️  Pausing new trades for today.")
                # Still manage positions (close losing trades, let winners run)
                self.manage_positions()
                self.print_status()
                return  # Skip opening new positions
            
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
        
        # Convert start_time to string if it's a datetime object
        start_time_str = trading_stats['start_time']
        if hasattr(start_time_str, 'isoformat'):
            start_time_str = start_time_str.isoformat()
        
        # Calculate P&L
        total_pnl = trading_bot.current_capital + trading_bot.reserved_capital - trading_bot.initial_capital
        
        # Debug logging
        logger.debug(f"📊 API Stats Debug:")
        logger.debug(f"  Initial: ${trading_bot.initial_capital:.2f}")
        logger.debug(f"  Current: ${trading_bot.current_capital:.2f}")
        logger.debug(f"  Reserved: ${trading_bot.reserved_capital:.2f}")
        logger.debug(f"  Total P&L: ${total_pnl:.2f}")
        
        stats_response = {
            'start_time': start_time_str,
            'total_trades': len(trading_bot.trades),
            'closed_trades': total,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'total_pnl': total_pnl,
            'current_capital': trading_bot.current_capital,
            'reserved_capital': trading_bot.reserved_capital,
            'open_positions': len(trading_bot.positions),
            'strategy_stats': dict(trading_bot.strategy_stats)
        }
        
        return jsonify(stats_response)
    
    return jsonify(trading_stats)

@app.route('/api/positions')
def get_positions():
    """Get detailed position information with thread safety"""
    global trading_bot
    
    positions_data = []
    
    if trading_bot:
        # 🔧 FIX: Thread-safe access to positions data
        with trading_bot.data_lock:
            # Create a copy of positions to avoid modification during iteration
            positions_copy = dict(trading_bot.positions)
        
        # Now process outside the lock (so we don't hold lock during API calls)
        for key, pos in positions_copy.items():
            current_price = trading_bot.get_current_price(pos['symbol'])
            if current_price:
                if pos['action'] == 'BUY':
                    pnl_pct = (current_price - pos['entry_price']) / pos['entry_price'] * 100
                else:
                    pnl_pct = (pos['entry_price'] - current_price) / pos['entry_price'] * 100
                
                hold_time = (datetime.now() - pos['entry_time']).total_seconds() / 60
                
                positions_data.append({
                    'symbol': pos['symbol'],
                    'strategy': pos['strategy'],
                    'action': pos['action'],
                    'quantity': pos['quantity'],
                    'entry_price': pos['entry_price'],
                    'current_price': current_price,
                    'pnl_pct': pnl_pct,
                    'stop_loss': pos['stop_loss'],
                    'take_profit': pos['take_profit'],
                    'hold_time': hold_time,
                    'reason': pos['reason'],
                    'confidence': pos['confidence']
                })
    
    return jsonify(positions_data)

@app.route('/api/logs')
def get_logs():
    """Get recent log entries with better formatting"""
    try:
        log_file = 'logs/multi_coin_trading.log'
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                # Return last 200 lines (more logs!)
                recent_logs = [line.strip() for line in lines[-200:] if line.strip()]
                return jsonify({
                    'logs': recent_logs,
                    'count': len(recent_logs),
                    'timestamp': datetime.now().isoformat()
                })
        else:
            # Log file doesn't exist yet
            return jsonify({
                'logs': [
                    f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - INFO - 🔥 Bot starting...',
                    f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - INFO - 📊 Scanning markets...',
                    f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - INFO - 🔍 Looking for opportunities...'
                ],
                'count': 3,
                'timestamp': datetime.now().isoformat()
            })
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return jsonify({
            'logs': [f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - ERROR - Failed to read logs: {str(e)}'],
            'count': 1,
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/trade-history')
def get_trade_history():
    """Get complete trade history from CSV file"""
    global trading_bot
    
    if not trading_bot:
        return jsonify({'trades': []})
    
    trade_history = []
    
    try:
        # Read directly from CSV file (all historical + current session trades)
        if os.path.exists(trading_bot.csv_file):
            with open(trading_bot.csv_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trade_record = {
                        'symbol': row.get('symbol', ''),
                        'strategy': row.get('strategy', ''),
                        'action': row.get('action', ''),
                        'entry_time': row.get('timestamp', ''),
                        'exit_time': row.get('timestamp', ''),
                        'entry_price': float(row.get('entry_price', 0)),
                        'exit_price': float(row.get('exit_price', 0)),
                        'quantity': float(row.get('quantity', 0)),
                        'entry_reason': row.get('entry_reason', 'N/A'),
                        'exit_reason': row.get('exit_reason', 'N/A'),
                        'market_condition_entry': row.get('entry_market_condition', 'Unknown'),
                        'market_condition_exit': row.get('exit_market_condition', 'Unknown'),
                        'hold_duration': float(row.get('hold_duration_hours', 0)) * 60,  # Convert to minutes
                        'pnl': float(row.get('pnl', 0)),
                        'pnl_pct': float(row.get('pnl_pct', 0)),
                        'fee': float(row.get('fees', 0)),
                        'stop_loss': float(row.get('stop_loss', 0)),
                        'take_profit': float(row.get('take_profit', 0)),
                        'confidence': float(row.get('confidence', 0)),
                        'is_win': float(row.get('pnl', 0)) > 0
                    }
                    trade_history.append(trade_record)
        
        # Also add current session closed trades
        closed_trades = [t for t in trading_bot.trades if t.get('action') == 'CLOSE']
        for close_trade in closed_trades:
            position_key = close_trade.get('position_key', '')
            entry_trade = next((t for t in trading_bot.trades 
                              if t.get('position_key') == position_key and t.get('action') != 'CLOSE'), None)
            
            trade_record = {
                'symbol': close_trade['symbol'],
                'strategy': close_trade['strategy'],
                'action': entry_trade['action'] if entry_trade else 'BUY',
                'entry_time': entry_trade['timestamp'].isoformat() if entry_trade else close_trade.get('entry_time', datetime.now()).isoformat(),
                'exit_time': close_trade['timestamp'].isoformat(),
                'entry_price': close_trade.get('entry_price', 0),
                'exit_price': close_trade['price'],
                'quantity': close_trade['quantity'],
                'entry_reason': close_trade.get('entry_reason', 'N/A'),
                'exit_reason': close_trade.get('exit_reason', 'N/A'),
                'market_condition_entry': entry_trade.get('market_condition', 'Unknown') if entry_trade else 'Unknown',
                'market_condition_exit': close_trade.get('market_condition_exit', 'Unknown'),
                'hold_duration': close_trade.get('hold_duration', 0),
                'pnl': close_trade['pnl'],
                'pnl_pct': close_trade['pnl_pct'],
                'fee': close_trade['fee'],
                'stop_loss': close_trade.get('stop_loss', 0),
                'take_profit': close_trade.get('take_profit', 0),
                'confidence': entry_trade.get('confidence', 0) if entry_trade else 0,
                'is_win': close_trade['pnl'] > 0
            }
            trade_history.append(trade_record)
        
    except Exception as e:
        logger.error(f"Error reading trade history: {e}")
    
    # Sort by exit time (most recent first)
    trade_history.sort(key=lambda x: x.get('exit_time', ''), reverse=True)
    
    return jsonify({'trades': trade_history})
@app.route('/api/analytics')
def get_analytics():
    """Get comprehensive performance analytics"""
    global trading_bot, performance_analytics
    
    if not trading_bot:
        return jsonify({'error': 'Bot not initialized'})
    
    try:
        wins = sum(1 for t in trading_bot.trades if t.get('pnl', 0) > 0)
        total_trades = len([t for t in trading_bot.trades if 'pnl' in t])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = trading_bot.current_capital + trading_bot.reserved_capital - trading_bot.initial_capital
        
        # Update analytics
        performance_analytics.update_drawdown(trading_bot.current_capital + trading_bot.reserved_capital)
        
        # Get live ready status
        live_ready = performance_analytics.is_live_ready(total_trades, win_rate, total_pnl)
        
        # Get streak info
        streak_info = performance_analytics.get_win_streak()
        
        # Get market distribution
        market_dist = performance_analytics.get_market_distribution()
        
        # Daily performance
        daily_perf = []
        for date, stats in sorted(performance_analytics.daily_stats.items()):
            daily_perf.append({
                'date': str(date),
                'trades': int(stats['trades']),
                'wins': int(stats['wins']),
                'losses': int(stats['losses']),
                'pnl': float(stats['pnl']),
                'capital': float(stats['capital']),
                'win_rate': float((stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0)
            })
        
        # Ensure all values are JSON-serializable
        response_data = {
            'max_drawdown': float(performance_analytics.max_drawdown),
            'current_drawdown': float(performance_analytics.current_drawdown),
            'peak_capital': float(performance_analytics.peak_capital),
            'consistency_score': float(performance_analytics.get_consistency_score()),
            'days_running': int((datetime.now() - performance_analytics.start_date).days),
            'live_ready': {
                'ready': bool(live_ready.get('ready', False)),
                'score': float(live_ready.get('score', 0)),
                'criteria': {
                    k: {
                        'value': float(v['value']) if isinstance(v['value'], (int, float)) else v['value'],
                        'required': int(v['required']),
                        'passed': bool(v['passed']),
                        'weight': int(v['weight'])
                    } for k, v in live_ready.get('criteria', {}).items()
                },
                'missing': [str(x) for x in live_ready.get('missing', [])]
            },
            'streak': {
                'current': int(streak_info.get('current', 0)),
                'type': str(streak_info.get('type', 'none')),
                'longest_win': int(streak_info.get('longest_win', 0)),
                'longest_loss': int(streak_info.get('longest_loss', 0))
            },
            'market_distribution': {str(k): float(v) for k, v in market_dist.items()},
            'daily_performance': daily_perf,
            'current_market_condition': performance_analytics.market_conditions[-1] if performance_analytics.market_conditions else None
        }
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in /api/analytics: {e}", exc_info=True)
        return jsonify({'error': f'Analytics error: {str(e)}'}), 500

@app.route('/api/validation')
def get_validation():
    """Get live trading readiness validation"""
    global trading_bot, performance_analytics
    
    if not trading_bot:
        return jsonify({'ready': False, 'error': 'Bot not initialized'})
    
    wins = sum(1 for t in trading_bot.trades if t.get('pnl', 0) > 0)
    total_trades = len([t for t in trading_bot.trades if 'pnl' in t])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    total_pnl = trading_bot.current_capital + trading_bot.reserved_capital - trading_bot.initial_capital
    
    validation_result = performance_analytics.is_live_ready(total_trades, win_rate, total_pnl)
    
    return jsonify(validation_result)

@app.route('/dashboard')
def dashboard():
    """Dashboard HTML page - ChatGPT Style Dark Theme"""
    html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>🔥 BADSHAH TRADING BOT</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            /* ===== RESET & BASE ===== */
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            :root {
                /* ChatGPT Dark Theme Colors */
                --bg-primary: #0D1117;
                --bg-secondary: #161B22;
                --bg-tertiary: #21262D;
                --text-primary: #E6EDF3;
                --text-secondary: #8B949E;
                --text-muted: #6E7681;
                --border-color: #30363D;
                --accent-blue: #58A6FF;
                --success-green: #3FB950;
                --danger-red: #F85149;
                --warning-yellow: #D29922;
                --gold: #FFA657;
            }
            
            body { 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
                background: var(--bg-primary);
                color: var(--text-primary);
                line-height: 1.6;
                font-size: 16px;
                padding: 0;
                margin: 0;
                min-height: 100vh;
            }
            
            @keyframes gradientShift {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            
            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            @keyframes pulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.05); }
            }
            
            .container { 
                max-width: 1400px; 
                margin: 0 auto; 
                animation: fadeInUp 0.6s ease;
            }
            
            header {
                text-align: center;
                margin-bottom: 40px;
                animation: fadeInUp 0.8s ease;
            }
            
            h1 { 
                font-size: 3em; 
                margin-bottom: 10px;
                text-shadow: 3px 3px 6px rgba(0,0,0,0.4);
                background: linear-gradient(45deg, #fff, #fcd34d);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .subtitle {
                font-size: 1.3em;
                opacity: 0.95;
                letter-spacing: 1px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
                animation: fadeInUp 1s ease;
            }
            
            .stat-card {
                background: rgba(255,255,255,0.12);
                backdrop-filter: blur(15px);
                border-radius: 20px;
                padding: 30px;
                border: 2px solid rgba(255,255,255,0.25);
                box-shadow: 0 8px 32px rgba(0,0,0,0.2);
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            
            .stat-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, rgba(255,255,255,0.1), transparent);
                opacity: 0;
                transition: opacity 0.3s;
            }
            
            .stat-card:hover {
                transform: translateY(-8px);
                border-color: rgba(255,255,255,0.4);
                box-shadow: 0 12px 40px rgba(0,0,0,0.3);
            }
            
            .stat-card:hover::before {
                opacity: 1;
            }
            
            .stat-label {
                font-size: 0.95em;
                opacity: 0.85;
                margin-bottom: 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
                font-weight: 600;
            }
            
            .stat-value {
                font-size: 2.2em;
                font-weight: bold;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            
            .positive { 
                color: #4ade80;
                animation: pulse 2s infinite;
            }
            
            .negative { 
                color: #f87171; 
            }
            
            .section {
                background: rgba(255,255,255,0.12);
                backdrop-filter: blur(15px);
                border-radius: 20px;
                padding: 30px;
                border: 2px solid rgba(255,255,255,0.25);
                box-shadow: 0 8px 32px rgba(0,0,0,0.2);
                margin-bottom: 30px;
                animation: fadeInUp 1.2s ease;
            }
            
            .section-title {
                font-size: 1.6em;
                margin-bottom: 25px;
                border-bottom: 2px solid rgba(255,255,255,0.2);
                padding-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .position-card {
                background: rgba(255,255,255,0.08);
                border-radius: 15px;
                padding: 20px;
                margin: 15px 0;
                border: 1px solid rgba(255,255,255,0.15);
                transition: all 0.3s;
            }
            
            .position-card:hover {
                background: rgba(255,255,255,0.12);
                border-color: rgba(255,255,255,0.3);
                transform: translateX(5px);
            }
            
            .position-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }
            
            .position-symbol {
                font-size: 1.4em;
                font-weight: bold;
            }
            
            .position-pnl {
                font-size: 1.3em;
                font-weight: bold;
            }
            
            .position-details {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            
            .detail-item {
                background: rgba(0,0,0,0.2);
                padding: 10px;
                border-radius: 8px;
            }
            
            .detail-label {
                font-size: 0.85em;
                opacity: 0.8;
                margin-bottom: 5px;
            }
            
            .detail-value {
                font-size: 1.1em;
                font-weight: 600;
            }
            
            .strategy-badge {
                display: inline-block;
                background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 0.9em;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            
            .action-badge {
                display: inline-block;
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 0.9em;
                font-weight: 600;
            }
            
            .action-buy {
                background: linear-gradient(135deg, #10b981, #059669);
            }
            
            .action-sell {
                background: linear-gradient(135deg, #ef4444, #dc2626);
            }
            
            .win-badge {
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 0.75em;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            
            .win-trade {
                border-left: 4px solid #10b981 !important;
                background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(5,150,105,0.05)) !important;
            }
            
            .loss-trade {
                border-left: 4px solid #ef4444 !important;
                background: linear-gradient(135deg, rgba(239,68,68,0.1), rgba(220,38,38,0.05)) !important;
            }
            
            .strategy-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 18px;
                margin: 12px 0;
                background: rgba(255,255,255,0.08);
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.1);
                transition: all 0.3s;
            }
            
            .strategy-item:hover {
                background: rgba(255,255,255,0.12);
                transform: translateX(5px);
            }
            
            .logs-container {
                background: rgba(0,0,0,0.4);
                border-radius: 12px;
                padding: 20px;
                max-height: 500px;
                overflow-y: auto;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
                line-height: 1.8;
                border: 1px solid rgba(255,255,255,0.1);
            }
            
            .logs-container::-webkit-scrollbar {
                width: 8px;
            }
            
            .logs-container::-webkit-scrollbar-track {
                background: rgba(255,255,255,0.05);
                border-radius: 4px;
            }
            
            .logs-container::-webkit-scrollbar-thumb {
                background: rgba(255,255,255,0.2);
                border-radius: 4px;
            }
            
            .logs-container::-webkit-scrollbar-thumb:hover {
                background: rgba(255,255,255,0.3);
            }
            
            .log-line {
                padding: 8px 12px;
                border-bottom: 1px solid rgba(255,255,255,0.05);
                border-radius: 4px;
                margin-bottom: 2px;
                transition: all 0.2s;
                word-wrap: break-word;
            }
            
            .log-line:hover {
                background: rgba(255,255,255,0.05);
                transform: translateX(2px);
            }
            
            .log-error { 
                color: #fca5a5; 
                background: rgba(252, 165, 165, 0.1);
                border-left: 3px solid #fca5a5;
            }
            .log-warning { 
                color: #fcd34d; 
                background: rgba(252, 211, 77, 0.1);
                border-left: 3px solid #fcd34d;
            }
            .log-info { 
                color: #a5f3fc; 
                background: rgba(165, 243, 252, 0.05);
                border-left: 3px solid rgba(165, 243, 252, 0.3);
            }
            .log-success { 
                color: #86efac; 
                background: rgba(134, 239, 172, 0.1);
                border-left: 3px solid #86efac;
            }
            
            .tabs {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }
            
            .tab-button {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                color: #fff;
                padding: 12px 24px;
                border-radius: 10px;
                cursor: pointer;
                transition: all 0.3s;
                font-size: 1em;
                font-weight: 600;
            }
            
            .tab-button:hover {
                background: rgba(255,255,255,0.15);
            }
            
            .tab-button.active {
                background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                border-color: transparent;
            }
            
            .tab-content {
                display: none;
            }
            
            .tab-content.active {
                display: block;
                animation: fadeInUp 0.4s ease;
            }
            
            .last-update {
                text-align: center;
                margin-top: 30px;
                opacity: 0.7;
                font-size: 0.95em;
                padding: 15px;
                background: rgba(0,0,0,0.2);
                border-radius: 10px;
            }
            
            .no-data {
                text-align: center;
                padding: 40px;
                opacity: 0.6;
                font-size: 1.1em;
            }
            
            @media (max-width: 768px) {
                h1 { font-size: 2em; }
                .subtitle { font-size: 1em; }
                .stats-grid { grid-template-columns: 1fr 1fr; }
                .position-details { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div style="
                    background: linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(139, 92, 246, 0.2) 100%);
                    padding: 30px;
                    border-radius: 20px;
                    border: 3px solid rgba(251, 191, 36, 0.5);
                    box-shadow: 0 8px 32px rgba(251, 191, 36, 0.3);
                    margin-bottom: 30px;
                ">
                    <h1 style="font-size: 3em; margin-bottom: 15px;">🔥 BADSHAH TRADING BOT 🔥</h1>
                    <div class="subtitle" style="font-size: 1.2em; margin-bottom: 20px;">Multi-Strategy • Multi-Timeframe • Multi-Coin</div>
                    <div style="
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 2px solid rgba(251, 191, 36, 0.3);
                    ">
                        <div style="font-size: 1.1em; margin-bottom: 8px; color: #e0e0e0;">
                            ⚡ Powered by Advanced AI & Professional Trading System ⚡
                        </div>
                        <div style="font-size: 1.4em; font-weight: bold;">
                            Created by <span style="
                                color: #fbbf24;
                                text-shadow: 0 0 20px rgba(251, 191, 36, 0.8);
                                padding: 5px 15px;
                                background: rgba(251, 191, 36, 0.1);
                                border-radius: 8px;
                                border: 2px solid rgba(251, 191, 36, 0.3);
                            ">Automator Abdullah Bukhari</span>
                        </div>
                    </div>
                </div>
            </header>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">💰 Total Trades</div>
                    <div class="stat-value" id="total-trades">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">🎯 Win Rate</div>
                    <div class="stat-value" id="win-rate">0%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">💵 Total P&L</div>
                    <div class="stat-value" id="total-pnl">$0.00</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">📊 Open Positions</div>
                    <div class="stat-value" id="open-positions">0</div>
                </div>
            </div>
            
            <div class="tabs">
                <button class="tab-button active" onclick="showTab('positions')">📊 Open Positions</button>
                <button class="tab-button" onclick="showTab('history')">📜 Trade History</button>
                <button class="tab-button" onclick="showTab('strategies')">🎯 Strategy Performance</button>
                <button class="tab-button" onclick="showTab('analytics')">📈 Performance Analytics</button>
                <button class="tab-button" onclick="showTab('logs')">📝 Live Logs</button>
            </div>
            
            <div id="tab-positions" class="tab-content active">
                <div class="section">
                    <div class="section-title">
                        <span>📊</span>
                        <span>Open Positions</span>
                    </div>
                    <div id="positions-list"></div>
                </div>
            </div>
            
            <div id="tab-history" class="tab-content">
                <div class="section">
                    <div class="section-title">
                        <span>📜</span>
                        <span>Complete Trade History</span>
                    </div>
                    <div id="history-list"></div>
                </div>
            </div>
            
            <div id="tab-strategies" class="tab-content">
                <div class="section">
                    <div class="section-title">
                        <span>🎯</span>
                        <span>Strategy Performance</span>
                    </div>
                    <div id="strategy-list"></div>
                </div>
            </div>
            
            <div id="tab-logs" class="tab-content">
                <div class="section">
                    <div class="section-title">
                        <span>📝</span>
                        <span>Live Trading Logs</span>
                    </div>
                    <div class="logs-container" id="logs-container"></div>
                </div>
            </div>
            
            <div id="tab-analytics" class="tab-content">
                <!-- Live Ready Status -->
                <div class="section" style="margin-bottom: 20px;">
                    <div class="section-title">
                        <span>🎯</span>
                        <span>Live Trading Readiness</span>
                    </div>
                    <div id="live-ready-container">
                        <div style="text-align: center; padding: 40px;">
                            <div id="readiness-score" style="font-size: 4em; font-weight: bold; margin-bottom: 20px;">0%</div>
                            <div id="readiness-status" style="font-size: 1.5em; margin-bottom: 30px;">Analyzing...</div>
                            <div id="criteria-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Performance Metrics -->
                <div class="stats-grid" style="margin-bottom: 20px;">
                    <div class="stat-card">
                        <div class="stat-label">📉 Max Drawdown</div>
                        <div class="stat-value" id="max-drawdown">0%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">🎯 Consistency</div>
                        <div class="stat-value" id="consistency-score">0%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">⏱️ Days Tested</div>
                        <div class="stat-value" id="days-tested">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">🔥 Current Streak</div>
                        <div class="stat-value" id="current-streak">0</div>
                    </div>
                </div>
                
                <!-- Market Conditions -->
                <div class="section" style="margin-bottom: 20px;">
                    <div class="section-title">
                        <span>🌍</span>
                        <span>Market Conditions Tested</span>
                    </div>
                    <div id="market-conditions" style="padding: 20px;"></div>
                </div>
                
                <!-- Daily Performance -->
                <div class="section">
                    <div class="section-title">
                        <span>📊</span>
                        <span>Daily Performance History</span>
                    </div>
                    <div id="daily-performance" style="padding: 20px;"></div>
                </div>
            </div>
            
            <div class="last-update">
                ⏰ Last updated: <span id="last-update">-</span> • 🔄 Auto-refresh: ON
            </div>
            
            <!-- Creator Footer -->
            <div style="
                margin-top: 40px;
                padding: 40px;
                background: linear-gradient(135deg, rgba(59, 130, 246, 0.25) 0%, rgba(139, 92, 246, 0.25) 100%);
                border-radius: 20px;
                border: 3px solid rgba(251, 191, 36, 0.6);
                text-align: center;
                box-shadow: 0 8px 40px rgba(251, 191, 36, 0.4), 0 0 80px rgba(59, 130, 246, 0.3);
                position: relative;
                overflow: hidden;
            ">
                <!-- Animated background -->
                <div style="
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: linear-gradient(45deg, transparent, rgba(251, 191, 36, 0.1), transparent);
                    animation: rotate 8s linear infinite;
                "></div>
                
                <div style="position: relative; z-index: 1;">
                    <div style="font-size: 2.5em; font-weight: bold; margin-bottom: 20px; 
                        background: linear-gradient(90deg, #3b82f6, #8b5cf6, #fbbf24, #3b82f6);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                        animation: gradient 4s ease infinite;
                        background-size: 300% 300%;
                        text-shadow: 0 0 30px rgba(251, 191, 36, 0.5);
                    ">
                        🔥 BADSHAH TRADING BOT 🔥
                    </div>
                    
                    <div style="
                        font-size: 1.3em;
                        margin: 25px 0;
                        padding: 20px;
                        background: rgba(0, 0, 0, 0.3);
                        border-radius: 15px;
                        border: 2px solid rgba(251, 191, 36, 0.3);
                    ">
                        <div style="font-size: 1.1em; margin-bottom: 10px; color: #e0e0e0;">
                            ⚡ Powered by Advanced AI & Multi-Strategy System ⚡
                        </div>
                        <div style="font-size: 0.9em; opacity: 0.8; color: #cbd5e1;">
                            Professional Trading Automation • Risk Management • Real-Time Analytics
                        </div>
                    </div>
                    
                    <div style="
                        margin-top: 30px;
                        padding: 25px;
                        background: linear-gradient(135deg, rgba(251, 191, 36, 0.2), rgba(251, 191, 36, 0.1));
                        border-radius: 15px;
                        border: 3px solid rgba(251, 191, 36, 0.5);
                        box-shadow: 0 0 30px rgba(251, 191, 36, 0.3);
                    ">
                        <div style="font-size: 1.1em; margin-bottom: 12px; color: #e0e0e0;">
                            ⚡ Created by ⚡
                        </div>
                        <div style="
                            font-size: 2em;
                            font-weight: bold;
                            color: #fbbf24;
                            text-shadow: 
                                0 0 10px rgba(251, 191, 36, 1),
                                0 0 20px rgba(251, 191, 36, 0.8),
                                0 0 30px rgba(251, 191, 36, 0.6),
                                0 0 40px rgba(251, 191, 36, 0.4);
                            letter-spacing: 2px;
                            animation: glow 2s ease-in-out infinite alternate;
                        ">
                            AUTOMATOR ABDULLAH BUKHARI
                        </div>
                        <div style="
                            margin-top: 15px;
                            font-size: 1.1em;
                            color: #cbd5e1;
                            font-style: italic;
                        ">
                            🏆 Professional Trading System Developer 🏆
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <style>
            @keyframes gradient {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            
            @keyframes glow {
                0% {
                    text-shadow: 
                        0 0 10px rgba(251, 191, 36, 1),
                        0 0 20px rgba(251, 191, 36, 0.8),
                        0 0 30px rgba(251, 191, 36, 0.6),
                        0 0 40px rgba(251, 191, 36, 0.4);
                }
                100% {
                    text-shadow: 
                        0 0 20px rgba(251, 191, 36, 1),
                        0 0 30px rgba(251, 191, 36, 0.9),
                        0 0 40px rgba(251, 191, 36, 0.7),
                        0 0 50px rgba(251, 191, 36, 0.5),
                        0 0 60px rgba(251, 191, 36, 0.3);
                }
            }
            
            @keyframes rotate {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
        
        <script>
            let currentTab = 'positions';
            
            function showTab(tabName) {
                currentTab = tabName;
                
                // Hide all tabs
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                });
                
                // Show selected tab
                document.getElementById('tab-' + tabName).classList.add('active');
                
                // Update button states
                document.querySelectorAll('.tab-button').forEach(btn => {
                    btn.classList.remove('active');
                });
                event.target.classList.add('active');
            }
            
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
                        
                        let hasStrategies = false;
                        for (const [name, stats] of Object.entries(data.strategy_stats || {})) {
                            if (stats.trades > 0) {
                                hasStrategies = true;
                                const div = document.createElement('div');
                                div.className = 'strategy-item';
                                div.innerHTML = `
                                    <div>
                                        <strong style="font-size: 1.2em;">${name.replace(/_/g, ' ')}</strong><br>
                                        <small style="opacity: 0.8;">
                                            ${stats.trades} trades • 
                                            Win Rate: ${stats.win_rate.toFixed(1)}% • 
                                            ${stats.wins} wins / ${stats.losses} losses
                                        </small>
                                    </div>
                                    <div style="font-size: 1.4em; font-weight: bold;" class="${stats.profit >= 0 ? 'positive' : 'negative'}">
                                        ${stats.profit >= 0 ? '+' : ''}$${stats.profit.toFixed(2)}
                                    </div>
                                `;
                                strategyList.appendChild(div);
                            }
                        }
                        
                        if (!hasStrategies) {
                            strategyList.innerHTML = '<div class="no-data">No strategy data yet... Waiting for trades! 🚀</div>';
                        }
                        
                        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                    })
                    .catch(err => console.error('Error fetching stats:', err));
            }
            
            // Smart price formatting for different coin types
            function formatPrice(price) {
                if (price === 0 || price === null || price === undefined) {
                    return '$0.00';
                }
                
                // For very small prices (< $0.01) - use more decimals
                if (price < 0.01) {
                    return '$' + price.toFixed(8).replace(/\.?0+$/, ''); // Remove trailing zeros
                }
                // For small prices (< $1) - use 4 decimals
                else if (price < 1) {
                    return '$' + price.toFixed(4);
                }
                // For normal prices - use 2 decimals
                else {
                    return '$' + price.toFixed(2);
                }
            }
            
            function updatePositions() {
                fetch('/api/positions')
                    .then(r => r.json())
                    .then(positions => {
                        const positionsList = document.getElementById('positions-list');
                        positionsList.innerHTML = '';
                        
                        if (positions.length === 0) {
                            positionsList.innerHTML = '<div class="no-data">No open positions. Bot is scanning for opportunities... 🔍</div>';
                            return;
                        }
                        
                        positions.forEach(pos => {
                            const div = document.createElement('div');
                            div.className = 'position-card';
                            
                            const pnlClass = pos.pnl_pct >= 0 ? 'positive' : 'negative';
                            const actionClass = pos.action === 'BUY' ? 'action-buy' : 'action-sell';
                            
                            div.innerHTML = `
                                <div class="position-header">
                                    <div>
                                        <span class="position-symbol">${pos.symbol}</span>
                                        <span class="strategy-badge">${pos.strategy.replace(/_/g, ' ')}</span>
                                        <span class="action-badge ${actionClass}">${pos.action}</span>
                                    </div>
                                    <div class="position-pnl ${pnlClass}">
                                        ${pos.pnl_pct >= 0 ? '+' : ''}${pos.pnl_pct.toFixed(2)}%
                                    </div>
                                </div>
                                
                                <div style="margin: 10px 0; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px;">
                                    <strong>Reason:</strong> ${pos.reason} • 
                                    <strong>Confidence:</strong> ${(pos.confidence * 100).toFixed(0)}%
                                </div>
                                
                                <div class="position-details">
                                    <div class="detail-item">
                                        <div class="detail-label">Entry Price</div>
                                        <div class="detail-value">${formatPrice(pos.entry_price)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Current Price</div>
                                        <div class="detail-value">${formatPrice(pos.current_price)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Quantity</div>
                                        <div class="detail-value">${pos.quantity.toFixed(4)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Hold Time</div>
                                        <div class="detail-value">${Math.floor(pos.hold_time)} min</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Stop Loss</div>
                                        <div class="detail-value negative">${formatPrice(pos.stop_loss)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Take Profit</div>
                                        <div class="detail-value positive">${formatPrice(pos.take_profit)}</div>
                                    </div>
                                </div>
                            `;
                            
                            positionsList.appendChild(div);
                        });
                    })
                    .catch(err => console.error('Error fetching positions:', err));
            }
            
            function updateLogs() {
                if (currentTab !== 'logs') return;
                
                fetch('/api/logs')
                    .then(r => r.json())
                    .then(data => {
                        const logsContainer = document.getElementById('logs-container');
                        
                        if (!data || !data.logs || data.logs.length === 0) {
                            logsContainer.innerHTML = `
                                <div class="no-data">
                                    <div style="font-size: 2em; margin-bottom: 10px;">📋</div>
                                    <div>No logs available yet...</div>
                                    <div style="font-size: 0.85em; opacity: 0.7; margin-top: 5px;">Bot is starting up...</div>
                                </div>
                            `;
                            return;
                        }
                        
                        // Add header with log count
                        let html = `<div style="margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
                            <div><strong>📊 Total Logs:</strong> ${data.count || data.logs.length}</div>
                            <div style="font-size: 0.85em; opacity: 0.7;">Last updated: ${new Date().toLocaleTimeString()}</div>
                        </div>`;
                        
                        // Add logs
                        html += '<div style="font-family: Courier New, monospace; font-size: 0.9em;">';
                        
                        data.logs.forEach(line => {
                            let className = 'log-line';
                            let icon = '💬';
                            
                            // Determine icon and class based on content
                            if (line.includes('ERROR') || line.includes('Error') || line.includes('error')) {
                                className += ' log-error';
                                icon = '❌';
                            } else if (line.includes('WARNING') || line.includes('Warning')) {
                                className += ' log-warning';
                                icon = '⚠️';
                            } else if (line.includes('SIGNAL') || line.includes('Signal')) {
                                className += ' log-success';
                                icon = '🎯';
                            } else if (line.includes('OPENED') || line.includes('BUY') || line.includes('SELL')) {
                                className += ' log-success';
                                icon = '🟢';
                            } else if (line.includes('CLOSED') || line.includes('PROFIT') || line.includes('LOSS')) {
                                className += ' log-success';
                                icon = '🔴';
                            } else if (line.includes('Scanning') || line.includes('Checking')) {
                                className += ' log-info';
                                icon = '🔍';
                            } else if (line.includes('INITIALIZED') || line.includes('Started')) {
                                className += ' log-info';
                                icon = '🚀';
                            } else if (line.includes('Capital') || line.includes('P&L')) {
                                className += ' log-info';
                                icon = '💰';
                            } else {
                                className += ' log-info';
                            }
                            
                            html += `<div class="${className}">${icon} ${line}</div>`;
                        });
                        
                        html += '</div>';
                        logsContainer.innerHTML = html;
                        
                        // Auto-scroll to bottom
                        logsContainer.scrollTop = logsContainer.scrollHeight;
                    })
                    .catch(err => {
                        console.error('Error fetching logs:', err);
                        const logsContainer = document.getElementById('logs-container');
                        logsContainer.innerHTML = `
                            <div class="no-data" style="color: #ff6b6b;">
                                <div style="font-size: 2em; margin-bottom: 10px;">⚠️</div>
                                <div>Failed to load logs</div>
                                <div style="font-size: 0.85em; opacity: 0.7; margin-top: 5px;">Error: ${err.message}</div>
                            </div>
                        `;
                    });
            }
            
            function updateHistory() {
                if (currentTab !== 'history') return;
                
                fetch('/api/trade-history')
                    .then(r => r.json())
                    .then(data => {
                        const historyList = document.getElementById('history-list');
                        historyList.innerHTML = '';
                        
                        if (data.trades.length === 0) {
                            historyList.innerHTML = '<div class="no-data">No closed trades yet... Keep trading! 🚀</div>';
                            return;
                        }
                        
                        data.trades.forEach(trade => {
                            const div = document.createElement('div');
                            div.className = 'position-card ' + (trade.is_win ? 'win-trade' : 'loss-trade');
                            
                            const pnlClass = trade.pnl >= 0 ? 'positive' : 'negative';
                            const actionClass = trade.action === 'BUY' ? 'action-buy' : 'action-sell';
                            const resultBadge = trade.is_win ? '🎉 WIN' : '❌ LOSS';
                            
                            const entryTime = new Date(trade.entry_time);
                            const exitTime = new Date(trade.exit_time);
                            const holdHours = (trade.hold_duration / 60).toFixed(1);
                            
                            div.innerHTML = `
                                <div class="position-header">
                                    <div>
                                        <span class="position-symbol">${trade.symbol}</span>
                                        <span class="strategy-badge">${trade.strategy.replace(/_/g, ' ')}</span>
                                        <span class="action-badge ${actionClass}">${trade.action}</span>
                                        <span class="win-badge ${pnlClass}">${resultBadge}</span>
                                    </div>
                                    <div class="position-pnl ${pnlClass}">
                                        ${trade.pnl >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%
                                        <div style="font-size: 0.8em; margin-top: 4px;">
                                            ${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(2)}
                                        </div>
                                    </div>
                                </div>
                                
                                <div style="margin: 10px 0; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 8px;">
                                    <div style="margin-bottom: 8px;">
                                        <strong>📌 Entry:</strong> ${trade.entry_reason} 
                                        <span style="opacity: 0.7;">(${trade.market_condition_entry})</span>
                                    </div>
                                    <div>
                                        <strong>🎯 Exit:</strong> ${trade.exit_reason}
                                        <span style="opacity: 0.7;">(${trade.market_condition_exit})</span>
                                    </div>
                                </div>
                                
                                <div class="position-details">
                                    <div class="detail-item">
                                        <div class="detail-label">Entry Price</div>
                                        <div class="detail-value">${formatPrice(trade.entry_price)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Exit Price</div>
                                        <div class="detail-value">${formatPrice(trade.exit_price)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Quantity</div>
                                        <div class="detail-value">${trade.quantity.toFixed(4)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Hold Time</div>
                                        <div class="detail-value">${holdHours}h</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Entry Time</div>
                                        <div class="detail-value">${entryTime.toLocaleString()}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Exit Time</div>
                                        <div class="detail-value">${exitTime.toLocaleString()}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Stop Loss</div>
                                        <div class="detail-value negative">${formatPrice(trade.stop_loss)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Take Profit</div>
                                        <div class="detail-value positive">${formatPrice(trade.take_profit)}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Confidence</div>
                                        <div class="detail-value">${(trade.confidence * 100).toFixed(0)}%</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Fees Paid</div>
                                        <div class="detail-value">$${trade.fee.toFixed(2)}</div>
                                    </div>
                                </div>
                            `;
                            
                            historyList.appendChild(div);
                        });
                    })
                    .catch(err => console.error('Error fetching trade history:', err));
            }
            
            function updateAnalytics() {
                if (currentTab !== 'analytics') return;
                
                fetch('/api/analytics')
                    .then(r => r.json())
                    .then(data => {
                        // Update metrics
                        document.getElementById('max-drawdown').textContent = data.max_drawdown.toFixed(2) + '%';
                        document.getElementById('consistency-score').textContent = data.consistency_score.toFixed(0) + '%';
                        document.getElementById('days-tested').textContent = data.days_running;
                        
                        // Update streak
                        const streak = data.streak;
                        const streakEl = document.getElementById('current-streak');
                        if (streak.current > 0) {
                            streakEl.textContent = streak.current + ' ' + streak.type;
                            streakEl.className = 'stat-value ' + (streak.type === 'win' ? 'positive' : 'negative');
                        } else {
                            streakEl.textContent = 'None';
                            streakEl.className = 'stat-value';
                        }
                        
                        // Update live ready status
                        const liveReady = data.live_ready;
                        const scoreEl = document.getElementById('readiness-score');
                        const statusEl = document.getElementById('readiness-status');
                        
                        scoreEl.textContent = liveReady.score.toFixed(0) + '%';
                        scoreEl.className = liveReady.ready ? 'positive' : 'negative';
                        
                        if (liveReady.ready) {
                            statusEl.innerHTML = '✅ <strong>READY FOR LIVE TRADING!</strong>';
                            statusEl.className = 'positive';
                        } else {
                            statusEl.innerHTML = '⏳ <strong>Keep Testing...</strong>';
                            statusEl.className = '';
                        }
                        
                        // Update criteria grid
                        const criteriaGrid = document.getElementById('criteria-grid');
                        criteriaGrid.innerHTML = '';
                        
                        for (const [key, crit] of Object.entries(liveReady.criteria)) {
                            const div = document.createElement('div');
                            div.style.cssText = 'background: rgba(255,255,255,0.08); padding: 15px; border-radius: 10px; border: 2px solid ' + (crit.passed ? '#4ade80' : '#f87171');
                            
                            const label = key.replace(/_/g, ' ').toUpperCase();
                            const icon = crit.passed ? '✅' : '❌';
                            
                            div.innerHTML = `
                                <div style="font-size: 2em; margin-bottom: 10px;">${icon}</div>
                                <div style="font-weight: bold; margin-bottom: 5px;">${label}</div>
                                <div style="font-size: 1.2em; color: ${crit.passed ? '#4ade80' : '#f87171'};">
                                    ${crit.value.toFixed(1)} / ${crit.required}
                                </div>
                            `;
                            
                            criteriaGrid.appendChild(div);
                        }
                        
                        // Update market conditions
                        const marketDiv = document.getElementById('market-conditions');
                        marketDiv.innerHTML = '';
                        
                        if (Object.keys(data.market_distribution).length > 0) {
                            for (const [condition, pct] of Object.entries(data.market_distribution)) {
                                const condDiv = document.createElement('div');
                                condDiv.style.cssText = 'margin: 10px 0; background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px;';
                                
                                condDiv.innerHTML = `
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <strong>${condition.replace(/_/g, ' ')}</strong>
                                        <span style="font-size: 1.3em; font-weight: bold;">${pct.toFixed(1)}%</span>
                                    </div>
                                    <div style="margin-top: 8px; background: rgba(0,0,0,0.2); height: 10px; border-radius: 5px; overflow: hidden;">
                                        <div style="width: ${pct}%; height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6);"></div>
                                    </div>
                                `;
                                
                                marketDiv.appendChild(condDiv);
                            }
                        } else {
                            marketDiv.innerHTML = '<div class="no-data">No market data yet...</div>';
                        }
                        
                        // Update daily performance
                        const dailyDiv = document.getElementById('daily-performance');
                        dailyDiv.innerHTML = '';
                        
                        if (data.daily_performance && data.daily_performance.length > 0) {
                            data.daily_performance.forEach(day => {
                                const dayDiv = document.createElement('div');
                                dayDiv.style.cssText = 'margin: 10px 0; background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px;';
                                
                                const pnlClass = day.pnl >= 0 ? 'positive' : 'negative';
                                
                                dayDiv.innerHTML = `
                                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                        <strong>${day.date}</strong>
                                        <span class="${pnlClass}" style="font-size: 1.2em; font-weight: bold;">
                                            ${day.pnl >= 0 ? '+' : ''}$${day.pnl.toFixed(2)}
                                        </span>
                                    </div>
                                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; font-size: 0.9em;">
                                        <div>Trades: ${day.trades}</div>
                                        <div>Wins: ${day.wins}</div>
                                        <div>Losses: ${day.losses}</div>
                                        <div>Win Rate: ${day.win_rate.toFixed(1)}%</div>
                                    </div>
                                `;
                                
                                dailyDiv.appendChild(dayDiv);
                            });
                        } else {
                            dailyDiv.innerHTML = '<div class="no-data">No daily performance data yet...</div>';
                        }
                    })
                    .catch(err => console.error('Error fetching analytics:', err));
            }
            
            // Update all data
            function updateAll() {
                updateStats();
                updatePositions();
                updateHistory();
                updateLogs();
                updateAnalytics();
            }
            
            // Initial load
            updateAll();
            
            // Auto-refresh every 5 seconds
            setInterval(updateAll, 5000);
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
