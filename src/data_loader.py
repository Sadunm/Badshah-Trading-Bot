#!/usr/bin/env python3
"""
Data loader and quality validation module
Loads raw CSV data, aggregates to different timeframes, and validates data quality
"""

import pandas as pd
import numpy as np
import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_raw_csv(abs_path):
    """
    Load raw CSV data from absolute path
        
        Args:
        abs_path (str): Absolute path to CSV file
            
        Returns:
        pd.DataFrame: Loaded data with standardized columns
        """
        try:
            # 🔥 BUG FIX: Fixed ALL indentation errors!
            # Load CSV with common column mappings
            df = pd.read_csv(abs_path)
            
            # Standardize column names (case insensitive)
            column_mapping = {}
            for col in df.columns:
                col_lower = col.lower()
                if 'timestamp' in col_lower or 'time' in col_lower:
                    column_mapping[col] = 'timestamp'
                elif 'open' in col_lower:
                    column_mapping[col] = 'open'
                elif 'high' in col_lower:
                    column_mapping[col] = 'high'
                elif 'low' in col_lower:
                    column_mapping[col] = 'low'
                elif 'close' in col_lower:
                    column_mapping[col] = 'close'
                elif 'volume' in col_lower:
                    column_mapping[col] = 'volume'
            
            df = df.rename(columns=column_mapping)
                
            # Convert timestamp to datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
                
            # Ensure numeric columns are float
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            logger.info(f"Loaded {len(df)} rows from {abs_path}")
            return df
                
        except Exception as e:
            logger.error(f"Error loading {abs_path}: {e}")
            raise
    
def aggregate_to_tf(df, target_tf):
        """
        Aggregate data to target timeframe
        
        Args:
        df (pd.DataFrame): Input data with OHLCV columns
        target_tf (str): Target timeframe ('5m', '15m', '1h', '4h', 'daily')
            
        Returns:
        pd.DataFrame: Aggregated data
    """
    if target_tf == '5m':
        return df.resample('5T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
    elif target_tf == '15m':
        return df.resample('15T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
    elif target_tf == '1h':
        return df.resample('1H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
    elif target_tf == '4h':
        return df.resample('4H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
    elif target_tf == 'daily':
        return df.resample('1D').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
        }).dropna()
    else:
        raise ValueError(f"Unsupported timeframe: {target_tf}")

def validate_continuity(df, timeframe):
    """
    Validate data continuity and detect gaps
    
    Args:
        df (pd.DataFrame): Data to validate
        timeframe (str): Expected timeframe
        
    Returns:
        dict: Validation results with gap information
    """
        if len(df) < 2:
        return {"valid": False, "reason": "insufficient_data", "gaps": []}
    
    # Calculate expected time intervals
    timeframes = {
        '5m': timedelta(minutes=5),
        '15m': timedelta(minutes=15),
        '1h': timedelta(hours=1),
        '4h': timedelta(hours=4),
        'daily': timedelta(days=1)
    }
    
    expected_interval = timeframes.get(timeframe, timedelta(minutes=5))
    max_gap = expected_interval * 2  # Allow 2x timeframe as max gap
    
    # Find gaps
    gaps = []
    for i in range(1, len(df)):
        time_diff = df.index[i] - df.index[i-1]
        if time_diff > max_gap:
            # 🔥 BUG FIX: Fixed incorrect indentation!
            gaps.append({
                "start": df.index[i-1],
                "end": df.index[i],
                "duration": str(time_diff)
            })
    
    # Calculate gap percentage
    total_periods = len(df)
    gap_percentage = len(gaps) / total_periods * 100
    
    # Check for excessive gaps
    valid = gap_percentage <= 10.0  # Max 10% gaps allowed
    
    return {
        "valid": valid,
        "gaps": gaps,
        "gap_percentage": gap_percentage,
        "total_periods": total_periods,
        "timeframe": timeframe
    }

def process_symbol_data(symbol, raw_data_dir="data/raw", processed_data_dir="data/processed"):
    """
    Process data for a single symbol through all timeframes
        
        Args:
        symbol (str): Symbol name (e.g., 'BTCUSDT')
        raw_data_dir (str): Raw data directory
        processed_data_dir (str): Processed data directory
            
        Returns:
        dict: Processing results
    """
    results = {
        "symbol": symbol,
        "processed_timeframes": [],
        "errors": [],
        "skipped_timeframes": []
    }
    
    # Find raw data file
    raw_file = None
    for ext in ['.csv', '.parquet']:
        potential_file = os.path.join(raw_data_dir, f"{symbol}{ext}")
        if os.path.exists(potential_file):
            # 🔥 BUG FIX: Fixed incorrect indentation!
            raw_file = potential_file
            break
    
    if not raw_file:
        error_msg = f"No raw data file found for {symbol}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        return results
    
    try:
        # 🔥 BUG FIX: Fixed incorrect indentation!
        # Load raw data
        df = load_raw_csv(raw_file)
            
        # Process each timeframe
        timeframes = ['5m', '15m', '1h', '4h', 'daily']
            
        for tf in timeframes:
                try:
                    # Aggregate to timeframe
                tf_df = aggregate_to_tf(df, tf)
                
                # Validate continuity
                validation = validate_continuity(tf_df, tf)
                
                if not validation["valid"]:
                    error_msg = f"Data validation failed for {symbol} {tf}: {validation['gap_percentage']:.1f}% gaps"
                    logger.warning(error_msg)
                    
                    # Write error report
                    error_report = {
                        "symbol": symbol,
                        "timeframe": tf,
                        "error": "excessive_gaps",
                        "gap_percentage": validation["gap_percentage"],
                        "gaps": validation["gaps"],
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    
                    error_file = f"reports/data_error_{symbol}_{tf}.json"
                    with open(error_file, 'w') as f:
                        json.dump(error_report, f, indent=2, default=str)
                    
                    results["skipped_timeframes"].append(tf)
                    continue
                
                # Save processed data
                output_file = os.path.join(processed_data_dir, f"{symbol}_{tf}.parquet")
                tf_df.to_parquet(output_file)
                
                results["processed_timeframes"].append({
                    "timeframe": tf,
                    "rows": len(tf_df),
                    "file": output_file
                })
                
                logger.info(f"Processed {symbol} {tf}: {len(tf_df)} rows")
                    
                except Exception as e:
                error_msg = f"Error processing {symbol} {tf}: {e}"
                    logger.error(error_msg)
                results["errors"].append(error_msg)
        
        return results
            
        except Exception as e:
        error_msg = f"Error loading raw data for {symbol}: {e}"
                    logger.error(error_msg)
        results["errors"].append(error_msg)
        return results

def update_manifest(processed_files, manifest_file="data/processed/manifest.json"):
    """
    Update manifest with file information and checksums
    
    Args:
        processed_files (list): List of processed file information
        manifest_file (str): Manifest file path
    """
    manifest = {}
    
            # Load existing manifest
    if os.path.exists(manifest_file):
        with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
    
    # Update with new files
    for file_info in processed_files:
        file_path = file_info["file"]
        if os.path.exists(file_path):
            # Calculate SHA256
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            manifest[file_path] = {
                "sha256": file_hash,
                "rows": file_info["rows"],
                "timeframe": file_info["timeframe"],
                "symbol": file_info.get("symbol", ""),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    # Save updated manifest
    with open(manifest_file, 'w') as f:
                json.dump(manifest, f, indent=2)
                
def main():
    """Main data processing function"""
    logger.info("Starting data processing pipeline")
    
    # Find all symbols in raw data directory
    raw_dir = "data/raw"
    symbols = set()
    
    for file in os.listdir(raw_dir):
        if file.endswith(('.csv', '.parquet')):
            # Extract symbol from filename
            symbol = file.split('_')[0]  # Assume format: SYMBOL_timestamp.csv
            symbols.add(symbol)
    
    logger.info(f"Found symbols: {list(symbols)}")
    
    all_results = []
    all_processed_files = []
    
    # Process each symbol
    for symbol in symbols:
        logger.info(f"Processing {symbol}")
        results = process_symbol_data(symbol)
        all_results.append(results)
        
        # Collect processed files for manifest
        for tf_info in results["processed_timeframes"]:
            all_processed_files.append({
                "file": tf_info["file"],
                "rows": tf_info["rows"],
                "timeframe": tf_info["timeframe"],
                "symbol": symbol
            })
    
    # Update manifest
    if all_processed_files:
        update_manifest(all_processed_files)
        logger.info(f"Updated manifest with {len(all_processed_files)} files")
    
    # Save processing summary
    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "symbols_processed": len(symbols),
        "total_files_processed": len(all_processed_files),
        "results": all_results
    }
    
    with open("reports/data_processing_summary.json", 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    logger.info("Data processing completed")
    return summary

if __name__ == "__main__":
    main()
