#!/usr/bin/env python3
"""
Regime detection module
Uses HMM for regime detection with fallback to volatility+ADX clustering
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_technical_indicators(df):
    """Calculate technical indicators for regime detection"""
    df = df.copy()
    
    # Price-based indicators
            df['returns'] = df['close'].pct_change()
            df['volatility'] = df['returns'].rolling(window=20).std()
    df['price_change'] = df['close'].pct_change(20)  # 20-period price change
    
    # Volume indicators
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    
    # Trend indicators
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['trend'] = (df['sma_20'] - df['sma_50']) / df['sma_50']
    
    # Volatility regime
    df['vol_regime'] = np.where(df['volatility'] > df['volatility'].rolling(50).quantile(0.7), 'high', 'low')
    
    # Volume regime
    df['vol_regime'] = np.where(df['volume_ratio'] > 1.5, 'high', 'low')
    
            return df
            
def hmm_regime_detection(df, n_regimes=3):
    """
    HMM-based regime detection
    
    Args:
        df (pd.DataFrame): Data with technical indicators
        n_regimes (int): Number of regimes to detect
        
    Returns:
        pd.DataFrame: Data with regime labels
    """
    try:
        from hmmlearn import hmm
        
            # Prepare features for HMM
        features = ['returns', 'volatility', 'volume_ratio', 'trend']
        feature_data = df[features].dropna()
        
        if len(feature_data) < 100:
            logger.warning("Insufficient data for HMM, using fallback method")
            return fallback_regime_detection(df)
            
            # Standardize features
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(feature_data)
        
        # Fit HMM
        model = hmm.GaussianHMM(n_components=n_regimes, covariance_type="full", random_state=42)
        model.fit(scaled_features)
            
            # Predict regimes
        regimes = model.predict(scaled_features)
        
        # Add regime labels to original dataframe
        df_result = df.copy()
        df_result['regime'] = np.nan
        df_result.loc[feature_data.index, 'regime'] = regimes
        
        # Forward fill missing values
        df_result['regime'] = df_result['regime'].fillna(method='ffill')
        
        logger.info(f"HMM detected {n_regimes} regimes")
        return df_result
        
    except ImportError:
        logger.warning("hmmlearn not available, using fallback method")
        return fallback_regime_detection(df)
        except Exception as e:
        logger.error(f"HMM detection failed: {e}, using fallback method")
        return fallback_regime_detection(df)

def fallback_regime_detection(df):
    """
    Fallback regime detection using volatility and trend clustering
    
    Args:
        df (pd.DataFrame): Data with technical indicators
        
    Returns:
        pd.DataFrame: Data with regime labels
    """
    df = df.copy()
    
    # Calculate regime features
    df = calculate_technical_indicators(df)
    
    # Simple regime classification based on volatility and trend
    df['regime'] = 0  # Default regime
    
    # High volatility regime
    high_vol_mask = df['volatility'] > df['volatility'].rolling(50).quantile(0.7)
    df.loc[high_vol_mask, 'regime'] = 1
    
    # Trend regime
    trend_mask = (df['trend'] > 0.02) & (df['volatility'] < df['volatility'].rolling(50).quantile(0.3))
    df.loc[trend_mask, 'regime'] = 2
    
    # Sideways regime (low volatility, low trend)
    sideways_mask = (df['volatility'] < df['volatility'].rolling(50).quantile(0.3)) & (abs(df['trend']) < 0.01)
    df.loc[sideways_mask, 'regime'] = 0
    
    logger.info("Used fallback regime detection method")
            return df
            
def analyze_regime_stability(df, window=50):
    """
    Analyze regime stability over time
    
    Args:
        df (pd.DataFrame): Data with regime labels
        window (int): Window size for stability analysis
        
    Returns:
        dict: Stability analysis results
    """
    if 'regime' not in df.columns:
        return {"error": "No regime column found"}
    
    # Calculate regime changes
    regime_changes = (df['regime'] != df['regime'].shift()).sum()
    total_periods = len(df)
    change_rate = regime_changes / total_periods
    
    # Calculate regime durations
    regime_durations = []
    current_regime = None
    current_duration = 0
    
    for regime in df['regime']:
        if regime == current_regime:
            current_duration += 1
        else:
            if current_regime is not None:
                regime_durations.append(current_duration)
            current_regime = regime
            current_duration = 1
    
    if current_regime is not None:
        regime_durations.append(current_duration)
    
    # Calculate stability metrics
    avg_duration = np.mean(regime_durations) if regime_durations else 0
    min_duration = np.min(regime_durations) if regime_durations else 0
    max_duration = np.max(regime_durations) if regime_durations else 0
    
    # Regime distribution
    regime_counts = df['regime'].value_counts().to_dict()
    
    return {
        "total_periods": total_periods,
        "regime_changes": regime_changes,
        "change_rate": change_rate,
        "avg_duration": avg_duration,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "regime_counts": regime_counts,
        "stability_score": 1 - change_rate  # Higher is more stable
    }

def process_symbol_regime(symbol, data_dir="data/processed"):
    """
    Process regime detection for a single symbol
        
        Args:
        symbol (str): Symbol name
        data_dir (str): Processed data directory
            
        Returns:
        dict: Processing results
    """
    results = {
        "symbol": symbol,
        "success": False,
        "regime_data": None,
        "stability_analysis": None,
        "error": None
    }
    
    try:
        # Find processed data file
        data_file = os.path.join(data_dir, f"{symbol}_5m.parquet")
        if not os.path.exists(data_file):
            results["error"] = f"Processed data file not found: {data_file}"
            return results
        
        # Load data
        df = pd.read_parquet(data_file)
        logger.info(f"Loaded {len(df)} rows for {symbol}")
        
        # Check if data has proper column names, if not, assume standard OHLCV format
        if len(df.columns) == 6 and all(isinstance(col, str) and col.isdigit() for col in df.columns):
            # Data has numeric column names, assume OHLCV format
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
        elif 'close' not in df.columns:
            # Try to identify columns by position
            if len(df.columns) >= 5:
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df = df.set_index('timestamp')
        
        # Calculate technical indicators
        df = calculate_technical_indicators(df)
        
        # Try HMM first, fallback to simple method
        df_with_regimes = hmm_regime_detection(df)
        
        # Analyze regime stability
        stability = analyze_regime_stability(df_with_regimes)
        
        # Save regime data
        regime_file = os.path.join(data_dir, f"{symbol}_regimes.parquet")
        df_with_regimes.to_parquet(regime_file)
        
        # Save regime report
        regime_report = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_periods": len(df_with_regimes),
            "regime_counts": stability["regime_counts"],
            "stability_score": stability["stability_score"],
            "avg_duration": stability["avg_duration"],
            "change_rate": stability["change_rate"]
        }
        
        report_file = f"reports/regime_{symbol}.json"
        with open(report_file, 'w') as f:
            json.dump(regime_report, f, indent=2, default=str)
        
        results["success"] = True
        results["regime_data"] = regime_file
        results["stability_analysis"] = stability
        
        logger.info(f"Regime detection completed for {symbol}")
            
        except Exception as e:
        error_msg = f"Error processing regime for {symbol}: {e}"
        logger.error(error_msg)
        results["error"] = error_msg
        
        # Write error report
        error_report = {
            "symbol": symbol,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        error_file = f"reports/regime_error_{symbol}.json"
        with open(error_file, 'w') as f:
            json.dump(error_report, f, indent=2, default=str)
    
    return results

def main():
    """Main regime detection function"""
    logger.info("Starting regime detection pipeline")
    
    # Find processed data files
    processed_dir = "data/processed"
    symbols = set()
    
    for file in os.listdir(processed_dir):
        if file.endswith('.parquet') and not file.endswith('_regimes.parquet'):
            symbol = file.split('_')[0]
            symbols.add(symbol)
    
    logger.info(f"Found symbols: {list(symbols)}")
    
    all_results = []
    successful_symbols = []
    
    # Process each symbol
    for symbol in symbols:
        logger.info(f"Processing regime detection for {symbol}")
        results = process_symbol_regime(symbol)
        all_results.append(results)
        
        if results["success"]:
            successful_symbols.append(symbol)
    
    # Save overall summary
    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "symbols_processed": len(symbols),
        "successful_symbols": successful_symbols,
        "results": all_results
    }
    
    with open("reports/regime_detection_summary.json", 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    logger.info(f"Regime detection completed. Success: {len(successful_symbols)}/{len(symbols)}")
    return summary

if __name__ == "__main__":
    main()
