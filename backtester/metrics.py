#!/usr/bin/env python3
"""
Backtester Metrics
Comprehensive performance metrics calculation
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """Calculate comprehensive trading performance metrics"""
    
    def __init__(self, risk_free_rate: float = 0.02):
        self.risk_free_rate = risk_free_rate
    
    def calculate_returns(self, equity_curve: pd.Series) -> pd.Series:
        """Calculate period returns from equity curve"""
        return equity_curve.pct_change().dropna()
    
    def calculate_total_return(self, equity_curve: pd.Series) -> float:
        """Calculate total return percentage"""
        if len(equity_curve) < 2:
            return 0.0
        
        initial = equity_curve.iloc[0]
        final = equity_curve.iloc[-1]
        
        # 🔥 BUG FIX: Check for zero initial capital before division!
        if initial == 0:
            logger.warning("Initial capital is zero, cannot calculate return")
            return 0.0
        
        return (final - initial) / initial
    
    def calculate_annual_return(self, equity_curve: pd.Series, periods_per_year: int = 252) -> float:
        """Calculate annualized return"""
        total_return = self.calculate_total_return(equity_curve)
        periods = len(equity_curve) - 1
        
        if periods <= 0:
            return 0.0
        
        years = periods / periods_per_year
        if years <= 0:
            return 0.0
        
        return (1 + total_return) ** (1 / years) - 1
    
    def calculate_volatility(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """Calculate annualized volatility"""
        if len(returns) < 2:
            return 0.0
        
        return returns.std() * np.sqrt(periods_per_year)
    
    def calculate_sharpe_ratio(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        
        # 🔥 BUG FIX: Calculate annual return from returns, not equity curve!
        # returns.mean() gives average return per period
        annual_return = returns.mean() * periods_per_year
        volatility = self.calculate_volatility(returns, periods_per_year)
        
        if volatility == 0:
            return 0.0
        
        return (annual_return - self.risk_free_rate) / volatility
    
    def calculate_sortino_ratio(self, returns: pd.Series, periods_per_year: int = 252) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        if len(returns) < 2:
            return 0.0
        
        # 🔥 BUG FIX: Calculate annual return from returns, not equity curve!
        annual_return = returns.mean() * periods_per_year
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf') if annual_return > self.risk_free_rate else 0.0
        
        downside_volatility = downside_returns.std() * np.sqrt(periods_per_year)
        
        if downside_volatility == 0:
            return 0.0
        
        return (annual_return - self.risk_free_rate) / downside_volatility
    
    def calculate_max_drawdown(self, equity_curve: pd.Series) -> Dict:
        """Calculate maximum drawdown and related metrics"""
        if len(equity_curve) < 2:
            return {
                'max_drawdown_pct': 0.0,
                'max_drawdown_duration': 0,
                'current_drawdown_pct': 0.0
            }
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # 🔥 BUG FIX: Avoid division by zero if running_max contains zeros!
        # Replace zeros with a small value to avoid division errors
        running_max = running_max.replace(0, 1e-10)
        
        # Calculate drawdown
        drawdown = (equity_curve - running_max) / running_max
        
        # Maximum drawdown
        max_drawdown_pct = drawdown.min() * 100
        
        # Drawdown duration
        in_drawdown = drawdown < 0
        drawdown_periods = []
        current_period = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_period += 1
            else:
                if current_period > 0:
                    drawdown_periods.append(current_period)
                current_period = 0
        
        if current_period > 0:
            drawdown_periods.append(current_period)
        
        max_drawdown_duration = max(drawdown_periods) if drawdown_periods else 0
        current_drawdown_pct = drawdown.iloc[-1] * 100
        
        return {
            'max_drawdown_pct': max_drawdown_pct,
            'max_drawdown_duration': max_drawdown_duration,
            'current_drawdown_pct': current_drawdown_pct
        }
    
    def calculate_win_rate(self, trade_pnls: List[float]) -> float:
        """Calculate win rate from trade PnLs"""
        if not trade_pnls:
            return 0.0
        
        winning_trades = sum(1 for pnl in trade_pnls if pnl > 0)
        return (winning_trades / len(trade_pnls)) * 100
    
    def calculate_profit_factor(self, trade_pnls: List[float]) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        if not trade_pnls:
            return 0.0
        
        gross_profit = sum(pnl for pnl in trade_pnls if pnl > 0)
        gross_loss = abs(sum(pnl for pnl in trade_pnls if pnl < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def calculate_expectancy(self, trade_pnls: List[float]) -> float:
        """Calculate expectancy (average trade PnL)"""
        if not trade_pnls:
            return 0.0
        
        return np.mean(trade_pnls)
    
    def calculate_trade_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate comprehensive trade metrics"""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate_pct': 0.0,
                'avg_trade_pnl': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0
            }
        
        trade_pnls = [trade.get('net_pnl', 0) for trade in trades]
        
        winning_trades = [pnl for pnl in trade_pnls if pnl > 0]
        losing_trades = [pnl for pnl in trade_pnls if pnl < 0]
        
        return {
            'total_trades': len(trades),
            'win_rate_pct': self.calculate_win_rate(trade_pnls),
            'avg_trade_pnl': self.calculate_expectancy(trade_pnls),
            'profit_factor': self.calculate_profit_factor(trade_pnls),
            'expectancy': self.calculate_expectancy(trade_pnls),
            'avg_win': np.mean(winning_trades) if winning_trades else 0.0,
            'avg_loss': np.mean(losing_trades) if losing_trades else 0.0,
            'largest_win': max(winning_trades) if winning_trades else 0.0,
            'largest_loss': min(losing_trades) if losing_trades else 0.0
        }
    
    def calculate_comprehensive_metrics(self, 
                                      equity_curve: pd.Series,
                                      trades: List[Dict],
                                      periods_per_year: int = 252) -> Dict:
        """Calculate all performance metrics"""
        
        # Basic metrics
        total_return = self.calculate_total_return(equity_curve)
        annual_return = self.calculate_annual_return(equity_curve, periods_per_year)
        
        # Risk metrics
        returns = self.calculate_returns(equity_curve)
        volatility = self.calculate_volatility(returns, periods_per_year)
        sharpe = self.calculate_sharpe_ratio(returns, periods_per_year)
        sortino = self.calculate_sortino_ratio(returns, periods_per_year)
        
        # Drawdown metrics
        drawdown_metrics = self.calculate_max_drawdown(equity_curve)
        
        # Trade metrics
        trade_metrics = self.calculate_trade_metrics(trades)
        
        # Combined metrics
        return {
            # Return metrics
            'total_return_pct': total_return * 100,
            'annual_return_pct': annual_return * 100,
            
            # Risk metrics
            'volatility_pct': volatility * 100,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            
            # Drawdown metrics
            'max_drawdown_pct': drawdown_metrics['max_drawdown_pct'],
            'max_drawdown_duration': drawdown_metrics['max_drawdown_duration'],
            'current_drawdown_pct': drawdown_metrics['current_drawdown_pct'],
            
            # Trade metrics
            **trade_metrics,
            
            # Additional metrics
            'calmar_ratio': annual_return / abs(drawdown_metrics['max_drawdown_pct'] / 100) if drawdown_metrics['max_drawdown_pct'] != 0 else 0.0,
            'recovery_factor': total_return / abs(drawdown_metrics['max_drawdown_pct'] / 100) if drawdown_metrics['max_drawdown_pct'] != 0 else 0.0
        }
    
    def validate_metrics(self, metrics: Dict) -> Dict:
        """Validate metrics for sanity and flag issues"""
        issues = []
        
        # Check for unrealistic returns
        if abs(metrics.get('total_return_pct', 0)) > 1000:
            issues.append("Unrealistic total return detected")
        
        # Check for invalid Sharpe ratio
        if abs(metrics.get('sharpe_ratio', 0)) > 10:
            issues.append("Unrealistic Sharpe ratio detected")
        
        # Check for invalid drawdown
        if metrics.get('max_drawdown_pct', 0) < -100:
            issues.append("Invalid drawdown detected")
        
        # Check for too few trades
        if metrics.get('total_trades', 0) < 10:
            issues.append("Insufficient trades for statistical significance")
        
        return {
            'metrics': metrics,
            'issues': issues,
            'is_valid': len(issues) == 0
        }
