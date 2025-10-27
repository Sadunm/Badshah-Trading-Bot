"""
Data Downloader for Badshah Trading System
Downloads historical data when no processed data is available
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# Try to import ccxt for data downloading
try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False
    print("Warning: ccxt not available for data downloading")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataDownloader:
    """Downloads historical data from various sources"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.raw_dir = os.path.join(data_dir, "raw")
        os.makedirs(self.raw_dir, exist_ok=True)
    
    def download_binance_data(self, 
                            symbol: str, 
                            timeframe: str = '1h',
                            days: int = 365,
                            exchange_name: str = 'binance') -> Optional[str]:
        """Download data from Binance"""
        if not CCXT_AVAILABLE:
            logger.error("ccxt not available for data downloading")
            return None
        
        try:
            # Initialize exchange
            exchange = getattr(ccxt, exchange_name)()
            
            # Calculate start time
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            # Convert timeframe
            tf_mapping = {
                '5T': '5m',
                '15T': '15m', 
                '1H': '1h',
                '4H': '4h',
                '1D': '1d'
            }
            ccxt_timeframe = tf_mapping.get(timeframe, '1h')
            
            # Download data
            logger.info(f"Downloading {symbol} {ccxt_timeframe} data from {days} days ago")
            
            ohlcv = exchange.fetch_ohlcv(
                symbol, 
                ccxt_timeframe, 
                since=int(start_time.timestamp() * 1000),
                limit=1000
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
            
            # Save to CSV
            output_path = os.path.join(self.raw_dir, f"{symbol}_{timeframe}.csv")
            df.to_csv(output_path)
            
            logger.info(f"Downloaded {len(df)} bars for {symbol} {timeframe}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error downloading data for {symbol}: {str(e)}")
            return None
    
    def download_multiple_symbols(self, 
                                symbols: List[str],
                                timeframes: List[str] = ['1H'],
                                days: int = 365) -> Dict[str, str]:
        """Download data for multiple symbols and timeframes"""
        results = {}
        
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    output_path = self.download_binance_data(symbol, timeframe, days)
                    if output_path:
                        results[f"{symbol}_{timeframe}"] = output_path
                        logger.info(f"✓ Downloaded {symbol} {timeframe}")
                    else:
                        logger.warning(f"✗ Failed to download {symbol} {timeframe}")
                        
                except Exception as e:
                    logger.error(f"Error downloading {symbol} {timeframe}: {str(e)}")
                    continue
        
        return results
    
    def create_sample_data(self, symbol: str, days: int = 365) -> str:
        """Create sample data for testing (when no real data available)"""
        try:
            # Generate sample OHLCV data
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            # Create hourly data
            date_range = pd.date_range(start=start_time, end=end_time, freq='1H')
            
            # Generate realistic price data
            np.random.seed(42)  # For reproducible results
            n_bars = len(date_range)
            
            # Start price
            start_price = 50000 if 'BTC' in symbol else 3000 if 'ETH' in symbol else 500
            
            # Generate price series with trend and volatility
            returns = np.random.normal(0.0001, 0.02, n_bars)  # Small positive drift, 2% volatility
            prices = [start_price]
            
            for ret in returns[1:]:
                new_price = prices[-1] * (1 + ret)
                prices.append(max(new_price, 1))  # Ensure positive prices
            
            # Generate OHLCV data
            data = []
            for i, (timestamp, price) in enumerate(zip(date_range, prices)):
                # Generate realistic OHLC from price
                volatility = np.random.uniform(0.001, 0.01)
                high = price * (1 + volatility)
                low = price * (1 - volatility)
                open_price = prices[i-1] if i > 0 else price
                close_price = price
                volume = np.random.uniform(1000, 10000)
                
                data.append({
                    'timestamp': timestamp,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close_price,
                    'volume': volume
                })
            
            # Create DataFrame
            df = pd.DataFrame(data)
            df = df.set_index('timestamp')
            
            # Save to CSV
            output_path = os.path.join(self.raw_dir, f"{symbol}.csv")
            df.to_csv(output_path)
            
            logger.info(f"Created sample data for {symbol}: {len(df)} bars")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating sample data for {symbol}: {str(e)}")
            return ""
    
    def check_data_availability(self, symbols: List[str]) -> Dict[str, bool]:
        """Check if data is available for symbols"""
        availability = {}
        
        for symbol in symbols:
            csv_path = os.path.join(self.raw_dir, f"{symbol}.csv")
            availability[symbol] = os.path.exists(csv_path)
        
        return availability
    
    def download_missing_data(self, symbols: List[str], days: int = 365) -> Dict[str, str]:
        """Download missing data for symbols"""
        results = {}
        
        # Check availability
        availability = self.check_data_availability(symbols)
        
        for symbol in symbols:
            if not availability[symbol]:
                logger.info(f"Downloading missing data for {symbol}")
                
                if CCXT_AVAILABLE:
                    # Try to download real data
                    output_path = self.download_binance_data(symbol, '1h', days)
                    if output_path:
                        results[symbol] = output_path
                    else:
                        # Fallback to sample data
                        logger.warning(f"Real data download failed for {symbol}, creating sample data")
                        output_path = self.create_sample_data(symbol, days)
                        if output_path:
                            results[symbol] = output_path
                else:
                    # Create sample data
                    logger.info(f"Creating sample data for {symbol}")
                    output_path = self.create_sample_data(symbol, days)
                    if output_path:
                        results[symbol] = output_path
            else:
                logger.info(f"Data already available for {symbol}")
                results[symbol] = os.path.join(self.raw_dir, f"{symbol}.csv")
        
        return results

def main():
    """Example usage of DataDownloader"""
    downloader = DataDownloader()
    
    # Check for missing data
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    availability = downloader.check_data_availability(symbols)
    
    print("Data availability:")
    for symbol, available in availability.items():
        print(f"  {symbol}: {'✓' if available else '✗'}")
    
    # Download missing data
    missing_symbols = [s for s, available in availability.items() if not available]
    if missing_symbols:
        print(f"\nDownloading data for: {missing_symbols}")
        results = downloader.download_missing_data(missing_symbols)
        
        print("Download results:")
        for symbol, path in results.items():
            print(f"  {symbol}: {path}")

if __name__ == "__main__":
    main()
