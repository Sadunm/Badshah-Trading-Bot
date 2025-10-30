# -*- coding: utf-8 -*-
"""
🔍 LOG ANALYZER - Quickly find important information in trading logs
"""

import os
import sys
from datetime import datetime
from collections import Counter

# Fix Windows encoding
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

def analyze_logs(log_file):
    """Analyze a log file and show summary"""
    
    if not os.path.exists(log_file):
        print(f"❌ Log file not found: {log_file}")
        return
    
    print("="*80)
    print(f"📊 ANALYZING: {log_file}")
    print("="*80)
    
    # Counters
    total_lines = 0
    errors = []
    warnings = []
    trades_opened = []
    trades_closed = []
    signals_generated = []
    signals_rejected = []
    confidence_issues = []
    volume_issues = []
    atr_issues = []
    
    # Read and analyze
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            total_lines += 1
            
            # Track errors and warnings
            if 'ERROR' in line:
                errors.append(line.strip())
            elif 'WARNING' in line:
                warnings.append(line.strip())
            
            # Track signals
            if '✅' in line and ('BUY' in line or 'SELL' in line):
                signals_generated.append(line.strip())
            
            # Track rejections
            if '❌' in line:
                signals_rejected.append(line.strip())
                
            # Track specific rejection reasons
            if 'Confidence' in line and '<' in line:
                confidence_issues.append(line.strip())
            if 'Volume too low' in line:
                volume_issues.append(line.strip())
            if 'ATR too low' in line:
                atr_issues.append(line.strip())
            
            # Track trades
            if '🚀 OPENING POSITION' in line:
                trades_opened.append(line.strip())
            if '💰 POSITION CLOSED' in line or 'CLOSED POSITION' in line:
                trades_closed.append(line.strip())
    
    # Print summary
    print(f"\n📝 TOTAL LINES: {total_lines}")
    print(f"⚠️  WARNINGS: {len(warnings)}")
    print(f"❌ ERRORS: {len(errors)}")
    print()
    
    print("="*80)
    print("🎯 TRADING ACTIVITY")
    print("="*80)
    print(f"✅ Signals Generated: {len(signals_generated)}")
    print(f"❌ Signals Rejected: {len(signals_rejected)}")
    print(f"🚀 Trades Opened: {len(trades_opened)}")
    print(f"💰 Trades Closed: {len(trades_closed)}")
    print()
    
    print("="*80)
    print("🔍 REJECTION REASONS")
    print("="*80)
    print(f"📊 Confidence too low: {len(confidence_issues)}")
    print(f"📉 Volume too low: {len(volume_issues)}")
    print(f"📈 ATR too low: {len(atr_issues)}")
    print()
    
    # Show last 10 confidence rejections
    if confidence_issues:
        print("="*80)
        print("⏸️  LAST 10 CONFIDENCE REJECTIONS:")
        print("="*80)
        for issue in confidence_issues[-10:]:
            print(issue)
        print()
    
    # Show last 10 errors
    if errors:
        print("="*80)
        print("❌ LAST 10 ERRORS:")
        print("="*80)
        for error in errors[-10:]:
            print(error)
        print()
    
    # Show all trades opened
    if trades_opened:
        print("="*80)
        print("🚀 ALL TRADES OPENED:")
        print("="*80)
        for trade in trades_opened:
            print(trade)
        print()
    
    # Show all trades closed
    if trades_closed:
        print("="*80)
        print("💰 ALL TRADES CLOSED:")
        print("="*80)
        for trade in trades_closed:
            print(trade)
        print()
    
    print("="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)


def list_log_files():
    """List all available log files"""
    
    if not os.path.exists('logs'):
        print("❌ No logs directory found!")
        return []
    
    log_files = []
    for file in os.listdir('logs'):
        if file.endswith('.log'):
            filepath = os.path.join('logs', file)
            size = os.path.getsize(filepath) / 1024  # KB
            modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            log_files.append({
                'name': file,
                'path': filepath,
                'size': size,
                'modified': modified
            })
    
    # Sort by modified time (newest first)
    log_files.sort(key=lambda x: x['modified'], reverse=True)
    
    return log_files


def main():
    print("="*80)
    print("🔍 TRADING BOT LOG ANALYZER")
    print("="*80)
    print()
    
    # List available logs
    log_files = list_log_files()
    
    if not log_files:
        print("❌ No log files found in 'logs' directory!")
        return
    
    print("📁 AVAILABLE LOG FILES:")
    print()
    
    for i, log in enumerate(log_files, 1):
        print(f"{i}. {log['name']}")
        print(f"   Size: {log['size']:.2f} KB | Modified: {log['modified']}")
        print()
    
    # Auto-analyze the latest session log
    latest_session = None
    for log in log_files:
        if log['name'].startswith('session_'):
            latest_session = log['path']
            break
    
    if latest_session:
        print(f"🔍 Auto-analyzing latest session log...")
        print()
        analyze_logs(latest_session)
    else:
        print("⚠️  No session log found. Analyzing general log...")
        analyze_logs('logs/multi_coin_trading.log')


if __name__ == "__main__":
    main()

