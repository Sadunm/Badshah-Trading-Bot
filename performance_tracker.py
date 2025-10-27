# -*- coding: utf-8 -*-
"""
Performance Tracker - Analyze trading results and generate reports
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd

class PerformanceTracker:
    """Track and analyze trading performance"""
    
    def __init__(self, trades_file='data/trades.json', reports_dir='reports'):
        self.trades_file = trades_file
        self.reports_dir = reports_dir
        os.makedirs(reports_dir, exist_ok=True)
        os.makedirs(os.path.dirname(trades_file), exist_ok=True)
        
    def load_trades(self) -> List[Dict]:
        """Load trades from file"""
        if not os.path.exists(self.trades_file):
            return []
        
        try:
            with open(self.trades_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def save_trade(self, trade: Dict):
        """Save a single trade"""
        trades = self.load_trades()
        trades.append(trade)
        
        with open(self.trades_file, 'w') as f:
            json.dump(trades, f, indent=2)
    
    def calculate_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate performance metrics"""
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'max_win': 0,
                'max_loss': 0,
            }
        
        df = pd.DataFrame(trades)
        
        # Basic stats
        total_trades = len(df)
        winning_trades = len(df[df['pnl'] > 0])
        losing_trades = len(df[df['pnl'] < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # PnL stats
        total_pnl = df['pnl'].sum()
        wins = df[df['pnl'] > 0]['pnl']
        losses = df[df['pnl'] < 0]['pnl']
        
        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = losses.mean() if len(losses) > 0 else 0
        
        profit_factor = abs(wins.sum() / losses.sum()) if len(losses) > 0 and losses.sum() != 0 else 0
        
        max_win = df['pnl'].max()
        max_loss = df['pnl'].min()
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_win': max_win,
            'max_loss': max_loss,
        }
    
    def generate_daily_report(self) -> str:
        """Generate daily performance report"""
        trades = self.load_trades()
        
        # Filter today's trades
        today = datetime.now().date()
        today_trades = [t for t in trades if datetime.fromisoformat(t['timestamp']).date() == today]
        
        # Calculate metrics
        metrics = self.calculate_metrics(today_trades)
        all_metrics = self.calculate_metrics(trades)
        
        # Generate report
        report = f"""
╔══════════════════════════════════════════════════════════════════╗
║           BADSHAH TRADING BOT - DAILY REPORT                    ║
║           {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          ║
╚══════════════════════════════════════════════════════════════════╝

TODAY'S PERFORMANCE
-------------------------------------------------------------------
Total Trades:        {metrics['total_trades']}
Winning Trades:      {metrics['winning_trades']}
Losing Trades:       {metrics['losing_trades']}
Win Rate:            {metrics['win_rate']:.1f}%

Total PnL:           ${metrics['total_pnl']:.2f}
Average Win:         ${metrics['avg_win']:.2f}
Average Loss:        ${metrics['avg_loss']:.2f}
Profit Factor:       {metrics['profit_factor']:.2f}

Best Trade:          ${metrics['max_win']:.2f}
Worst Trade:         ${metrics['max_loss']:.2f}

OVERALL PERFORMANCE (ALL TIME)
-------------------------------------------------------------------
Total Trades:        {all_metrics['total_trades']}
Winning Trades:      {all_metrics['winning_trades']}
Losing Trades:       {all_metrics['losing_trades']}
Win Rate:            {all_metrics['win_rate']:.1f}%

Total PnL:           ${all_metrics['total_pnl']:.2f}
Average Win:         ${all_metrics['avg_win']:.2f}
Average Loss:        ${all_metrics['avg_loss']:.2f}
Profit Factor:       {all_metrics['profit_factor']:.2f}

COIN BREAKDOWN (TODAY)
-------------------------------------------------------------------
"""
        
        # Coin-by-coin breakdown
        if today_trades:
            df = pd.DataFrame(today_trades)
            for symbol in df['symbol'].unique():
                symbol_trades = df[df['symbol'] == symbol]
                symbol_pnl = symbol_trades['pnl'].sum()
                symbol_count = len(symbol_trades)
                symbol_wins = len(symbol_trades[symbol_trades['pnl'] > 0])
                symbol_wr = (symbol_wins / symbol_count * 100) if symbol_count > 0 else 0
                
                report += f"{symbol:12} | Trades: {symbol_count:2} | Win Rate: {symbol_wr:5.1f}% | PnL: ${symbol_pnl:+8.2f}\n"
        else:
            report += "No trades today\n"
        
        report += f"""
-------------------------------------------------------------------
Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # Save report
        report_file = os.path.join(self.reports_dir, f"daily_report_{today.strftime('%Y%m%d')}.txt")
        with open(report_file, 'w') as f:
            f.write(report)
        
        # Also save as latest
        with open(os.path.join(self.reports_dir, 'daily_report.txt'), 'w') as f:
            f.write(report)
        
        return report
    
    def generate_weekly_report(self) -> str:
        """Generate weekly performance report"""
        trades = self.load_trades()
        
        # Filter this week's trades
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_trades = [t for t in trades if datetime.fromisoformat(t['timestamp']).date() >= week_start]
        
        metrics = self.calculate_metrics(week_trades)
        
        report = f"""
╔══════════════════════════════════════════════════════════════════╗
║           BADSHAH TRADING BOT - WEEKLY REPORT                   ║
║           Week of {week_start.strftime('%Y-%m-%d')}                              ║
╚══════════════════════════════════════════════════════════════════╝

WEEK'S PERFORMANCE
-------------------------------------------------------------------
Total Trades:        {metrics['total_trades']}
Winning Trades:      {metrics['winning_trades']}
Losing Trades:       {metrics['losing_trades']}
Win Rate:            {metrics['win_rate']:.1f}%

Total PnL:           ${metrics['total_pnl']:.2f}
Average Win:         ${metrics['avg_win']:.2f}
Average Loss:        ${metrics['avg_loss']:.2f}
Profit Factor:       {metrics['profit_factor']:.2f}

Best Trade:          ${metrics['max_win']:.2f}
Worst Trade:         ${metrics['max_loss']:.2f}

DAILY BREAKDOWN
-------------------------------------------------------------------
"""
        
        # Day-by-day breakdown
        if week_trades:
            df = pd.DataFrame(week_trades)
            df['date'] = pd.to_datetime(df['timestamp']).dt.date
            
            for day in pd.date_range(week_start, today, freq='D'):
                day_date = day.date()
                day_trades = df[df['date'] == day_date]
                
                if len(day_trades) > 0:
                    day_pnl = day_trades['pnl'].sum()
                    day_count = len(day_trades)
                    day_wins = len(day_trades[day_trades['pnl'] > 0])
                    day_wr = (day_wins / day_count * 100) if day_count > 0 else 0
                    
                    report += f"{day_date.strftime('%a %Y-%m-%d')} | Trades: {day_count:2} | Win Rate: {day_wr:5.1f}% | PnL: ${day_pnl:+8.2f}\n"
                else:
                    report += f"{day_date.strftime('%a %Y-%m-%d')} | No trades\n"
        
        report += f"""
-------------------------------------------------------------------
Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # Save report
        report_file = os.path.join(self.reports_dir, f"weekly_report_{week_start.strftime('%Y%m%d')}.txt")
        with open(report_file, 'w') as f:
            f.write(report)
        
        # Also save as latest
        with open(os.path.join(self.reports_dir, 'weekly_report.txt'), 'w') as f:
            f.write(report)
        
        return report
    
    def coin_performance_analysis(self) -> str:
        """Analyze which coins are performing best"""
        trades = self.load_trades()
        
        if not trades:
            return "No trades to analyze"
        
        df = pd.DataFrame(trades)
        
        report = """
╔══════════════════════════════════════════════════════════════════╗
║           COIN PERFORMANCE ANALYSIS                             ║
╚══════════════════════════════════════════════════════════════════╝

"""
        
        for symbol in sorted(df['symbol'].unique()):
            symbol_trades = df[df['symbol'] == symbol]
            metrics = self.calculate_metrics(symbol_trades.to_dict('records'))
            
            # Status emoji
            if metrics['win_rate'] >= 55 and metrics['total_pnl'] > 0:
                status = "KEEP"
                emoji = "[OK]"
            elif metrics['win_rate'] >= 45:
                status = "REVIEW"
                emoji = "[?]"
            else:
                status = "REMOVE"
                emoji = "[X]"
            
            report += f"""
{emoji} {symbol}
   Total Trades:     {metrics['total_trades']}
   Win Rate:         {metrics['win_rate']:.1f}%
   Total PnL:        ${metrics['total_pnl']:+.2f}
   Avg Profit/Trade: ${(metrics['total_pnl'] / metrics['total_trades']):+.2f}
   Profit Factor:    {metrics['profit_factor']:.2f}
   Status:           {status}
"""
        
        # Save report
        with open(os.path.join(self.reports_dir, 'coin_analysis.txt'), 'w') as f:
            f.write(report)
        
        return report


if __name__ == '__main__':
    # Test the tracker
    tracker = PerformanceTracker()
    
    print("Generating reports...")
    print(tracker.generate_daily_report())
    print("\n" + "="*70 + "\n")
    print(tracker.generate_weekly_report())
    print("\n" + "="*70 + "\n")
    print(tracker.coin_performance_analysis())

