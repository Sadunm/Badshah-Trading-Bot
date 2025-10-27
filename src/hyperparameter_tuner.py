#!/usr/bin/env python3
"""
Hyperparameter Tuner - Advanced hyperparameter optimization
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import logging
import time
from sklearn.model_selection import ParameterGrid
from sklearn.metrics import make_scorer
import random

logger = logging.getLogger(__name__)

class HyperparameterTuner:
    """Advanced hyperparameter tuning system"""
    
    def __init__(self):
        self.tuning_history = []
        self.best_hyperparameters = {}
        self.performance_tracking = {}
        
    def get_hyperparameter_grid(self):
        """Get comprehensive hyperparameter grid"""
        return {
            'Simple_Momentum': {
                'ema_short': [5, 8, 12, 15, 18, 21],
                'ema_long': [20, 25, 30, 35, 40, 50],
                'macd_fast': [8, 10, 12, 15, 18],
                'macd_slow': [20, 25, 30, 35, 40],
                'rsi_period': [10, 14, 18, 21, 25],
                'volume_mult': [1.2, 1.5, 2.0, 2.5, 3.0],
                'momentum_threshold': [0.0005, 0.001, 0.002, 0.003, 0.005],
                'volatility_filter': [0.8, 1.0, 1.2, 1.5],
                'trend_strength': [0.5, 1.0, 1.5, 2.0]
            },
            'Simple_MeanReversion': {
                'rsi_period': [10, 14, 18, 21, 25, 30],
                'rsi_oversold': [20, 25, 30, 35, 40],
                'rsi_overbought': [60, 65, 70, 75, 80],
                'bb_period': [15, 20, 25, 30, 35],
                'bb_std': [1.5, 2.0, 2.5, 3.0, 3.5],
                'stoch_k': [10, 14, 18, 21],
                'stoch_d': [3, 5, 7, 10],
                'volume_threshold': [0.8, 1.0, 1.2, 1.5],
                'momentum_filter': [0.0005, 0.001, 0.002, 0.005],
                'reversion_strength': [0.5, 1.0, 1.5, 2.0]
            },
            'Simple_Breakout': {
                'lookback': [15, 20, 25, 30, 35, 40],
                'vol_mult': [1.2, 1.5, 2.0, 2.5, 3.0, 4.0],
                'atr_mult': [0.3, 0.5, 0.7, 1.0, 1.5],
                'momentum_threshold': [0.0005, 0.001, 0.002, 0.003, 0.005],
                'volatility_threshold': [0.8, 1.0, 1.2, 1.5, 2.0],
                'price_threshold': [0.001, 0.002, 0.005, 0.01],
                'volume_confirmation': [1.2, 1.5, 2.0, 2.5],
                'breakout_strength': [0.5, 1.0, 1.5, 2.0],
                'trend_confirmation': [0.5, 1.0, 1.5, 2.0]
            }
        }
    
    def calculate_hyperparameter_score(self, metrics):
        """Calculate hyperparameter optimization score"""
        # Advanced scoring with multiple factors
        weights = {
            'winrate_pct': 0.20,
            'total_return_pct': 0.15,
            'sharpe': 0.15,
            'max_drawdown_pct': 0.15,
            'total_trades': 0.10,
            'avg_trade_pnl': 0.10,
            'profit_factor': 0.10,
            'consistency': 0.05
        }
        
        # Calculate profit factor
        total_trades = metrics.get('total_trades', 0)
        winrate = metrics.get('winrate_pct', 0)
        avg_pnl = metrics.get('avg_trade_pnl', 0)
        
        if total_trades > 0:
            winning_trades = total_trades * winrate / 100
            losing_trades = total_trades - winning_trades
            
            if losing_trades > 0:
                profit_factor = (winning_trades * avg_pnl) / (losing_trades * abs(avg_pnl))
            else:
                profit_factor = 2.0
        else:
            profit_factor = 0
        
        # Calculate consistency (lower volatility is better)
        returns = [metrics.get('avg_trade_pnl', 0)] * total_trades if total_trades > 0 else [0]
        consistency = 1.0 / (1.0 + np.std(returns)) if len(returns) > 1 else 0
        
        # Normalize metrics
        winrate_score = min(winrate / 80, 1.0)  # Cap at 80%
        return_score = max(min(metrics.get('total_return_pct', 0) / 100, 1.0), -1.0)  # Cap at ±100%
        sharpe_score = max(min(metrics.get('sharpe', 0) / 10, 1.0), -1.0)  # Cap at ±10
        drawdown_score = max(1 + metrics.get('max_drawdown_pct', 0) / 50, 0.0)  # Penalty for drawdown
        trades_score = min(total_trades / 200, 1.0)  # Prefer more trades
        pnl_score = max(min(avg_pnl / 10, 1.0), -1.0)  # Cap at ±10%
        profit_factor_score = min(profit_factor / 5, 1.0)  # Cap at 5
        consistency_score = min(consistency * 10, 1.0)  # Cap at 1
        
        # Calculate weighted score
        total_score = (
            weights['winrate_pct'] * winrate_score +
            weights['total_return_pct'] * return_score +
            weights['sharpe'] * sharpe_score +
            weights['max_drawdown_pct'] * drawdown_score +
            weights['total_trades'] * trades_score +
            weights['avg_trade_pnl'] * pnl_score +
            weights['profit_factor'] * profit_factor_score +
            weights['consistency'] * consistency_score
        )
        
        return total_score
    
    def run_hyperparameter_tuning(self, backtester, max_iterations=1000):
        """Run hyperparameter tuning until no improvement"""
        logger.info("Starting hyperparameter tuning")
        
        hyperparameter_grid = self.get_hyperparameter_grid()
        best_scores = {}
        no_improvement_count = {}
        max_no_improvement = 100
        
        iteration = 0
        start_time = time.time()
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Hyperparameter tuning iteration {iteration}")
            
            # Generate new market data
            from realistic_market_generator import RealisticMarketGenerator
            generator = RealisticMarketGenerator()
            market_conditions = ['trending', 'ranging', 'volatile', 'calm', 'mixed']
            market_condition = random.choice(market_conditions)
            
            if market_condition == 'trending':
                df = generator.generate_trending_market(1000)
            elif market_condition == 'ranging':
                df = generator.generate_ranging_market(1000)
            elif market_condition == 'volatile':
                df = generator.generate_volatile_market(1000)
            elif market_condition == 'calm':
                df = generator.generate_calm_market(1000)
            else:
                df = generator.generate_mixed_market(1000)
            
            # Tune each strategy
            for strategy_type in ['Simple_Momentum', 'Simple_MeanReversion', 'Simple_Breakout']:
                if strategy_type not in best_scores:
                    best_scores[strategy_type] = -float('inf')
                    no_improvement_count[strategy_type] = 0
                
                # Get parameter grid for this strategy
                param_grid = hyperparameter_grid[strategy_type]
                
                # Sample random parameters
                params = {}
                for param, values in param_grid.items():
                    params[param] = random.choice(values)
                
                # Test parameters
                try:
                    result = backtester.backtest_ultimate_strategy(df, strategy_type, params)
                    score = self.calculate_hyperparameter_score(result['metrics'])
                    
                    # Check for improvement
                    if score > best_scores[strategy_type]:
                        best_scores[strategy_type] = score
                        no_improvement_count[strategy_type] = 0
                        
                        # Store best parameters
                        self.best_hyperparameters[strategy_type] = {
                            'params': params,
                            'score': score,
                            'metrics': result['metrics'],
                            'market_condition': market_condition
                        }
                        
                        logger.info(f"{strategy_type} new best score: {score:.4f}")
                    else:
                        no_improvement_count[strategy_type] += 1
                    
                    # Track performance
                    self.performance_tracking[f"{strategy_type}_{iteration}"] = {
                        'score': score,
                        'params': params,
                        'market_condition': market_condition,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                except Exception as e:
                    logger.error(f"Error tuning {strategy_type}: {e}")
                    continue
            
            # Check if all strategies have plateaued
            all_plateaued = all(count >= max_no_improvement for count in no_improvement_count.values())
            
            if all_plateaued:
                logger.info("All strategies have plateaued - stopping optimization")
                break
            
            # Save progress every 50 iterations
            if iteration % 50 == 0:
                self.save_tuning_progress()
                elapsed_time = time.time() - start_time
                logger.info(f"Progress saved after {iteration} iterations ({elapsed_time:.2f}s)")
        
        # Final save
        self.save_tuning_progress()
        
        logger.info("Hyperparameter tuning completed")
        return self.best_hyperparameters
    
    def save_tuning_progress(self):
        """Save tuning progress"""
        progress = {
            'timestamp': datetime.now().isoformat(),
            'best_hyperparameters': self.best_hyperparameters,
            'performance_tracking': self.performance_tracking,
            'tuning_history': self.tuning_history
        }
        
        with open('reports/hyperparameter_tuning_progress.json', 'w') as f:
            json.dump(progress, f, indent=2)
        
        logger.info("Tuning progress saved")

def main():
    """Test the hyperparameter tuner"""
    logger.info("Testing hyperparameter tuner")
    
    from ultimate_backtester import UltimateBacktester
    
    # Test tuner
    backtester = UltimateBacktester()
    tuner = HyperparameterTuner()
    
    # Run tuning
    best_params = tuner.run_hyperparameter_tuning(backtester, max_iterations=100)
    
    print("Hyperparameter tuning completed!")
    for strategy, params in best_params.items():
        print(f"{strategy}: Score = {params['score']:.4f}")

if __name__ == "__main__":
    main()
