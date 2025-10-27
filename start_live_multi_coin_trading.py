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
        self.positions = {}  # {symbol: {'quantity': X, 'avg_price': Y}}
        self.trades = []
        self.is_running = True
        
        # Trading costs
        self.fee_rate = 0.0005  # 0.05%
        self.slippage_rate = 0.0002  # 0.02%
        
        logger.info(f"Multi-Coin Trading initialized with ${initial_capital:.2f}")
        
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
    
    def calculate_position_size(self, price, symbol):
        """Calculate appropriate position size based on capital and price"""
        # Use 1% of capital per trade
        risk_amount = self.current_capital * 0.01
        
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
                    self.positions[symbol] = {'quantity': 0, 'avg_price': 0}
                
                # Update position
                old_qty = self.positions[symbol]['quantity']
                old_price = self.positions[symbol]['avg_price']
                new_qty = old_qty + quantity
                new_avg_price = ((old_qty * old_price) + (quantity * exec_price)) / new_qty if new_qty > 0 else exec_price
                
                self.positions[symbol] = {
                    'quantity': new_qty,
                    'avg_price': new_avg_price
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
    
    def start_trading(self, symbols, cycles=10):
        """Start multi-coin trading"""
        logger.info(f"[START] Trading for {len(symbols)} coins: {', '.join(symbols)}")
        
        try:
            for cycle in range(1, cycles + 1):
                logger.info(f"\n{'='*70}")
                logger.info(f"CYCLE {cycle}/{cycles}")
                logger.info(f"{'='*70}")
                
                # Get current prices for all symbols
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
                    time.sleep(30)
                    continue
                
                # Simple trading logic
                for symbol in prices:
                    price = prices[symbol]
                    
                    # Buy on first cycle if we don't have position
                    if cycle == 1 and symbol not in self.positions:
                        self.place_order(symbol, 'BUY', price)
                    
                    # Sell on 5th cycle if we have position
                    elif cycle == 5 and symbol in self.positions:
                        self.place_order(symbol, 'SELL', price)
                    
                    # Buy again on 7th cycle
                    elif cycle == 7 and symbol not in self.positions:
                        self.place_order(symbol, 'BUY', price)
                
                # Print status
                logger.info("")
                self.print_status(prices)
                
                # Wait before next cycle
                if cycle < cycles:
                    logger.info(f"\n[WAIT] Waiting 30 seconds...\n")
                    time.sleep(30)
            
            # Final summary
            logger.info(f"\n{'='*70}")
            logger.info("[SUMMARY] FINAL SUMMARY")
            logger.info(f"{'='*70}")
            
            final_prices = {s: self.get_current_price(s) for s in symbols}
            self.print_status(final_prices)
            
            # Close all positions
            logger.info("\n[CLOSING] Closing all positions...")
            for symbol in list(self.positions.keys()):
                price = final_prices.get(symbol)
                if price:
                    self.place_order(symbol, 'SELL', price)
            
            # Final stats
            final_value = self.current_capital
            total_pnl = final_value - self.initial_capital
            total_pnl_pct = (total_pnl / self.initial_capital) * 100
            
            logger.info(f"\n{'='*70}")
            logger.info("[COMPLETE] TRADING COMPLETE!")
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
    
    # Test connection
    logger.info("Testing API connection...")
    test_price = trader.get_current_price('BTCUSDT')
    if test_price:
        logger.info(f"[OK] API connection OK (BTC: ${test_price:.2f})")
    else:
        logger.error("[ERROR] API connection failed!")
        sys.exit(1)
    
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

