#!/usr/bin/env python3
"""
Strategy Selector - Focus on best performing strategies
"""

import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class StrategySelector:
    """Strategy selection system for focusing on best performers"""
    
    def __init__(self):
        self.performance_history = {}
        self.strategy_rankings = {}
        
    def evaluate_strategy_performance(self, strategy_results):
        """Evaluate strategy performance and rank them"""
        rankings = []
        
        for strategy in strategy_results:
            metrics = strategy.get('metrics', {})
            
            # Calculate performance score
            score = self.calculate_performance_score(metrics)
            
            rankings.append({
                'strategy_type': strategy.get('strategy_type'),
                'symbol': strategy.get('symbol'),
                'score': score,
                'metrics': metrics,
                'params': strategy.get('params', {})
            })
        
        # Sort by score (descending)
        rankings.sort(key=lambda x: x['score'], reverse=True)
        
        return rankings
    
    def calculate_performance_score(self, metrics):
        """Calculate comprehensive performance score"""
        # Weighted scoring system
        weights = {
            'winrate_pct': 0.25,
            'total_return_pct': 0.20,
            'sharpe': 0.20,
            'max_drawdown_pct': 0.15,
            'total_trades': 0.10,
            'avg_trade_pnl': 0.10
        }
        
        # Normalize and score each metric
        winrate_score = min(metrics.get('winrate_pct', 0) / 50, 1.0)  # Cap at 50%
        return_score = max(min(metrics.get('total_return_pct', 0) / 20, 1.0), -1.0)  # Cap at ±20%
        sharpe_score = max(min(metrics.get('sharpe', 0) / 2, 1.0), -1.0)  # Cap at ±2
        drawdown_score = max(1 + metrics.get('max_drawdown_pct', 0) / 10, 0.0)  # Penalty for drawdown
        trades_score = min(metrics.get('total_trades', 0) / 50, 1.0)  # Prefer more trades
        pnl_score = max(min(metrics.get('avg_trade_pnl', 0) / 1, 1.0), -1.0)  # Cap at ±1%
        
        # Calculate weighted score
        total_score = (
            weights['winrate_pct'] * winrate_score +
            weights['total_return_pct'] * return_score +
            weights['sharpe'] * sharpe_score +
            weights['max_drawdown_pct'] * drawdown_score +
            weights['total_trades'] * trades_score +
            weights['avg_trade_pnl'] * pnl_score
        )
        
        return total_score
    
    def select_best_strategies(self, strategy_results, max_strategies=2):
        """Select best performing strategies"""
        rankings = self.evaluate_strategy_performance(strategy_results)
        
        # Filter out strategies with negative scores
        good_strategies = [s for s in rankings if s['score'] > 0]
        
        # Select top strategies
        selected_strategies = good_strategies[:max_strategies]
        
        # If no good strategies, select least bad ones
        if not selected_strategies:
            selected_strategies = rankings[:max_strategies]
        
        return selected_strategies
    
    def generate_adaptive_config(self, selected_strategies, base_config):
        """Generate adaptive configuration with selected strategies"""
        # Update strategies in config
        base_config['strategies'] = []
        
        for i, strategy in enumerate(selected_strategies):
            strategy_config = {
                'symbol': strategy['symbol'],
                'regime': 0,
                'strategy_type': strategy['strategy_type'],
                'params': strategy['params'],
                'priority': i + 1,
                'performance_score': strategy['score']
            }
            base_config['strategies'].append(strategy_config)
        
        # Update risk settings based on performance
        if selected_strategies:
            avg_score = np.mean([s['score'] for s in selected_strategies])
            
            if avg_score > 0.5:
                # High performance - more aggressive
                base_config['system_config']['trading_settings']['risk_per_trade'] = 0.003
                base_config['system_config']['trading_settings']['max_exposure_pct'] = 0.08
            elif avg_score > 0.2:
                # Medium performance - moderate
                base_config['system_config']['trading_settings']['risk_per_trade'] = 0.002
                base_config['system_config']['trading_settings']['max_exposure_pct'] = 0.05
            else:
                # Low performance - conservative
                base_config['system_config']['trading_settings']['risk_per_trade'] = 0.001
                base_config['system_config']['trading_settings']['max_exposure_pct'] = 0.03
        
        return base_config
    
    def save_strategy_selection(self, selected_strategies, config):
        """Save strategy selection results"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'selected_strategies': selected_strategies,
            'adaptive_config': config,
            'selection_criteria': {
                'max_strategies': 2,
                'min_score': 0.0,
                'performance_weights': {
                    'winrate_pct': 0.25,
                    'total_return_pct': 0.20,
                    'sharpe': 0.20,
                    'max_drawdown_pct': 0.15,
                    'total_trades': 0.10,
                    'avg_trade_pnl': 0.10
                }
            }
        }
        
        with open('reports/strategy_selection_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info("Strategy selection results saved")
    
    def run_strategy_selection(self, strategy_results, base_config):
        """Run complete strategy selection process"""
        logger.info("Starting strategy selection process")
        
        # Evaluate and rank strategies
        rankings = self.evaluate_strategy_performance(strategy_results)
        
        # Select best strategies
        selected_strategies = self.select_best_strategies(strategy_results, max_strategies=2)
        
        # Generate adaptive config
        adaptive_config = self.generate_adaptive_config(selected_strategies, base_config)
        
        # Save results
        self.save_strategy_selection(selected_strategies, adaptive_config)
        
        # Log results
        logger.info("Strategy selection completed:")
        for i, strategy in enumerate(selected_strategies):
            logger.info(f"  {i+1}. {strategy['strategy_type']}: Score={strategy['score']:.3f}")
        
        return selected_strategies, adaptive_config

def main():
    """Test the strategy selector"""
    logger.info("Testing strategy selector")
    
    # Sample strategy results
    strategy_results = [
        {
            'strategy_type': 'Simple_Momentum',
            'symbol': 'BTCUSDT',
            'metrics': {
                'total_trades': 15,
                'winrate_pct': 20.0,
                'total_return_pct': -2.17,
                'sharpe': -11.364,
                'max_drawdown_pct': -2.17,
                'avg_trade_pnl': -0.15
            },
            'params': {'ema_short': 8, 'ema_long': 21}
        },
        {
            'strategy_type': 'Simple_MeanReversion',
            'symbol': 'BTCUSDT',
            'metrics': {
                'total_trades': 58,
                'winrate_pct': 31.03,
                'total_return_pct': -3.84,
                'sharpe': -7.130,
                'max_drawdown_pct': -3.91,
                'avg_trade_pnl': -0.07
            },
            'params': {'rsi_period': 14, 'rsi_oversold': 30, 'rsi_overbought': 70}
        }
    ]
    
    # Sample base config
    base_config = {
        'system_config': {
            'trading_settings': {
                'risk_per_trade': 0.002,
                'max_exposure_pct': 0.05
            }
        }
    }
    
    # Test strategy selector
    selector = StrategySelector()
    selected_strategies, adaptive_config = selector.run_strategy_selection(strategy_results, base_config)
    
    print("Strategy selection completed!")
    print(f"Selected {len(selected_strategies)} strategies")

if __name__ == "__main__":
    main()
