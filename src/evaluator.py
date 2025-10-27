#!/usr/bin/env python3
"""
Candidate evaluator with Walk Forward and Monte Carlo analysis
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backtester import VectorizedBacktester

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CandidateEvaluator:
    """Evaluates strategy candidates with WF and MC analysis"""
    
    def __init__(self, data_dir="data/processed"):
        self.data_dir = data_dir
        self.backtester = VectorizedBacktester()
    
    def load_candidates(self, candidates_file="reports/candidates_raw.json"):
        """Load strategy candidates"""
        with open(candidates_file, 'r') as f:
            data = json.load(f)
        return data['candidates']
    
    def load_data(self, symbol, timeframe="5m"):
        """Load data for a symbol"""
        data_file = os.path.join(self.data_dir, f"{symbol}_{timeframe}.parquet")
        
        if not os.path.exists(data_file):
            raise FileNotFoundError(f"Data file not found: {data_file}")
        
        df = pd.read_parquet(data_file)
        
        # Fix column names
        if len(df.columns) == 6:
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            if df['timestamp'].dtype in ['int64', 'float64']:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
        
        return df
    
    def walk_forward_analysis(self, df, strategy_type, params, n_folds=4):
        """
        Perform walk-forward analysis
        
        Args:
            df (pd.DataFrame): Price data
            strategy_type (str): Strategy type
            params (dict): Strategy parameters
            n_folds (int): Number of folds
            
        Returns:
            dict: Walk-forward results
        """
        total_len = len(df)
        fold_size = total_len // n_folds
        
        fold_results = []
        
        for i in range(n_folds):
            # Training period
            train_start = 0
            train_end = (i + 1) * fold_size
            
            # Test period
            test_start = train_end
            test_end = min((i + 2) * fold_size, total_len) if i < n_folds - 1 else total_len
            
            if test_end - test_start < 50:  # Minimum test period
                continue
            
            # Train on first part, test on second part
            train_data = df.iloc[train_start:train_end]
            test_data = df.iloc[test_start:test_end]
            
            # Backtest on test period
            try:
                results = self.backtester.backtest_strategy(
                    test_data, strategy_type, params, initial_capital=10000
                )
                
                fold_results.append({
                    'fold': i + 1,
                    'train_period': f"{train_data.index[0]} to {train_data.index[-1]}",
                    'test_period': f"{test_data.index[0]} to {test_data.index[-1]}",
                    'metrics': results['metrics']
                })
            
        except Exception as e:
                logger.warning(f"Walk-forward fold {i+1} failed: {e}")
                continue
        
        # Calculate average metrics
        if fold_results:
            avg_metrics = {}
            for key in ['total_trades', 'winrate_pct', 'avg_trade_pnl', 'sharpe', 'max_drawdown_pct', 'expectancy', 'total_return_pct']:
                values = [fold['metrics'][key] for fold in fold_results if key in fold['metrics']]
                avg_metrics[key] = np.mean(values) if values else 0
            
            return {
                'n_folds': len(fold_results),
                'fold_results': fold_results,
                'avg_metrics': avg_metrics
            }
        else:
            return {'n_folds': 0, 'fold_results': [], 'avg_metrics': {}}
    
    def monte_carlo_analysis(self, df, strategy_type, params, n_runs=50, block_size=20):
        """
        Perform Monte Carlo analysis with block bootstrap
        
        Args:
            df (pd.DataFrame): Price data
            strategy_type (str): Strategy type
            params (dict): Strategy parameters
            n_runs (int): Number of Monte Carlo runs
            block_size (int): Block size for bootstrap
            
        Returns:
            dict: Monte Carlo results
        """
        returns = df['close'].pct_change().dropna()
        n_blocks = len(returns) // block_size
        
        mc_results = []
        
        for run in range(n_runs):
            try:
                # Block bootstrap
                bootstrap_returns = []
                for _ in range(n_blocks):
                    start_idx = np.random.randint(0, len(returns) - block_size)
                    block = returns.iloc[start_idx:start_idx + block_size]
                    bootstrap_returns.extend(block.values)
                
                # Create bootstrap price series
                bootstrap_prices = [df['close'].iloc[0]]
                for ret in bootstrap_returns:
                    bootstrap_prices.append(bootstrap_prices[-1] * (1 + ret))
                
                # Create bootstrap dataframe
                bootstrap_df = df.copy()
                bootstrap_df['close'] = bootstrap_prices[:len(df)]
                bootstrap_df['open'] = bootstrap_df['close'].shift(1).fillna(bootstrap_df['close'])
                bootstrap_df['high'] = np.maximum(bootstrap_df['open'], bootstrap_df['close'])
                bootstrap_df['low'] = np.minimum(bootstrap_df['open'], bootstrap_df['close'])
                
                # Backtest bootstrap data
                results = self.backtester.backtest_strategy(
                    bootstrap_df, strategy_type, params, initial_capital=10000
                )
                
                mc_results.append(results['metrics'])
            
        except Exception as e:
                logger.warning(f"Monte Carlo run {run+1} failed: {e}")
                continue
        
        if mc_results:
            # Calculate statistics
            metrics_stats = {}
            for key in ['total_trades', 'winrate_pct', 'avg_trade_pnl', 'sharpe', 'max_drawdown_pct', 'expectancy', 'total_return_pct']:
                values = [result[key] for result in mc_results if key in result]
                if values:
                    metrics_stats[key] = {
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'min': np.min(values),
                        'max': np.max(values),
                        'median': np.median(values)
                    }
            
            return {
                'n_runs': len(mc_results),
                'metrics_stats': metrics_stats,
                'all_results': mc_results
            }
        else:
            return {'n_runs': 0, 'metrics_stats': {}, 'all_results': []}
    
    def calculate_composite_score(self, wf_metrics, mc_metrics):
        """
        Calculate composite score for candidate ranking
        
        Args:
            wf_metrics (dict): Walk-forward metrics
            mc_metrics (dict): Monte Carlo metrics
            
        Returns:
            float: Composite score
        """
        # Normalize metrics (simple min-max normalization)
        sharpe = wf_metrics.get('sharpe', 0)
        expectancy = wf_metrics.get('expectancy', 0)
        winrate = wf_metrics.get('winrate_pct', 0) / 100
        drawdown = abs(wf_metrics.get('max_drawdown_pct', 0)) / 100
        
        # Normalize to 0-1 range (assuming reasonable bounds)
        sharpe_norm = max(0, min(1, (sharpe + 2) / 4))  # -2 to 2 range
        expectancy_norm = max(0, min(1, (expectancy + 0.1) / 0.2))  # -0.1 to 0.1 range
        winrate_norm = max(0, min(1, winrate))  # 0 to 1 range
        drawdown_norm = max(0, min(1, 1 - drawdown))  # Invert drawdown (lower is better)
        
        # Composite score
        score = (0.35 * sharpe_norm + 
                0.25 * expectancy_norm +
                0.20 * winrate_norm - 
                0.20 * drawdown_norm)
        
        return score
    
    def evaluate_candidate(self, candidate):
        """
        Evaluate a single candidate
        
        Args:
            candidate (dict): Strategy candidate
            
        Returns:
            dict: Evaluation results
        """
        symbol = candidate['symbol']
        strategy_type = candidate['strategy_type']
        params = candidate['params']
        
        try:
            # Load data
            df = self.load_data(symbol)
            
            # Full backtest
            full_results = self.backtester.backtest_strategy(df, strategy_type, params)
            
            # Walk-forward analysis
            wf_results = self.walk_forward_analysis(df, strategy_type, params)
            
            # Monte Carlo analysis
            mc_results = self.monte_carlo_analysis(df, strategy_type, params)
            
            # Calculate composite score
            composite_score = self.calculate_composite_score(
                wf_results.get('avg_metrics', {}), 
                mc_results.get('metrics_stats', {})
            )
            
            return {
                'candidate_id': candidate['id'],
                'symbol': symbol,
                'strategy_type': strategy_type,
                'params': params,
                'full_backtest': full_results['metrics'],
                'walk_forward': wf_results,
                'monte_carlo': mc_results,
                'composite_score': composite_score,
                'evaluation_timestamp': datetime.utcnow().isoformat() + "Z"
            }
            
        except Exception as e:
            logger.error(f"Error evaluating candidate {candidate['id']}: {e}")
            return {
                'candidate_id': candidate['id'],
                'symbol': symbol,
                'strategy_type': strategy_type,
                'params': params,
                'error': str(e),
                'composite_score': 0
            }
    
    def evaluate_all_candidates(self, candidates_file="reports/candidates_raw.json"):
        """
        Evaluate all candidates
        
        Args:
            candidates_file (str): Path to candidates file
            
        Returns:
            dict: All evaluation results
        """
        candidates = self.load_candidates(candidates_file)
        logger.info(f"Evaluating {len(candidates)} candidates")
        
        all_results = []
        
        for candidate in candidates:
            logger.info(f"Evaluating candidate {candidate['id']}: {candidate['strategy_type']}")
            result = self.evaluate_candidate(candidate)
            all_results.append(result)
        
        # Sort by composite score
        all_results.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
        
        # Save results
        results = {
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'total_candidates': len(candidates),
            'evaluated_candidates': len(all_results),
            'results': all_results
        }
        
        with open("reports/candidates_all.json", 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save top candidates
        top_candidates = all_results[:3]  # Top 3
        with open("reports/candidates_top.json", 'w') as f:
            json.dump(top_candidates, f, indent=2, default=str)
        
        logger.info(f"Evaluation completed. Top candidate score: {top_candidates[0].get('composite_score', 0):.3f}")
        
        return results

def main():
    """Main evaluation function"""
    logger.info("Starting candidate evaluation")
    
    evaluator = CandidateEvaluator()
    results = evaluator.evaluate_all_candidates()
    
    logger.info("Candidate evaluation completed")
    return results

if __name__ == "__main__":
    main()
