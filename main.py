#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main paper trading engine
Orchestrates the complete paper trading system
"""

import sys
import os
import json
import argparse
import logging
from datetime import datetime
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def setup_logging(log_level="INFO"):
    """Setup logging configuration"""
    # FIX: Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler('logs/paper_trading.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def load_config(config_file="config/adaptive_config.json"):
    """Load adaptive configuration"""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    # 🔥 BUG FIX: Handle malformed JSON with try-except!
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON in {config_file}: {e}")

def initialize_system(config):
    """Initialize the trading system"""
    logger = logging.getLogger(__name__)
    logger.info("Initializing paper trading system...")
    
    # Check safety mode
    if config.get('safety_mode', True):
        logger.info("SAFETY MODE ENABLED - Conservative settings active")
    
    # Log configuration
    # FIX: Added safety checks for nested dictionaries
    try:
        trading_settings = config['system_config']['trading_settings']
        logger.info(f"Risk per trade: {trading_settings.get('risk_per_trade_pct', 0.01)*100:.1f}%")
        logger.info(f"Max exposure: {trading_settings.get('max_exposure_pct', 0.1)*100:.1f}%")
        logger.info(f"Daily stop loss: {trading_settings.get('daily_stop_loss_pct', 0.05)*100:.1f}%")
    except KeyError as e:
        logger.warning(f"Configuration key missing: {e}, using defaults")
    
    # Log selected strategies
    candidates = config['strategies']
    logger.info(f"Selected {len(candidates)} strategies:")
    for candidate in candidates:
        logger.info(f"  - {candidate['symbol']}: {candidate['strategy_type']}")
    
    return True

def run_paper_trading(config, track_performance=True):
    """Run paper trading simulation"""
    logger = logging.getLogger(__name__)
    logger.info("Starting paper trading simulation...")
    
    # Import trading components
    try:
        from ultimate_backtester import UltimateBacktester
        import pandas as pd
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False
    
    # Initialize backtester
    # 🔥 BUG FIX: Safe nested dict access with get() and defaults!
    trading_settings = config.get('system_config', {}).get('trading_settings', {})
    fee_rate = trading_settings.get('fee_rate', 0.0005)
    slippage_rate = trading_settings.get('slippage_rate', 0.0002)
    initial_capital = trading_settings.get('initial_capital', 10000)
    
    backtester = UltimateBacktester(
        fee_rate=fee_rate,
        slippage_rate=slippage_rate
    )
    
    # Process each selected strategy
    results = []
    
    for candidate in config['strategies']:
        symbol = candidate['symbol']
        strategy_type = candidate['strategy_type']
        params = candidate['params']
        
        logger.info(f"Processing {symbol} with {strategy_type}")
        
        try:
            # Load data
            data_file = f"data/processed/{symbol}_5m.parquet"
            if not os.path.exists(data_file):
                logger.warning(f"Data file not found: {data_file}")
                # Try user_data folder
                data_file = f"user_data/{symbol}_5m.parquet"
                if not os.path.exists(data_file):
                    logger.warning(f"Data file not found in user_data either: {data_file}")
                    continue
            
            df = pd.read_parquet(data_file)
            
            # Fix column names if needed
            if len(df.columns) == 6 and all(isinstance(col, str) and col.isdigit() for col in df.columns):
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                if df['timestamp'].dtype in ['int64', 'float64']:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.set_index('timestamp')
            else:
                # If columns are not numeric strings, try to rename by position
                if len(df.columns) >= 5:
                    df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]
                    if 'timestamp' in df.columns:
                        if df['timestamp'].dtype in ['int64', 'float64']:
                            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                        df = df.set_index('timestamp')
            
            # Debug: Print column names
            logger.info(f"Data columns after processing: {list(df.columns)}")
            
            # Ensure we have the required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.error(f"Missing required columns: {missing_cols}")
                continue
            
            # Run backtest
            result = backtester.backtest_ultimate_strategy(df, strategy_type, params, initial_capital)
            
            # Store results
            results.append({
                'symbol': symbol,
                'strategy_type': strategy_type,
                'params': params,
                'metrics': result['metrics'],
                'total_trades': result['metrics']['total_trades'],
                'total_return_pct': result['metrics']['total_return_pct'],
                'winrate_pct': result['metrics']['winrate_pct'],
                'sharpe': result['metrics']['sharpe']
            })
            
            logger.info(f"{symbol} completed: {result['metrics']['total_trades']} trades, "
                       f"{result['metrics']['total_return_pct']:.2f}% return")
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            continue
    
    # Save results
    if track_performance:
        # FIX: Create reports directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        performance_report = {
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'session_type': 'paper_trading',
            'config_used': config,
            'results': results,
            'summary': {
                'total_strategies': len(results),
                'successful_strategies': len([r for r in results if r['total_trades'] > 0]),
                'avg_return': sum(r['total_return_pct'] for r in results) / len(results) if results else 0,
                'total_trades': sum(r['total_trades'] for r in results)
            }
        }
        
        with open('reports/paper_trading_results.json', 'w', encoding='utf-8') as f:
            json.dump(performance_report, f, indent=2, default=str)
        
        logger.info("Performance results saved to reports/paper_trading_results.json")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Paper Trading System')
    parser.add_argument('--mode', choices=['paper', 'live'], default='paper',
                       help='Trading mode')
    # FIX: Updated default config path to match load_config()
    parser.add_argument('--config', default='config/adaptive_config.json',
                       help='Configuration file')
    parser.add_argument('--log-level', default='info',
                       help='Logging level')
    parser.add_argument('--track-performance', action='store_true',
                       help='Track and save performance metrics')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.log_level)
    logger.info("=== Paper Trading System Started ===")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Config: {args.config}")
    
    try:
        # Load configuration
        config = load_config(args.config)
        logger.info("Configuration loaded successfully")
        
        # Initialize system
        if not initialize_system(config):
            logger.error("System initialization failed")
            sys.exit(1)
        
        # Check if auto-start is enabled
        if not config['system_config'].get('auto_start_paper', False):
            logger.warning("Auto-start is DISABLED in configuration")
            logger.info("To enable auto-start, set 'auto_start_paper': true in adaptive_config.json")
            logger.info("Manual start required - system ready but not running")
            return
        
        # Run paper trading
        if args.mode == 'paper':
            success = run_paper_trading(config, args.track_performance)
            if success:
                logger.info("Paper trading completed successfully")
            else:
                logger.error("Paper trading failed")
                sys.exit(1)
        else:
            logger.error("Live trading not implemented - use paper mode only")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"System error: {e}")
        sys.exit(1)
    
    logger.info("=== Paper Trading System Completed ===")

if __name__ == "__main__":
    main()
