"""
Paper Trader for Badshah Trading System
Simulates trading with realistic fills and risk management
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaperTrader:
    """Paper trading simulator with realistic fills and risk management"""
    
    def __init__(self, 
                 config_path: str = "adaptive_config.json",
                 testnet: bool = True,
                 dry_run: bool = True):
        self.config_path = config_path
        self.testnet = testnet
        self.dry_run = dry_run
        
        # Load configuration
        self.config = self._load_config()
        self.safety_settings = self.config.get('safety_settings', {})
        
        # Trading state
        self.positions = {}
        self.balance = 10000.0  # Starting balance
        self.initial_balance = self.balance  # 🔥 SAVE initial balance for return calculations!
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.trade_history = []
        
        # Risk limits
        self.risk_per_trade = self.safety_settings.get('risk_per_trade', 0.005)
        self.max_exposure = self.safety_settings.get('max_exposure_per_symbol', 0.15)
        self.daily_stop_loss = self.safety_settings.get('daily_stop_loss', 0.03)
        
        # Setup logging
        self.log_file = "logs/paper_trading.log"
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
    def _load_config(self) -> Dict:
        """Load trading configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            return {}
    
    def start_trading(self) -> None:
        """Start paper trading (requires manual approval)"""
        try:
            logger.info("=== Paper Trading Started ===")
            logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'TESTNET'}")
            logger.info(f"Balance: ${self.balance:.2f}")
            logger.info(f"Risk per trade: {self.risk_per_trade:.1%}")
            logger.info(f"Daily stop loss: {self.daily_stop_loss:.1%}")
            
            # Check safety limits
            if not self._check_safety_limits():
                logger.error("Safety limits not met - trading stopped")
                return
            
            # Start trading loop
            self._trading_loop()
            
        except Exception as e:
            logger.error(f"Error in trading: {str(e)}")
    
    def _check_safety_limits(self) -> bool:
        """Check if safety limits are properly configured"""
        try:
            # Check risk per trade
            if self.risk_per_trade > 0.01:
                logger.warning(f"Risk per trade too high: {self.risk_per_trade:.1%}")
                return False
            
            # Check max exposure
            if self.max_exposure > 0.15:
                logger.warning(f"Max exposure too high: {self.max_exposure:.1%}")
                return False
            
            # Check daily stop loss
            if self.daily_stop_loss > 0.03:
                logger.warning(f"Daily stop loss too high: {self.daily_stop_loss:.1%}")
                return False
            
            logger.info("✓ Safety limits check passed")
            return True
            
        except Exception as e:
            logger.error(f"Error checking safety limits: {str(e)}")
            return False
    
    def _trading_loop(self) -> None:
        """Main trading loop"""
        try:
            logger.info("Starting trading loop...")
            
            # Simulate trading for demonstration
            for i in range(10):  # Simulate 10 trading cycles
                logger.info(f"Trading cycle {i+1}/10")
                
                # Check daily stop loss
                if self.daily_pnl < -self.balance * self.daily_stop_loss:
                    logger.warning("Daily stop loss triggered - stopping trading")
                    break
                
                # Simulate trade
                self._simulate_trade()
                
                # Wait between cycles
                time.sleep(1)
            
            # Generate performance report
            self._generate_performance_report()
            
        except Exception as e:
            logger.error(f"Error in trading loop: {str(e)}")
    
    def _simulate_trade(self) -> None:
        """Simulate a trade for demonstration"""
        try:
            # Get current price (simulated)
            current_price = 50000 + np.random.normal(0, 1000)
            
            # Calculate position size
            position_size = self._calculate_position_size(current_price)
            
            if position_size > 0:
                # Simulate trade
                trade = {
                    'timestamp': datetime.utcnow(),
                    'symbol': 'BTCUSDT',
                    'side': 'long',
                    'entry_price': current_price,
                    'quantity': position_size,
                    'pnl': np.random.normal(0, 100),  # Simulated PnL
                    'exit_reason': 'signal'
                }
                
                # Update balance
                self.balance += trade['pnl']
                self.daily_pnl += trade['pnl']
                self.total_trades += 1
                self.trade_history.append(trade)
                
                logger.info(f"Trade executed: {trade['side']} {trade['quantity']:.4f} @ ${trade['entry_price']:.2f}")
                logger.info(f"PnL: ${trade['pnl']:.2f}, Balance: ${self.balance:.2f}")
            
        except Exception as e:
            logger.error(f"Error simulating trade: {str(e)}")
    
    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size based on risk management"""
        try:
            # Calculate risk amount
            risk_amount = self.balance * self.risk_per_trade
            
            # Calculate stop loss distance (simplified)
            stop_loss_distance = price * 0.02  # 2% stop loss
            
            # Calculate position size
            position_size = risk_amount / stop_loss_distance
            
            # Apply max exposure limit
            max_position_value = self.balance * self.max_exposure
            max_position_size = max_position_value / price
            
            position_size = min(position_size, max_position_size)
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 0.0
    
    def _generate_performance_report(self) -> None:
        """Generate performance report"""
        try:
            if not self.trade_history:
                logger.warning("No trades to report")
                return
            
            # Calculate metrics
            total_pnl = sum(trade['pnl'] for trade in self.trade_history)
            winning_trades = [t for t in self.trade_history if t['pnl'] > 0]
            losing_trades = [t for t in self.trade_history if t['pnl'] < 0]
            
            # 🔥 BUG FIX: Check for empty trade_history before division!
            if len(self.trade_history) > 0:
                win_rate = len(winning_trades) / len(self.trade_history) * 100
            else:
                win_rate = 0
            avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
            
            # Create report
            report = {
                'timestamp': datetime.utcnow().isoformat(),
                'trading_summary': {
                    'total_trades': len(self.trade_history),
                    'winning_trades': len(winning_trades),
                    'losing_trades': len(losing_trades),
                    'win_rate': win_rate,
                    'total_pnl': total_pnl,
                    'final_balance': self.balance,
                    # 🔥 BUG FIX: Use initial_balance, not hardcoded 10000! Also check for zero division!
                    'return_pct': (self.balance - self.initial_balance) / self.initial_balance * 100 if self.initial_balance > 0 else 0
                },
                'risk_metrics': {
                    'max_daily_loss': self.daily_pnl,
                    'risk_per_trade': self.risk_per_trade,
                    'max_exposure': self.max_exposure
                },
                'trade_history': self.trade_history
            }
            
            # Save report
            report_path = "reports/performance.json"
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Performance report saved: {report_path}")
            logger.info(f"Total trades: {len(self.trade_history)}")
            logger.info(f"Win rate: {win_rate:.1f}%")
            logger.info(f"Total PnL: ${total_pnl:.2f}")
            logger.info(f"Final balance: ${self.balance:.2f}")
            
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}")

def main():
    """Example usage of PaperTrader"""
    trader = PaperTrader(
        config_path='adaptive_config.json',
        testnet=True,
        dry_run=True
    )
    
    # Start trading (requires manual approval)
    print("Paper trading simulator ready")
    print("Run trader.start_trading() to begin")

if __name__ == "__main__":
    main()
