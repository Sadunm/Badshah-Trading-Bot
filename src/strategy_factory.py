#!/usr/bin/env python3
"""
Strategy Factory
Creates strategy candidates from templates and performs lightweight simulation
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import logging
from itertools import product

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_templates(templates_file="src/templates.json"):
    """Load strategy templates"""
    with open(templates_file, 'r') as f:
        return json.load(f)

def generate_strategy_candidates(templates, symbols, regimes):
    """
    Generate strategy candidates from templates
    
    Args:
        templates (dict): Strategy templates
        symbols (list): List of symbols
        regimes (list): List of regimes
        
    Returns:
        list: List of strategy candidates
    """
    candidates = []
    candidate_id = 0
    
    for symbol in symbols:
        for regime in regimes:
            for strategy_type, params in templates.items():
                # Generate parameter combinations
                param_names = list(params.keys())
                param_values = list(params.values())
                
                for param_combo in product(*param_values):
                    # Create parameter dictionary
                    param_dict = dict(zip(param_names, param_combo))
                    
                    # Determine required timeframe based on strategy type
                    if strategy_type in ['Pullback', 'MeanReversion']:
                        required_tf = '5m'
                    elif strategy_type == 'Breakout':
                        required_tf = '15m'
                    else:  # Momentum
                        required_tf = '1h'
                    
                    candidate = {
                        "id": candidate_id,
                        "symbol": symbol,
                        "regime": regime,
                        "strategy_type": strategy_type,
                        "template": strategy_type,
                        "params": param_dict,
                        "required_tf": required_tf,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    }
                    
                    candidates.append(candidate)
                    candidate_id += 1
    
    # 🔥 BUG FIX: Return should be OUTSIDE all loops, not inside!
    # Was returning after processing just 1 symbol & 1 regime!
    return candidates
            
def lightweight_simulation(df, strategy_type, params):
    """
    Perform lightweight simulation to estimate trade count
    
    Args:
        df (pd.DataFrame): Price data
        strategy_type (str): Type of strategy
        params (dict): Strategy parameters
        
    Returns:
        dict: Simulation results
    """
    try:
        # Calculate basic indicators
        df = df.copy()
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(20).std()
        
        # Simple signal generation based on strategy type
        if strategy_type == 'Pullback':
            # RSI-based pullback
            rsi_period = 14
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # Entry signals
            entry_signals = (rsi < params['rsi_entry']) & (df['volume'] > df['volume'].rolling(20).mean() * params['volume_ratio'])
            trade_count = entry_signals.sum()
            
        elif strategy_type == 'Breakout':
            # Volume breakout
            lookback = params['lookback']
            vol_threshold = df['volume'].rolling(lookback).mean() * params['vol_mult']
            price_breakout = df['close'] > df['close'].rolling(lookback).max().shift(1)
            
            entry_signals = (df['volume'] > vol_threshold) & price_breakout
            trade_count = entry_signals.sum()
            
        elif strategy_type == 'MeanReversion':
            # RSI mean reversion
            rsi_period = 14
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            entry_signals = rsi < params['rsi_buy']
            trade_count = entry_signals.sum()
            
        elif strategy_type == 'Momentum':
            # EMA crossover
            ema_short = df['close'].ewm(span=params['ema_short']).mean()
            ema_long = df['close'].ewm(span=params['ema_long']).mean()
            
            entry_signals = (ema_short > ema_long) & (ema_short.shift(1) <= ema_long.shift(1))
            trade_count = entry_signals.sum()
            
        else:
            trade_count = 0
            
            return {
            "trade_count": trade_count,
            "sufficient": trade_count >= 50,
            "data_points": len(df)
            }
            
        except Exception as e:
        logger.warning(f"Lightweight simulation failed: {e}")
        return {
            "trade_count": 0,
            "sufficient": False,
            "data_points": len(df) if df is not None else 0,
            "error": str(e)
        }

def filter_candidates(candidates, data_dir="data/processed"):
    """
    Filter candidates based on lightweight simulation
    
    Args:
        candidates (list): List of strategy candidates
        data_dir (str): Processed data directory
        
    Returns:
        list: Filtered candidates
    """
    filtered_candidates = []
    
    for candidate in candidates:
        symbol = candidate['symbol']
        required_tf = candidate['required_tf']
        
        # Find data file
        data_file = os.path.join(data_dir, f"{symbol}_{required_tf}.parquet")
        if not os.path.exists(data_file):
            logger.warning(f"Data file not found: {data_file}")
            continue
        
        try:
            # Load data
            df = pd.read_parquet(data_file)
            
            # Fix column names if needed
            if len(df.columns) == 6 and all(isinstance(col, str) and col.isdigit() for col in df.columns):
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.set_index('timestamp')
            
            # Perform lightweight simulation
            sim_result = lightweight_simulation(df, candidate['strategy_type'], candidate['params'])
            
            if sim_result['sufficient']:
                candidate['simulation_result'] = sim_result
                filtered_candidates.append(candidate)
                logger.info(f"Candidate {candidate['id']} passed simulation: {sim_result['trade_count']} trades")
            else:
                logger.info(f"Candidate {candidate['id']} insufficient: {sim_result['trade_count']} trades")
            
        except Exception as e:
            logger.error(f"Error processing candidate {candidate['id']}: {e}")
            continue
    
    return filtered_candidates

def main():
    """Main strategy factory function"""
    logger.info("Starting strategy factory")
    
    # Load templates
    templates = load_templates()
    logger.info(f"Loaded {len(templates)} strategy templates")
    
    # Define symbols and regimes
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    regimes = [0, 1, 2]  # Based on regime detection results
    
    # Generate candidates
    candidates = generate_strategy_candidates(templates, symbols, regimes)
    logger.info(f"Generated {len(candidates)} strategy candidates")
    
    # Filter candidates
    filtered_candidates = filter_candidates(candidates)
    logger.info(f"Filtered to {len(filtered_candidates)} viable candidates")
    
    # Save results
    results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_candidates": len(candidates),
        "viable_candidates": len(filtered_candidates),
        "candidates": filtered_candidates
    }
    
    with open("reports/candidates_raw.json", 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info("Strategy factory completed")
    return results

if __name__ == "__main__":
    main()