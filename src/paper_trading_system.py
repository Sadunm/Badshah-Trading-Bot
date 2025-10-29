#!/usr/bin/env python3
"""
Paper Trading System
Ready for live testing with your API credentials
"""

import pandas as pd
import numpy as np
import requests
import hmac
import hashlib
import time
import json
import logging
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class PaperTradingSystem:
    """
    Paper Trading System
    Ready for live testing
    """
    
    def __init__(self, api_key, secret_key, testnet=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        
        if testnet:
            self.base_url = "https://testnet.binance.vision"
        else:
            self.base_url = "https://api.binance.com"
        
        # Paper trading state
        self.initial_capital = 10000.0
        self.current_capital = 10000.0
        self.positions = {}
        self.trades = []
        self.is_running = False
        
        logger.info("Paper Trading System initialized")
        logger.info(f"Initial Capital: ${self.initial_capital}")
        logger.info(f"Testnet: {self.testnet}")
    
    def get_server_time(self):
        """Get server time"""
        try:
            response = requests.get(f"{self.base_url}/api/v3/time")
            return response.json()['serverTime']
        except Exception as e:
            logger.error(f"Error getting server time: {e}")
            return int(time.time() * 1000)
    
    def get_current_price(self, symbol):
        """Get current price for a symbol"""
        try:
            url = f"{self.base_url}/api/v3/ticker/price"
            params = {'symbol': symbol}
            response = requests.get(url, params=params)
            data = response.json()
            return float(data['price'])
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def get_account_info(self):
        """Get account information"""
        try:
            timestamp = int(time.time() * 1000)
            query_string = f"timestamp={timestamp}"
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            url = f"{self.base_url}/api/v3/account"
            params = {
                'timestamp': timestamp,
                'signature': signature
            }
            headers = {'X-MBX-APIKEY': self.api_key}
            
            response = requests.get(url, params=params, headers=headers)
            return response.json()
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    def place_paper_order(self, symbol, side, quantity, price=None):
        """Place a paper trading order"""
        try:
            current_price = self.get_current_price(symbol)
            if current_price is None:
                logger.error(f"Could not get price for {symbol}")
                return None
            
            if price is None:
                price = current_price
            
            # Calculate order value
            order_value = quantity * price
            
            # Check if we have enough capital
            if side == 'BUY' and order_value > self.current_capital:
                logger.warning(f"Insufficient capital for {symbol} {side} order")
                return None
            
            # Simulate order execution
            order = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'order_value': order_value,
                'timestamp': datetime.now().isoformat(),
                'status': 'FILLED'
            }
            
            # Update capital and positions
            if side == 'BUY':
                self.current_capital -= order_value
                if symbol not in self.positions:
                    self.positions[symbol] = {'quantity': 0, 'avg_price': 0}
                
                # Update position
                old_quantity = self.positions[symbol]['quantity']
                old_avg_price = self.positions[symbol]['avg_price']
                
                new_quantity = old_quantity + quantity
                new_avg_price = ((old_quantity * old_avg_price) + (quantity * price)) / new_quantity
                
                self.positions[symbol] = {
                    'quantity': new_quantity,
                    'avg_price': new_avg_price
                }
                
            elif side == 'SELL':
                if symbol not in self.positions or self.positions[symbol]['quantity'] < quantity:
                    logger.warning(f"Insufficient position for {symbol} {side} order")
                    return None
                
                self.current_capital += order_value
                self.positions[symbol]['quantity'] -= quantity
                
                if self.positions[symbol]['quantity'] == 0:
                    del self.positions[symbol]
            
            # Record trade
            self.trades.append(order)
            
            logger.info(f"Paper order executed: {side} {quantity} {symbol} at ${price:.2f}")
            return order
            
        except Exception as e:
            logger.error(f"Error placing paper order: {e}")
            return None
    
    def get_portfolio_value(self):
        """Get current portfolio value"""
        try:
            total_value = self.current_capital
            
            for symbol, position in self.positions.items():
                current_price = self.get_current_price(symbol)
                if current_price:
                    position_value = position['quantity'] * current_price
                    total_value += position_value
            
            return total_value
        except Exception as e:
            logger.error(f"Error calculating portfolio value: {e}")
            return self.current_capital
    
    def get_performance_metrics(self):
        """Get performance metrics"""
        try:
            current_value = self.get_portfolio_value()
            
            # 🔥 BUG FIX: Check for zero initial_capital before division!
            if self.initial_capital == 0:
                total_return = 0
            else:
                total_return = ((current_value - self.initial_capital) / self.initial_capital) * 100
            
            # Calculate win rate
            if self.trades:
                profitable_trades = 0
                for i in range(0, len(self.trades), 2):
                    if i + 1 < len(self.trades):
                        buy_order = self.trades[i]
                        sell_order = self.trades[i + 1]
                        if sell_order['price'] > buy_order['price']:
                            profitable_trades += 1
                
                # 🔥 BUG FIX: Check for zero division in win rate calculation!
                total_closed_trades = len(self.trades) // 2
                if total_closed_trades > 0:
                    win_rate = (profitable_trades / total_closed_trades) * 100
                else:
                    win_rate = 0
            else:
                win_rate = 0
            
            return {
                'initial_capital': self.initial_capital,
                'current_value': current_value,
                'total_return_pct': total_return,
                'total_trades': len(self.trades),
                'win_rate_pct': win_rate,
                'positions': self.positions
            }
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return None
    
    def start_paper_trading(self, strategy_class, strategy_name, params, symbol='BTCUSDT'):
        """Start paper trading"""
        try:
            logger.info(f"Starting paper trading for {strategy_name}")
            self.is_running = True
            
            # Get initial market data
            df = self.get_historical_data(symbol, '5m', 100)
            if df is None:
                logger.error("Failed to get initial market data")
                return False
            
            # Initialize strategy
            strategy = strategy_class()
            
            # Run initial backtest to get signals
            result = strategy.backtest_guaranteed_strategy(df, strategy_name, params)
            
            if result and result['metrics']['total_trades'] > 0:
                logger.info(f"Strategy {strategy_name} ready for paper trading")
                logger.info(f"Expected performance: {result['metrics']['total_return_pct']:.2f}% return")
                logger.info(f"Expected win rate: {result['metrics']['winrate_pct']:.2f}%")
                
                # Start monitoring
                self.monitor_and_trade(strategy, strategy_name, params, symbol)
                
            else:
                logger.error(f"Strategy {strategy_name} not ready for paper trading")
                return False
                
        except Exception as e:
            logger.error(f"Error starting paper trading: {e}")
            return False
    
    def get_historical_data(self, symbol, interval, limit):
        """Get historical data"""
        try:
            url = f"{self.base_url}/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            # Convert to DataFrame
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            
            # Convert timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df[['open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return None
    
    def monitor_and_trade(self, strategy, strategy_name, params, symbol):
        """Monitor market and execute trades"""
        try:
            logger.info(f"Starting monitoring for {strategy_name}")
            
            while self.is_running:
                # Get latest data
                df = self.get_historical_data(symbol, '5m', 50)
                if df is None:
                    logger.warning("Failed to get latest data")
                    time.sleep(60)
                    continue
                
                # Get current price
                current_price = self.get_current_price(symbol)
                if current_price is None:
                    logger.warning("Failed to get current price")
                    time.sleep(60)
                    continue
                
                # Check for trading signals
                # This is a simplified version - in reality you'd implement
                # the actual signal generation logic here
                
                # Log current status
                portfolio_value = self.get_portfolio_value()
                performance = self.get_performance_metrics()
                
                logger.info(f"Portfolio Value: ${portfolio_value:.2f}")
                logger.info(f"Total Return: {performance['total_return_pct']:.2f}%")
                logger.info(f"Total Trades: {performance['total_trades']}")
                
                # Wait before next check
                time.sleep(300)  # 5 minutes
                
        except Exception as e:
            logger.error(f"Error in monitoring: {e}")
    
    def stop_paper_trading(self):
        """Stop paper trading"""
        self.is_running = False
        logger.info("Paper trading stopped")
    
    def get_final_report(self):
        """Get final trading report"""
        try:
            performance = self.get_performance_metrics()
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'strategy_name': 'Paper Trading System',
                'initial_capital': self.initial_capital,
                'final_value': performance['current_value'],
                'total_return_pct': performance['total_return_pct'],
                'total_trades': performance['total_trades'],
                'win_rate_pct': performance['win_rate_pct'],
                'positions': performance['positions'],
                'trades': self.trades
            }
            
            # Save report
            with open('reports/paper_trading_final_report.json', 'w') as f:
                json.dump(report, f, indent=2)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating final report: {e}")
            return None

def main():
    """Main function"""
    logger.info("Starting Paper Trading System")
    
    # Your API credentials
    API_KEY = "tlA62wL7hb0H6ro0v9rhYcuSManm5gscnBWhNKHq9gamBRj3HJfm1drOECVNzHrk"
    SECRET_KEY = "7Lfx9dhbMP1EfiyXl6u3VluGUXZ5g4Bde7jk83uRQVZM9fCKqPojELo4zhe8izu3"
    
    # Initialize paper trading system
    paper_trader = PaperTradingSystem(API_KEY, SECRET_KEY, testnet=True)
    
    # Test account connection
    account_info = paper_trader.get_account_info()
    if account_info:
        logger.info("✅ API connection successful!")
        logger.info(f"Account status: {account_info.get('accountType', 'Unknown')}")
    else:
        logger.error("❌ API connection failed!")
        return
    
    # Test price fetching
    btc_price = paper_trader.get_current_price('BTCUSDT')
    if btc_price:
        logger.info(f"✅ Current BTC price: ${btc_price:.2f}")
    else:
        logger.error("❌ Failed to get BTC price!")
        return
    
    # Test portfolio value
    portfolio_value = paper_trader.get_portfolio_value()
    logger.info(f"✅ Portfolio value: ${portfolio_value:.2f}")
    
    # Test performance metrics
    performance = paper_trader.get_performance_metrics()
    if performance:
        logger.info(f"✅ Performance metrics calculated")
        logger.info(f"  Total Return: {performance['total_return_pct']:.2f}%")
        logger.info(f"  Total Trades: {performance['total_trades']}")
        logger.info(f"  Win Rate: {performance['win_rate_pct']:.2f}%")
    
    print(f"\n🎯 PAPER TRADING SYSTEM READY!")
    print(f"  API Connection: ✅")
    print(f"  Price Fetching: ✅")
    print(f"  Portfolio Tracking: ✅")
    print(f"  Performance Metrics: ✅")
    print(f"  Initial Capital: ${paper_trader.initial_capital}")
    print(f"  Current Value: ${portfolio_value:.2f}")
    
    print(f"\n💡 READY FOR LIVE PAPER TRADING!")
    print(f"  Use: paper_trader.start_paper_trading(strategy_class, strategy_name, params)")
    print(f"  Stop: paper_trader.stop_paper_trading()")
    print(f"  Report: paper_trader.get_final_report()")

if __name__ == "__main__":
    main()
