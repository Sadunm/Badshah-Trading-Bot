# -*- coding: utf-8 -*-
"""
Live Multi-Coin Paper Trading Bot
Supports trading multiple coins simultaneously
"""

import os
import sys
import time
import requests
import json
import logging
import numpy as np
import talib
from datetime import datetime
from threading import Thread
from flask import Flask, jsonify

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

class MultiCoinTrading:
    def __init__(self, api_key, secret_key, initial_capital=10000):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = 'https://testnet.binance.vision'
        
        # Trading state
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}  # {symbol: {'quantity': X, 'avg_price': Y, 'entry_price': Z}}
        self.trades = []
        self.is_running = True
        
        # Trading costs
        self.fee_rate = 0.0005  # 0.05%
        self.slippage_rate = 0.0002  # 0.02%
        
        # Strategy parameters (OPTIMIZED)
        self.rsi_period = 14
        self.rsi_oversold = 35  # Buy signal
        self.rsi_overbought = 65  # Sell signal
        self.ema_fast = 9
        self.ema_slow = 21
        self.stop_loss_pct = 0.015  # 1.5% stop loss
        self.take_profit_pct = 0.025  # 2.5% take profit
        self.risk_per_trade = 0.005  # 0.5% per trade (reduced)
        
        logger.info(f"Multi-Coin Trading initialized with ${initial_capital:.2f}")
        logger.info(f"[STRATEGY] 🔥 ADAPTIVE MULTI-STRATEGY SYSTEM - Auto Market Detection")
        logger.info(f"[INDICATORS] RSI({self.rsi_period}) + EMA({self.ema_fast}/{self.ema_slow}) + ATR + SL/TP")
        logger.info(f"[STRATEGIES] Scalping | Momentum | Fade | Range | Buy Dips | Adaptive")
        
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
        except requests.exceptions.Timeout:
            logger.error(f"Timeout getting price for {symbol}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def get_historical_data(self, symbol, interval='5m', limit=100):
        """Get historical kline/candlestick data"""
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
                # Extract close prices
                closes = np.array([float(k[4]) for k in klines])
                highs = np.array([float(k[2]) for k in klines])
                lows = np.array([float(k[3]) for k in klines])
                return closes, highs, lows
            return None, None, None
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return None, None, None
    
    def calculate_rsi(self, closes):
        """Calculate RSI indicator"""
        try:
            if len(closes) < self.rsi_period + 1:
                return None
            rsi = talib.RSI(closes, timeperiod=self.rsi_period)
            return rsi[-1]  # Return latest RSI
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None
    
    def calculate_ema(self, closes):
        """Calculate EMA indicators"""
        try:
            if len(closes) < max(self.ema_fast, self.ema_slow) + 1:
                return None, None
            ema_fast = talib.EMA(closes, timeperiod=self.ema_fast)
            ema_slow = talib.EMA(closes, timeperiod=self.ema_slow)
            return ema_fast[-1], ema_slow[-1]
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return None, None
    
    def calculate_volatility(self, closes, highs, lows):
        """Calculate market volatility (ATR - Average True Range)"""
        try:
            if len(closes) < 14:
                return None
            atr = talib.ATR(highs, lows, closes, timeperiod=14)
            # Normalize ATR as % of price
            volatility_pct = (atr[-1] / closes[-1]) * 100
            return volatility_pct
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return None
    
    def detect_market_condition(self, closes, highs, lows, rsi, ema_fast, ema_slow):
        """Detect current market condition for adaptive strategy selection"""
        try:
            # Calculate additional metrics
            volatility = self.calculate_volatility(closes, highs, lows)
            if volatility is None:
                return 'UNKNOWN'
            
            # Calculate trend strength
            trend_strength = abs(ema_fast - ema_slow) / ema_slow * 100
            
            # Calculate price momentum
            price_change_5 = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
            price_change_10 = (closes[-1] - closes[-10]) / closes[-10] * 100 if len(closes) >= 10 else 0
            
            # Detect conditions
            if volatility > 3.0:  # High volatility
                return 'HIGH_VOLATILITY'
            elif trend_strength > 2.0 and ema_fast > ema_slow and price_change_10 > 2.0:
                return 'STRONG_UPTREND'
            elif trend_strength > 2.0 and ema_fast < ema_slow and price_change_10 < -2.0:
                return 'STRONG_DOWNTREND'
            elif trend_strength < 0.5 and 45 <= rsi <= 55:
                return 'RANGING'
            elif ema_fast > ema_slow:
                return 'WEAK_UPTREND'
            elif ema_fast < ema_slow:
                return 'WEAK_DOWNTREND'
            else:
                return 'NEUTRAL'
                
        except Exception as e:
            logger.error(f"Error detecting market condition: {e}")
            return 'UNKNOWN'
    
    def generate_signal(self, symbol):
        """🔥 ADAPTIVE MULTI-STRATEGY SYSTEM - Auto detects market & applies best strategy"""
        try:
            # Get historical data
            closes, highs, lows = self.get_historical_data(symbol)
            if closes is None or len(closes) < 50:
                return None, None
            
            # Calculate indicators
            rsi = self.calculate_rsi(closes)
            ema_fast, ema_slow = self.calculate_ema(closes)
            
            if rsi is None or ema_fast is None or ema_slow is None:
                return None, None
            
            current_price = closes[-1]
            prev_price = closes[-2]
            
            # 🔍 DETECT MARKET CONDITION
            market_condition = self.detect_market_condition(closes, highs, lows, rsi, ema_fast, ema_slow)
            
            # Calculate metrics for strategies
            price_change_3 = (closes[-1] - closes[-3]) / closes[-3] * 100 if len(closes) >= 3 else 0
            ema_cross_up = closes[-2] < ema_slow and current_price > ema_slow
            ema_cross_down = closes[-2] > ema_fast and current_price < ema_fast
            
            # 🎯 STRATEGY 1: HIGH VOLATILITY → SCALPING (Quick in/out)
            if market_condition == 'HIGH_VOLATILITY':
                # Buy on quick dips, sell on quick pumps
                if rsi < 45 and price_change_3 < -0.5:
                    logger.info(f"[SIGNAL] {symbol} BUY: Scalping Dip | Volatility High, RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'BUY', current_price
                elif rsi > 55 and price_change_3 > 0.5:
                    logger.info(f"[SIGNAL] {symbol} SELL: Scalping Pump | Volatility High, RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'SELL', current_price
            
            # 🎯 STRATEGY 2: STRONG UPTREND → MOMENTUM + BUY DIPS
            elif market_condition == 'STRONG_UPTREND':
                # Buy dips in uptrend OR momentum continuation
                if rsi < 50 or ema_cross_up:
                    reason = f"Momentum/Dip Buy | Strong Uptrend, RSI={rsi:.1f}"
                    logger.info(f"[SIGNAL] {symbol} BUY: {reason}, Price=${current_price:.2f}")
                    return 'BUY', current_price
                elif rsi > 70:  # Only sell if extremely overbought
                    logger.info(f"[SIGNAL] {symbol} SELL: Extreme Overbought | RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'SELL', current_price
            
            # 🎯 STRATEGY 3: STRONG DOWNTREND → FADE/REVERSE (Sell rallies)
            elif market_condition == 'STRONG_DOWNTREND':
                # Sell rallies in downtrend OR momentum continuation
                if rsi > 50 or ema_cross_down:
                    reason = f"Fade Rally | Strong Downtrend, RSI={rsi:.1f}"
                    logger.info(f"[SIGNAL] {symbol} SELL: {reason}, Price=${current_price:.2f}")
                    return 'SELL', current_price
                elif rsi < 30:  # Only buy if extremely oversold
                    logger.info(f"[SIGNAL] {symbol} BUY: Extreme Oversold | RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'BUY', current_price
            
            # 🎯 STRATEGY 4: RANGING → RANGE TRADING (Buy low, sell high)
            elif market_condition == 'RANGING':
                # Buy at bottom of range, sell at top
                if rsi < 40:
                    logger.info(f"[SIGNAL] {symbol} BUY: Range Bottom | RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'BUY', current_price
                elif rsi > 60:
                    logger.info(f"[SIGNAL] {symbol} SELL: Range Top | RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'SELL', current_price
            
            # 🎯 STRATEGY 5: WEAK UPTREND → MODERATE MOMENTUM
            elif market_condition == 'WEAK_UPTREND':
                if rsi < 45:
                    logger.info(f"[SIGNAL] {symbol} BUY: Weak Uptrend Dip | RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'BUY', current_price
                elif rsi > 65:
                    logger.info(f"[SIGNAL] {symbol} SELL: Overbought | RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'SELL', current_price
            
            # 🎯 STRATEGY 6: WEAK DOWNTREND → CAREFUL TRADING
            elif market_condition == 'WEAK_DOWNTREND':
                if rsi < 35:
                    logger.info(f"[SIGNAL] {symbol} BUY: Oversold Bounce | RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'BUY', current_price
                elif rsi > 55:
                    logger.info(f"[SIGNAL] {symbol} SELL: Weak Downtrend Rally | RSI={rsi:.1f}, Price=${current_price:.2f}")
                    return 'SELL', current_price
            
            # Debug: Log market condition
            logger.info(f"[{symbol}] No signal | Market: {market_condition}, RSI={rsi:.1f}, Price=${current_price:.2f}")
            
            return None, current_price
            
        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return None, None
    
    def check_stop_loss_take_profit(self, symbol, current_price):
        """Check if stop-loss or take-profit is hit"""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        entry_price = position.get('entry_price', position['avg_price'])
        
        # Calculate PnL percentage
        pnl_pct = (current_price - entry_price) / entry_price
        
        # Stop Loss hit
        if pnl_pct <= -self.stop_loss_pct:
            logger.warning(f"[STOP-LOSS] {symbol}: {pnl_pct*100:.2f}% loss - Auto selling!")
            return 'SELL'
        
        # Take Profit hit
        elif pnl_pct >= self.take_profit_pct:
            logger.info(f"[TAKE-PROFIT] {symbol}: {pnl_pct*100:.2f}% profit - Auto selling!")
            return 'SELL'
        
        return None
    
    def calculate_position_size(self, price, symbol):
        """Calculate appropriate position size based on capital and price"""
        # Use configured risk per trade (0.5%)
        risk_amount = self.current_capital * self.risk_per_trade
        
        # Calculate quantity
        quantity = risk_amount / price
        
        # Round to appropriate decimals
        if price > 1000:  # BTC, ETH
            quantity = round(quantity, 4)
        elif price > 100:  # BNB, etc
            quantity = round(quantity, 3)
        elif price > 1:
            quantity = round(quantity, 2)
        else:  # Small price coins
            quantity = round(quantity, 1)
        
        return quantity
    
    def place_order(self, symbol, side, price):
        """Place a paper trading order"""
        try:
            quantity = self.calculate_position_size(price, symbol)
            
            if quantity <= 0:
                logger.warning(f"Invalid quantity for {symbol}")
                return None
            
            # Apply slippage
            if side == 'BUY':
                exec_price = price * (1 + self.slippage_rate)
            else:
                exec_price = price * (1 - self.slippage_rate)
            
            # Calculate costs
            cost = quantity * exec_price
            fee = cost * self.fee_rate
            total_cost = cost + fee
            
            if side == 'BUY':
                # Check capital
                if total_cost > self.current_capital:
                    logger.warning(f"Insufficient capital for {symbol}: need ${total_cost:.2f}, have ${self.current_capital:.2f}")
                    return None
                
                # Execute buy
                self.current_capital -= total_cost
                
                if symbol not in self.positions:
                    self.positions[symbol] = {'quantity': 0, 'avg_price': 0, 'entry_price': exec_price}
                
                # Update position
                old_qty = self.positions[symbol]['quantity']
                old_price = self.positions[symbol]['avg_price']
                new_qty = old_qty + quantity
                new_avg_price = ((old_qty * old_price) + (quantity * exec_price)) / new_qty if new_qty > 0 else exec_price
                
                # Store entry price for first buy
                entry_price = self.positions[symbol].get('entry_price', exec_price)
                
                self.positions[symbol] = {
                    'quantity': new_qty,
                    'avg_price': new_avg_price,
                    'entry_price': entry_price if old_qty > 0 else exec_price  # Reset on new position
                }
                
                order = {
                    'symbol': symbol,
                    'side': 'BUY',
                    'quantity': quantity,
                    'price': exec_price,
                    'fee': fee,
                    'timestamp': datetime.now()
                }
                
                self.trades.append(order)
                logger.info(f"[BUY] {quantity:.4f} {symbol} @ ${exec_price:.2f} (Fee: ${fee:.2f})")
                return order
                
            elif side == 'SELL':
                # Check position
                if symbol not in self.positions or self.positions[symbol]['quantity'] <= 0:
                    logger.warning(f"No position to sell for {symbol}")
                    return None
                
                # Use available quantity
                quantity = min(quantity, self.positions[symbol]['quantity'])
                
                # Calculate proceeds
                proceeds = quantity * exec_price
                fee = proceeds * self.fee_rate
                net_proceeds = proceeds - fee
                
                # Calculate PnL
                entry_cost = quantity * self.positions[symbol]['avg_price']
                entry_fee = entry_cost * self.fee_rate
                pnl = net_proceeds - entry_cost - entry_fee
                
                # Execute sell
                self.current_capital += net_proceeds
                
                # Update position
                self.positions[symbol]['quantity'] -= quantity
                
                if self.positions[symbol]['quantity'] <= 0.0001:
                    del self.positions[symbol]
                
                order = {
                    'symbol': symbol,
                    'side': 'SELL',
                    'quantity': quantity,
                    'price': exec_price,
                    'fee': fee,
                    'pnl': pnl,
                    'timestamp': datetime.now()
                }
                
                self.trades.append(order)
                logger.info(f"[SELL] {quantity:.4f} {symbol} @ ${exec_price:.2f} (PnL: ${pnl:.2f})")
                return order
        
        except Exception as e:
            logger.error(f"Order error for {symbol}: {e}")
            return None
    
    def get_portfolio_value(self, prices):
        """Calculate total portfolio value"""
        total = self.current_capital
        
        for symbol, position in self.positions.items():
            if symbol in prices and prices[symbol]:
                total += position['quantity'] * prices[symbol]
        
        return total
    
    def update_global_stats(self, prices):
        """Update global trading stats for dashboard"""
        global trading_stats
        
        portfolio_value = self.get_portfolio_value(prices)
        pnl = portfolio_value - self.initial_capital
        pnl_pct = (pnl / self.initial_capital) * 100
        
        # Calculate win rate
        wins = sum(1 for t in self.trades if t['side'] == 'SELL' and t.get('pnl', 0) > 0)
        total_sells = sum(1 for t in self.trades if t['side'] == 'SELL')
        win_rate = (wins / total_sells * 100) if total_sells > 0 else 0
        
        # Update positions list
        positions_list = []
        for symbol, pos in self.positions.items():
            current_price = prices.get(symbol, 0)
            value = pos['quantity'] * current_price if current_price else 0
            pos_pnl = value - (pos['quantity'] * pos['avg_price'])
            pos_pnl_pct = (pos_pnl / (pos['quantity'] * pos['avg_price']) * 100) if pos['quantity'] * pos['avg_price'] > 0 else 0
            
            positions_list.append({
                'symbol': symbol,
                'quantity': pos['quantity'],
                'avg_price': pos['avg_price'],
                'current_price': current_price,
                'value': value,
                'pnl': pos_pnl,
                'pnl_pct': pos_pnl_pct
            })
        
        # Update recent trades (last 20)
        recent_trades = []
        for trade in self.trades[-20:]:
            recent_trades.append({
                'symbol': trade['symbol'],
                'side': trade['side'],
                'quantity': trade['quantity'],
                'price': trade['price'],
                'total': trade['quantity'] * trade['price'],
                'time': trade['timestamp'].strftime('%H:%M:%S')
            })
        
        # Update global stats
        trading_stats.update({
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'portfolio_value': portfolio_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'positions': positions_list,
            'recent_trades': recent_trades,
            'last_update': datetime.now().isoformat()
        })
    
    def print_status(self, prices):
        """Print current status"""
        portfolio_value = self.get_portfolio_value(prices)
        pnl = portfolio_value - self.initial_capital
        pnl_pct = (pnl / self.initial_capital) * 100
        
        logger.info(f"[CAPITAL] ${self.current_capital:.2f} | Portfolio: ${portfolio_value:.2f} | PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")
        
        if self.positions:
            logger.info(f"[POSITIONS] {len(self.positions)}")
            for symbol, pos in self.positions.items():
                current_price = prices.get(symbol, 0)
                value = pos['quantity'] * current_price if current_price else 0
                logger.info(f"   {symbol}: {pos['quantity']:.4f} @ ${pos['avg_price']:.2f} | Current: ${current_price:.2f} | Value: ${value:.2f}")
        else:
            logger.info("[POSITIONS] No open positions")
        
        if self.trades:
            wins = sum(1 for t in self.trades if t['side'] == 'SELL' and t.get('pnl', 0) > 0)
            total_sells = sum(1 for t in self.trades if t['side'] == 'SELL')
            win_rate = (wins / total_sells * 100) if total_sells > 0 else 0
            logger.info(f"[STATS] Trades: {len(self.trades)} | Win Rate: {win_rate:.1f}%")
        
        # Update global stats for dashboard
        self.update_global_stats(prices)
    
    def start_trading(self, symbols, cycles=10):
        """Start multi-coin trading with RSI + EMA strategy"""
        logger.info(f"[START] Trading {len(symbols)} coins with Advanced Strategy")
        logger.info(f"[STRATEGY] RSI({self.rsi_period}) + EMA({self.ema_fast}/{self.ema_slow})")
        logger.info(f"[RISK] Stop-Loss: {self.stop_loss_pct*100:.1f}% | Take-Profit: {self.take_profit_pct*100:.1f}%")
        logger.info(f"[COINS] {', '.join(symbols)}")
        
        try:
            for cycle in range(1, cycles + 1):
                logger.info(f"\n{'='*70}")
                logger.info(f"CYCLE {cycle}/{cycles}")
                logger.info(f"{'='*70}")
                
                # Get current prices
                prices = {}
                for symbol in symbols:
                    price = self.get_current_price(symbol)
                    if price:
                        prices[symbol] = price
                        logger.info(f"[PRICE] {symbol}: ${price:.2f}")
                    else:
                        logger.warning(f"[WARNING] Failed to get price for {symbol}")
                
                if not prices:
                    logger.error("[ERROR] No prices available, skipping cycle")
                    time.sleep(60)
                    continue
                
                # Strategy-based trading logic
                for symbol in symbols:
                    try:
                        current_price = prices.get(symbol)
                        if not current_price:
                            continue
                        
                        # Check Stop-Loss / Take-Profit first (for existing positions)
                        if symbol in self.positions and self.positions[symbol]['quantity'] > 0:
                            sl_tp_action = self.check_stop_loss_take_profit(symbol, current_price)
                            if sl_tp_action == 'SELL':
                                self.place_order(symbol, 'SELL', current_price)
                                continue
                        
                        # Generate trading signal based on indicators
                        signal, signal_price = self.generate_signal(symbol)
                        
                        if signal == 'BUY':
                            # Only buy if we don't have a position
                            if symbol not in self.positions or self.positions[symbol]['quantity'] == 0:
                                # Check if we have enough capital (max 5 positions)
                                if len([p for p in self.positions.values() if p['quantity'] > 0]) < 5:
                                    self.place_order(symbol, 'BUY', current_price)
                                else:
                                    logger.warning(f"[LIMIT] Max 5 positions reached, skipping {symbol}")
                        
                        elif signal == 'SELL':
                            # Only sell if we have a position
                            if symbol in self.positions and self.positions[symbol]['quantity'] > 0:
                                self.place_order(symbol, 'SELL', current_price)
                    
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        continue
                
                # Print status
                logger.info("")
                self.print_status(prices)
                
                # Wait before next cycle (1 minute for more frequent signals)
                if cycle < cycles:
                    logger.info(f"\n[WAIT] Waiting 1 minute...\n")
                    time.sleep(60)
            
            # Final summary
            logger.info(f"\n{'='*70}")
            logger.info("[SUMMARY] FINAL SUMMARY")
            logger.info(f"{'='*70}")
            
            final_prices = {s: self.get_current_price(s) for s in symbols}
            self.print_status(final_prices)
            
            # Close all positions at end of cycle
            logger.info("\n[CLOSING] Closing all positions...")
            for symbol in list(self.positions.keys()):
                if self.positions[symbol]['quantity'] > 0:
                    price = final_prices.get(symbol)
                    if price:
                        self.place_order(symbol, 'SELL', price)
            
            # Final stats
            final_value = self.current_capital
            total_pnl = final_value - self.initial_capital
            total_pnl_pct = (total_pnl / self.initial_capital) * 100
            
            logger.info(f"\n{'='*70}")
            logger.info("[COMPLETE] TRADING CYCLE COMPLETE!")
            logger.info(f"{'='*70}")
            logger.info(f"Initial Capital: ${self.initial_capital:.2f}")
            logger.info(f"Final Capital: ${final_value:.2f}")
            logger.info(f"Total PnL: ${total_pnl:.2f} ({total_pnl_pct:+.2f}%)")
            logger.info(f"Total Trades: {len(self.trades)}")
            
            return True
            
        except KeyboardInterrupt:
            logger.info("\n[STOPPED] Trading stopped by user")
            return False
        except Exception as e:
            logger.error(f"[ERROR] Trading error: {e}")
            import traceback
            traceback.print_exc()
            return False

def load_symbols_from_config():
    """Load trading symbols from config"""
    try:
        with open('config/adaptive_config.json', 'r') as f:
            config = json.load(f)
        
        # Extract unique symbols from strategies
        symbols = list(set([s['symbol'] for s in config.get('strategies', [])]))
        return symbols
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")
        return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']  # Default

# Flask app for health check (Render.com keep-alive)
app = Flask(__name__)

# Global variable to store trading stats
trading_stats = {
    'initial_capital': 10000,
    'current_capital': 10000,
    'portfolio_value': 10000,
    'pnl': 0,
    'pnl_pct': 0,
    'total_trades': 0,
    'win_rate': 0,
    'positions': [],
    'recent_trades': [],
    'last_update': datetime.now().isoformat()
}

@app.route('/')
def home():
    """Home endpoint"""
    return jsonify({
        'status': 'running',
        'bot': 'BADSHAH Trading Bot',
        'version': '1.0',
        'message': 'Bot is alive and trading!'
    })

@app.route('/health')
def health():
    """Health check endpoint for UptimeRobot"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/status')
def status():
    """Trading status endpoint"""
    try:
        # Try to get BTC price to verify API connection
        response = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT', timeout=5)
        btc_price = response.json().get('price', 'N/A') if response.status_code == 200 else 'N/A'
        
        return jsonify({
            'status': 'active',
            'bot': 'Multi-Coin Trading',
            'btc_price': btc_price,
            'timestamp': datetime.now().isoformat()
        })
    except:
        return jsonify({
            'status': 'active',
            'bot': 'Multi-Coin Trading',
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/stats')
def api_stats():
    """API endpoint for trading stats (JSON)"""
    return jsonify(trading_stats)

@app.route('/dashboard')
def dashboard():
    """Live trading dashboard"""
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BADSHAH Trading Bot - Live Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-label {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        
        .positive {
            color: #10b981;
        }
        
        .negative {
            color: #ef4444;
        }
        
        .section {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .section h2 {
            margin-bottom: 20px;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        
        .position-item, .trade-item {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        
        .position-header {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .position-details {
            font-size: 0.9em;
            color: #666;
        }
        
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #667eea;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-size: 1em;
            cursor: pointer;
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            transition: all 0.3s ease;
        }
        
        .refresh-btn:hover {
            background: #764ba2;
            transform: scale(1.05);
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #10b981;
            animation: pulse 2s infinite;
            margin-right: 8px;
        }
        
        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.5;
            }
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 1.8em;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><span class="status-indicator"></span>BADSHAH TRADING BOT</h1>
            <p>Live Paper Trading Dashboard</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Capital</div>
                <div class="stat-value" id="capital">Loading...</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Portfolio Value</div>
                <div class="stat-value" id="portfolio">Loading...</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">PnL</div>
                <div class="stat-value" id="pnl">Loading...</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Trades</div>
                <div class="stat-value" id="trades">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value" id="winrate">0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Open Positions</div>
                <div class="stat-value" id="positions">0</div>
            </div>
        </div>
        
        <div class="section">
            <h2>Open Positions</h2>
            <div id="positions-list" class="loading">Loading positions...</div>
        </div>
        
        <div class="section">
            <h2>Recent Trades</h2>
            <div id="trades-list" class="loading">Loading trades...</div>
        </div>
        
        <button class="refresh-btn" onclick="loadData()">Refresh Data</button>
    </div>
    
    <script>
        function formatCurrency(value) {
            return '$' + parseFloat(value).toFixed(2).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
        }
        
        function formatPercent(value) {
            const sign = value >= 0 ? '+' : '';
            return sign + parseFloat(value).toFixed(2) + '%';
        }
        
        async function loadData() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                // Update main stats
                document.getElementById('capital').textContent = formatCurrency(data.current_capital);
                document.getElementById('portfolio').textContent = formatCurrency(data.portfolio_value);
                
                const pnlElement = document.getElementById('pnl');
                const pnlText = formatCurrency(data.pnl) + ' (' + formatPercent(data.pnl_pct) + ')';
                pnlElement.textContent = pnlText;
                pnlElement.className = 'stat-value ' + (data.pnl >= 0 ? 'positive' : 'negative');
                
                document.getElementById('trades').textContent = data.total_trades;
                document.getElementById('winrate').textContent = data.win_rate.toFixed(1) + '%';
                document.getElementById('positions').textContent = data.positions.length;
                
                // Update positions list
                const positionsList = document.getElementById('positions-list');
                if (data.positions.length === 0) {
                    positionsList.innerHTML = '<p class="loading">No open positions</p>';
                } else {
                    positionsList.innerHTML = data.positions.map(pos => `
                        <div class="position-item">
                            <div class="position-header">
                                <span>${pos.symbol}</span>
                                <span class="${pos.pnl_pct >= 0 ? 'positive' : 'negative'}">${formatPercent(pos.pnl_pct)}</span>
                            </div>
                            <div class="position-details">
                                Quantity: ${pos.quantity} | Entry: ${formatCurrency(pos.avg_price)} | Current: ${formatCurrency(pos.current_price)} | Value: ${formatCurrency(pos.value)}
                            </div>
                        </div>
                    `).join('');
                }
                
                // Update recent trades
                const tradesList = document.getElementById('trades-list');
                if (data.recent_trades.length === 0) {
                    tradesList.innerHTML = '<p class="loading">No recent trades</p>';
                } else {
                    tradesList.innerHTML = data.recent_trades.slice(0, 10).map(trade => `
                        <div class="trade-item">
                            <div class="position-header">
                                <span><strong>${trade.side}</strong> ${trade.symbol}</span>
                                <span>${trade.time}</span>
                            </div>
                            <div class="position-details">
                                Quantity: ${trade.quantity} | Price: ${formatCurrency(trade.price)} | Total: ${formatCurrency(trade.total)}
                            </div>
                        </div>
                    `).join('');
                }
                
            } catch (error) {
                console.error('Error loading data:', error);
            }
        }
        
        // Load data on page load
        loadData();
        
        // Auto-refresh every 30 seconds
        setInterval(loadData, 30000);
    </script>
</body>
</html>
    """
    return html

def run_flask():
    """Run Flask in a separate thread"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  BADSHAH TRADING BOT - MULTI-COIN LIVE PAPER TRADING")
    print("="*70)
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Start Flask server in background thread
    logger.info("Starting web server for health checks...")
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("[OK] Web server started")
    
    # Load symbols from config
    symbols = load_symbols_from_config()
    logger.info(f"Loaded {len(symbols)} coins from config: {', '.join(symbols)}")
    
    print(f"\n[INFO] Trading {len(symbols)} coins: {', '.join(symbols)}")
    print("[INFO] Press Ctrl+C to stop at any time")
    
    # Start trading
    trader = MultiCoinTrading(API_KEY, SECRET_KEY, initial_capital=10000)
    
    # Test connection (optional - don't exit on failure for cloud deployment)
    logger.info("Testing API connection...")
    test_price = trader.get_current_price('BTCUSDT')
    if test_price:
        logger.info(f"[OK] API connection OK (BTC: ${test_price:.2f})")
    else:
        logger.warning("[WARNING] Initial API test failed - will retry during trading cycles")
        logger.warning("[INFO] Flask server is running - bot is alive!")
    
    # Run trading continuously (for cloud deployment)
    try:
        while True:
            logger.info("Starting new trading cycle...")
            success = trader.start_trading(symbols, cycles=10)
            
            if success:
                logger.info("[OK] Trading cycle completed. Restarting in 60 seconds...")
            else:
                logger.warning("[WARNING] Trading cycle ended early. Restarting in 60 seconds...")
            
            time.sleep(60)  # Wait 60 seconds before next cycle
    except KeyboardInterrupt:
        logger.info("\n[STOP] Trading stopped by user")
        print("\n[OK] TRADING BOT STOPPED!")

