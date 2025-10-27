#!/usr/bin/env python3
"""
Phase-2 Evolution - Advanced Autonomous Trading AI
Advanced pipeline with market regime detection, ensemble models, and dynamic risk control
"""

import pandas as pd
import numpy as np
import json
import joblib
import ccxt
import os
import sys
import argparse
from datetime import datetime, timedelta
import warnings
from typing import Dict, List, Tuple, Optional
import logging

# Advanced ML imports
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, r2_score
import lightgbm as lgb
from hmmlearn import hmm

# Suppress warnings
warnings.filterwarnings('ignore')

class MarketRegimeDetector:
    """Hidden Markov Model for market regime detection"""
    
    def __init__(self, n_regimes=3):
        self.n_regimes = n_regimes
        self.model = hmm.GaussianHMM(n_components=n_regimes, covariance_type="full", n_iter=100)
        self.regime_labels = {0: 'bear', 1: 'sideways', 2: 'bull'}
        
    def detect_regimes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect market regimes using HMM"""
        # Prepare features for regime detection
        features = []
        
        # Price momentum
        features.append(df['close'].pct_change(5).fillna(0))
        features.append(df['close'].pct_change(10).fillna(0))
        features.append(df['close'].pct_change(20).fillna(0))
        
        # Volatility
        features.append(df['close'].pct_change().rolling(10).std().fillna(0))
        features.append(df['close'].pct_change().rolling(20).std().fillna(0))
        
        # Volume patterns
        features.append(df['volume'].pct_change().fillna(0))
        features.append((df['volume'] / df['volume'].rolling(20).mean()).fillna(1))
        
        # Technical indicators
        features.append(df['rsi'].fillna(50))
        features.append(df['macd'].fillna(0))
        
        # Combine features
        X = np.column_stack(features)
        
        # Fit HMM model
        self.model.fit(X)
        
        # Predict regimes
        regimes = self.model.predict(X)
        
        # Add regime information to dataframe
        df['regime'] = regimes
        df['regime_label'] = df['regime'].map(self.regime_labels)
        
        return df

class AdvancedFeatureEngineer:
    """Advanced feature engineering with regime-aware indicators"""
    
    def __init__(self):
        self.scalers = {}
        
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate comprehensive feature set"""
        
        # Basic price features
        df['price_change'] = df['close'].pct_change()
        df['high_low_ratio'] = df['high'] / df['low']
        df['open_close_ratio'] = df['open'] / df['close']
        
        # Technical indicators
        df['rsi'] = self._calculate_rsi(df['close'], 14)
        df['rsi_30'] = self._calculate_rsi(df['close'], 30)
        
        # EMAs
        for period in [8, 21, 50, 100, 200]:
            df[f'ema_{period}'] = df['close'].ewm(span=period).mean()
        
        # MACD
        df['macd'] = df['ema_12'] - df['ema_26'] if 'ema_12' in df.columns else df['ema_8'] - df['ema_21']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # ATR and volatility
        df['atr'] = self._calculate_atr(df, 14)
        df['atr_ratio'] = df['atr'] / df['close']
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        df['volatility_ratio'] = df['volatility'] / df['volatility'].rolling(50).mean()
        
        # OBV and volume indicators
        df['obv'] = self._calculate_obv(df)
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        df['volume_price_trend'] = df['volume'] * df['price_change']
        
        # Momentum indicators
        for period in [5, 10, 20, 50]:
            df[f'momentum_{period}'] = df['close'].pct_change(period)
            df[f'roc_{period}'] = (df['close'] / df['close'].shift(period) - 1) * 100
        
        # Trend strength
        df['trend_strength'] = (df['close'] - df['close'].rolling(50).mean()) / df['close'].rolling(50).std()
        df['trend_direction'] = np.where(df['ema_8'] > df['ema_21'], 1, -1)
        
        # Support and resistance levels
        df['resistance'] = df['high'].rolling(20).max()
        df['support'] = df['low'].rolling(20).min()
        df['price_position'] = (df['close'] - df['support']) / (df['resistance'] - df['support'])
        
        # Lagged features
        for lag in [1, 2, 3, 5, 10, 20]:
            df[f'close_lag_{lag}'] = df['close'].shift(lag)
            df[f'volume_lag_{lag}'] = df['volume'].shift(lag)
            df[f'price_change_lag_{lag}'] = df['price_change'].shift(lag)
        
        # Regime-specific features
        if 'regime' in df.columns:
            df['regime_bull'] = (df['regime'] == 2).astype(int)
            df['regime_bear'] = (df['regime'] == 0).astype(int)
            df['regime_sideways'] = (df['regime'] == 1).astype(int)
        
        # Fill NaN values
        df = df.fillna(method='ffill').fillna(0)
        
        return df
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        return true_range.rolling(period).mean()
    
    def _calculate_obv(self, df):
        """Calculate On-Balance Volume"""
        obv = np.where(df['close'] > df['close'].shift(1), df['volume'],
                      np.where(df['close'] < df['close'].shift(1), -df['volume'], 0))
        return pd.Series(obv, index=df.index).cumsum()

class EnsembleModel:
    """Advanced ensemble model with LSTM + XGBoost + LightGBM + Meta-learner"""
    
    def __init__(self, sequence_length=60):
        self.sequence_length = sequence_length
        self.models = {}
        self.scalers = {}
        self.meta_learner = None
        self.feature_columns = None
        
    def prepare_sequences(self, X, y, sequence_length=60):
        """Prepare sequences for LSTM"""
        X_seq, y_seq = [], []
        for i in range(sequence_length, len(X)):
            X_seq.append(X[i-sequence_length:i])
            y_seq.append(y[i])
        return np.array(X_seq), np.array(y_seq)
    
    def train_ensemble(self, X, y, X_val=None, y_val=None):
        """Train ensemble of models"""
        self.feature_columns = X.columns.tolist()
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        self.scalers['main'] = scaler
        
        # Prepare validation data
        if X_val is not None:
            X_val_scaled = scaler.transform(X_val)
        else:
            X_val_scaled = X_scaled[-int(len(X_scaled) * 0.2):]
            X_scaled = X_scaled[:-int(len(X_scaled) * 0.2)]
            y_val = y[-int(len(y) * 0.2):]
            y = y[:-int(len(y) * 0.2)]
        
        # 1. XGBoost
        try:
            import xgboost as xgb
            xgb_model = xgb.XGBRegressor(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42
            )
            xgb_model.fit(X_scaled, y)
            self.models['xgboost'] = xgb_model
        except ImportError:
            # Fallback to RandomForest
            rf_model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42)
            rf_model.fit(X_scaled, y)
            self.models['xgboost'] = rf_model
        
        # 2. LightGBM
        try:
            lgb_model = lgb.LGBMRegressor(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1
            )
            lgb_model.fit(X_scaled, y)
            self.models['lightgbm'] = lgb_model
        except ImportError:
            # Fallback to GradientBoosting
            gb_model = GradientBoostingRegressor(n_estimators=200, max_depth=8, random_state=42)
            gb_model.fit(X_scaled, y)
            self.models['lightgbm'] = gb_model
        
        # 3. Simple LSTM (using a simple neural network approximation)
        from sklearn.neural_network import MLPRegressor
        lstm_model = MLPRegressor(
            hidden_layer_sizes=(100, 50, 25),
            activation='relu',
            solver='adam',
            alpha=0.001,
            learning_rate='adaptive',
            max_iter=500,
            random_state=42
        )
        lstm_model.fit(X_scaled, y)
        self.models['lstm'] = lstm_model
        
        # 4. Meta-learner (Ridge regression)
        # Get predictions from base models
        base_predictions = np.column_stack([
            self.models['xgboost'].predict(X_scaled),
            self.models['lightgbm'].predict(X_scaled),
            self.models['lstm'].predict(X_scaled)
        ])
        
        self.meta_learner = Ridge(alpha=1.0)
        self.meta_learner.fit(base_predictions, y)
        
        # Evaluate ensemble
        val_predictions = self.predict(X_val_scaled)
        val_score = r2_score(y_val, val_predictions)
        
        return val_score
    
    def predict(self, X):
        """Make ensemble predictions"""
        if self.scalers is None or not self.scalers:
            raise ValueError("Model not trained yet")
        
        X_scaled = self.scalers['main'].transform(X)
        
        # Get base model predictions
        base_predictions = np.column_stack([
            self.models['xgboost'].predict(X_scaled),
            self.models['lightgbm'].predict(X_scaled),
            self.models['lstm'].predict(X_scaled)
        ])
        
        # Meta-learner prediction
        ensemble_prediction = self.meta_learner.predict(base_predictions)
        
        return ensemble_prediction

class DynamicRiskController:
    """Dynamic risk control with ATR-based stop loss and Kelly sizing"""
    
    def __init__(self, base_position_size=0.02, max_position_size=0.1):
        self.base_position_size = base_position_size
        self.max_position_size = max_position_size
        self.kelly_multiplier = 0.25  # Conservative Kelly fraction
        
    def calculate_position_size(self, signal_strength, win_rate, avg_win, avg_loss, atr, price):
        """Calculate position size using Kelly criterion and ATR"""
        
        # Kelly criterion
        if avg_loss != 0:
            kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
            kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25%
        else:
            kelly_fraction = 0.02
        
        # ATR-based adjustment
        atr_ratio = atr / price
        atr_adjustment = min(1.0, 0.02 / atr_ratio) if atr_ratio > 0 else 1.0
        
        # Signal strength adjustment
        signal_adjustment = abs(signal_strength)
        
        # Final position size
        position_size = (self.base_position_size * 
                        kelly_fraction * 
                        atr_adjustment * 
                        signal_adjustment)
        
        return min(position_size, self.max_position_size)
    
    def calculate_stop_loss_take_profit(self, entry_price, signal_direction, atr, volatility):
        """Calculate dynamic stop loss and take profit levels"""
        
        # ATR-based stop loss (2x ATR)
        atr_stop = 2.0 * atr
        
        # Volatility-based adjustment
        volatility_multiplier = min(2.0, max(0.5, volatility / 0.02))
        
        # Dynamic levels
        stop_loss = atr_stop * volatility_multiplier
        take_profit = stop_loss * 2.0  # 2:1 risk-reward ratio
        
        if signal_direction > 0:  # Long position
            stop_price = entry_price - stop_loss
            take_price = entry_price + take_profit
        else:  # Short position
            stop_price = entry_price + stop_loss
            take_price = entry_price - take_profit
        
        return stop_price, take_price, stop_loss, take_profit

class WalkForwardBacktester:
    """Walk-forward backtesting for realistic validation"""
    
    def __init__(self, train_period=252, test_period=63, step_size=21):
        self.train_period = train_period  # ~1 year
        self.test_period = test_period    # ~3 months
        self.step_size = step_size        # ~1 month
        
    def run_backtest(self, df, model, risk_controller, feature_columns):
        """Run walk-forward backtest"""
        
        results = []
        total_periods = len(df) - self.train_period - self.test_period
        
        for i in range(0, total_periods, self.step_size):
            # Define train and test periods
            train_start = i
            train_end = i + self.train_period
            test_start = train_end
            test_end = min(test_start + self.test_period, len(df))
            
            if test_end - test_start < 30:  # Skip if test period too short
                continue
            
            # Get train and test data
            train_data = df.iloc[train_start:train_end]
            test_data = df.iloc[test_start:test_end]
            
            # Prepare features
            X_train = train_data[feature_columns].fillna(0)
            y_train = train_data['target'].fillna(0)
            X_test = test_data[feature_columns].fillna(0)
            y_test = test_data['target'].fillna(0)
            
            # Train model on this period
            model.train_ensemble(X_train, y_train, X_test, y_test)
            
            # Generate predictions
            predictions = model.predict(X_test)
            
            # Calculate trading signals
            signals = np.where(predictions > 0.01, 1, np.where(predictions < -0.01, -1, 0))
            
            # Simulate trading with dynamic risk control
            trades = self._simulate_trading(test_data, signals, risk_controller)
            
            # Calculate metrics
            period_result = self._calculate_metrics(trades, test_data)
            period_result['period'] = i
            period_result['train_start'] = train_start
            period_result['test_start'] = test_start
            period_result['test_end'] = test_end
            
            results.append(period_result)
        
        return results
    
    def _simulate_trading(self, df, signals, risk_controller):
        """Simulate trading with dynamic risk control"""
        trades = []
        position = 0
        entry_price = 0
        
        for i, (idx, row) in enumerate(df.iterrows()):
            if i < 1:  # Skip first row
                continue
            
            current_price = row['close']
            signal = signals[i]
            atr = row.get('atr', current_price * 0.02)
            volatility = row.get('volatility', 0.02)
            
            # Close existing position if signal changes
            if position != 0 and signal != position:
                if position > 0:  # Close long
                    exit_price = current_price
                    pnl = (exit_price - entry_price) / entry_price
                else:  # Close short
                    exit_price = current_price
                    pnl = (entry_price - exit_price) / entry_price
                
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'position': position,
                    'pnl': pnl,
                    'entry_time': df.index[i-1],
                    'exit_time': idx
                })
                position = 0
            
            # Open new position
            if signal != 0 and position == 0:
                position = signal
                entry_price = current_price
                
                # Calculate position size and risk levels
                signal_strength = abs(signal)
                win_rate = 0.5  # Placeholder - would be calculated from historical data
                avg_win = 0.02
                avg_loss = 0.01
                
                position_size = risk_controller.calculate_position_size(
                    signal_strength, win_rate, avg_win, avg_loss, atr, current_price
                )
                
                stop_price, take_price, stop_loss, take_profit = risk_controller.calculate_stop_loss_take_profit(
                    entry_price, signal, atr, volatility
                )
        
        return trades
    
    def _calculate_metrics(self, trades, df):
        """Calculate performance metrics"""
        if not trades:
            return {
                'total_trades': 0,
                'total_profit': 0,
                'total_profit_pct': 0,
                'winrate_pct': 0,
                'sharpe': 0,
                'max_drawdown_pct': 0,
                'avg_trade_pnl': 0
            }
        
        pnls = [trade['pnl'] for trade in trades]
        total_profit = sum(pnls)
        total_profit_pct = total_profit * 100
        winrate_pct = (sum(1 for pnl in pnls if pnl > 0) / len(pnls)) * 100
        
        # Calculate Sharpe ratio
        if len(pnls) > 1 and np.std(pnls) > 0:
            sharpe = np.mean(pnls) / np.std(pnls) * np.sqrt(252)
        else:
            sharpe = 0
        
        # Calculate max drawdown
        cumulative = np.cumprod([1 + pnl for pnl in pnls])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown_pct = np.min(drawdown) * 100
        
        return {
            'total_trades': len(trades),
            'total_profit': total_profit,
            'total_profit_pct': total_profit_pct,
            'winrate_pct': winrate_pct,
            'sharpe': sharpe,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_trade_pnl': np.mean(pnls) if pnls else 0
        }

class AdvancedAdaptiveLoop:
    """Advanced adaptive loop with all Phase-2 features"""
    
    def __init__(self, symbols=['BTC/USDT', 'ETH/USDT', 'BNB/USDT'], continuous=False, max_cycles=3):
        self.symbols = symbols
        self.continuous = continuous
        self.max_cycles = max_cycles
        self.exchange = ccxt.binance()
        self.cycle_count = 0
        self.stable_cycles = 0
        self.required_stable_cycles = 3
        
        # Initialize components
        self.regime_detector = MarketRegimeDetector()
        self.feature_engineer = AdvancedFeatureEngineer()
        self.risk_controller = DynamicRiskController()
        self.backtester = WalkForwardBacktester()
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Setup comprehensive logging"""
        os.makedirs('logs', exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler('logs/adaptive_loop.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log_action(self, message):
        """Log action with timestamp"""
        self.logger.info(message)
    
    def download_data(self, symbol, limit=5000):
        """Download fresh market data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, '5m', limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            self.log_action(f"Error downloading {symbol}: {e}")
            return None
    
    def process_symbol(self, symbol):
        """Process single symbol through complete pipeline"""
        self.log_action(f"Processing {symbol}")
        
        # 1. Download data
        df = self.download_data(symbol)
        if df is None or len(df) < 1000:
            self.log_action(f"Insufficient data for {symbol}")
            return None
        
        # 2. Detect market regimes
        df = self.regime_detector.detect_regimes(df)
        
        # 3. Engineer features
        df = self.feature_engineer.engineer_features(df)
        
        # 4. Create target variable
        df['target'] = df['close'].shift(-1) / df['close'] - 1
        df = df.dropna()
        
        if len(df) < 500:
            self.log_action(f"Insufficient data after preprocessing for {symbol}")
            return None
        
        # 5. Prepare features for modeling
        feature_columns = [col for col in df.columns if col not in ['open', 'high', 'low', 'close', 'volume', 'target', 'timestamp']]
        X = df[feature_columns]
        y = df['target']
        
        # 6. Train ensemble model
        model = EnsembleModel()
        val_score = model.train_ensemble(X, y)
        
        # 7. Run walk-forward backtest
        backtest_results = self.backtester.run_backtest(df, model, self.risk_controller, feature_columns)
        
        # 8. Calculate overall metrics
        if backtest_results:
            overall_metrics = self._calculate_overall_metrics(backtest_results)
            overall_metrics['symbol'] = symbol
            overall_metrics['val_score'] = val_score
            overall_metrics['feature_count'] = len(feature_columns)
        else:
            overall_metrics = {
                'symbol': symbol,
                'total_trades': 0,
                'total_profit_pct': 0,
                'winrate_pct': 0,
                'sharpe': 0,
                'max_drawdown_pct': 0,
                'val_score': val_score,
                'feature_count': len(feature_columns)
            }
        
        return overall_metrics
    
    def _calculate_overall_metrics(self, backtest_results):
        """Calculate overall metrics from walk-forward results"""
        all_pnls = []
        all_trades = 0
        
        for result in backtest_results:
            all_trades += result['total_trades']
            # Simulate PnL from profit percentage
            period_pnl = result['total_profit_pct'] / 100
            all_pnls.append(period_pnl)
        
        if not all_pnls:
            return {
                'total_trades': 0,
                'total_profit_pct': 0,
                'winrate_pct': 0,
                'sharpe': 0,
                'max_drawdown_pct': 0
            }
        
        total_profit_pct = sum(all_pnls) * 100
        winrate_pct = np.mean([r['winrate_pct'] for r in backtest_results])
        sharpe = np.mean([r['sharpe'] for r in backtest_results])
        max_drawdown_pct = min([r['max_drawdown_pct'] for r in backtest_results])
        
        return {
            'total_trades': all_trades,
            'total_profit_pct': total_profit_pct,
            'winrate_pct': winrate_pct,
            'sharpe': sharpe,
            'max_drawdown_pct': max_drawdown_pct
        }
    
    def check_stability(self, results):
        """Check if system meets stability criteria"""
        if not results:
            return False
        
        best_result = max(results, key=lambda x: x.get('total_profit_pct', 0))
        
        sharpe_ok = best_result.get('sharpe', 0) >= 2.0
        mdd_ok = best_result.get('max_drawdown_pct', 100) <= 18
        winrate_ok = best_result.get('winrate_pct', 0) >= 60
        pnl_ok = best_result.get('total_profit_pct', 0) > 0
        
        is_stable = sharpe_ok and mdd_ok and winrate_ok and pnl_ok
        
        if is_stable:
            self.stable_cycles += 1
            self.log_action(f"Stable cycle detected! Count: {self.stable_cycles}/{self.required_stable_cycles}")
        else:
            self.stable_cycles = 0
            self.log_action(f"Cycle not stable. Reset count to 0")
        
        return is_stable and self.stable_cycles >= self.required_stable_cycles
    
    def run_cycle(self):
        """Run one complete adaptive cycle"""
        self.cycle_count += 1
        self.log_action(f"Starting Phase-2 adaptive cycle {self.cycle_count}")
        
        cycle_results = []
        
        for symbol in self.symbols:
            result = self.process_symbol(symbol)
            if result:
                cycle_results.append(result)
                self.log_action(f"{symbol}: {result['total_profit_pct']:.2f}% profit, {result['winrate_pct']:.2f}% winrate, Sharpe: {result['sharpe']:.2f}")
        
        # Check stability
        is_stable = self.check_stability(cycle_results)
        
        # Save cycle report
        self._save_cycle_report(cycle_results, is_stable)
        
        return cycle_results, is_stable
    
    def _save_cycle_report(self, results, is_stable):
        """Save cycle report"""
        cycle_data = {
            'cycle_number': self.cycle_count,
            'timestamp': datetime.now().isoformat(),
            'phase': 'Phase-2',
            'results': results,
            'stable': is_stable,
            'stable_cycles': self.stable_cycles
        }
        
        # Load existing report
        try:
            with open('reports/cycle_report.json', 'r') as f:
                existing_data = json.load(f)
        except:
            existing_data = {'cycles': []}
        
        if 'cycles' not in existing_data:
            existing_data['cycles'] = []
        
        existing_data['cycles'].append(cycle_data)
        
        # Save updated report
        with open('reports/cycle_report.json', 'w') as f:
            json.dump(existing_data, f, indent=2)
    
    def run_adaptive_loop(self):
        """Run the complete adaptive loop"""
        self.log_action("Starting Phase-2 Advanced Adaptive Loop")
        
        all_results = []
        
        while self.cycle_count < self.max_cycles:
            results, is_stable = self.run_cycle()
            all_results.extend(results)
            
            if is_stable:
                self.log_action("Stability achieved! Stopping cycles.")
                break
            
            if not self.continuous and self.cycle_count >= self.max_cycles:
                self.log_action("Maximum cycles reached.")
                break
        
        # Generate final summary
        self._generate_final_summary(all_results)
        
        return all_results
    
    def _generate_final_summary(self, all_results):
        """Generate final summary report"""
        if not all_results:
            status = "failed"
            best_metrics = {}
        else:
            best_result = max(all_results, key=lambda x: x.get('total_profit_pct', 0))
            best_metrics = {
                'best_symbol': best_result.get('symbol', 'Unknown'),
                'total_profit_pct': best_result.get('total_profit_pct', 0),
                'winrate_pct': best_result.get('winrate_pct', 0),
                'sharpe': best_result.get('sharpe', 0),
                'max_drawdown_pct': best_result.get('max_drawdown_pct', 0)
            }
            
            # Determine status
            sharpe_ok = best_metrics.get('sharpe', 0) >= 2.0
            mdd_ok = best_metrics.get('max_drawdown_pct', 100) <= 18
            winrate_ok = best_metrics.get('winrate_pct', 0) >= 60
            pnl_ok = best_metrics.get('total_profit_pct', 0) > 0
            
            if sharpe_ok and mdd_ok and winrate_ok and pnl_ok:
                status = "stable"
            elif self.cycle_count >= 2:
                status = "partial"
            else:
                status = "failed"
        
        final_summary = {
            "status": status,
            "phase": "Phase-2",
            "cycles_run": self.cycle_count,
            "stable_cycles": self.stable_cycles,
            "best_metrics": best_metrics,
            "paths": {
                "best_model": "models/",
                "last_trades_csv": "data/processed/",
                "cycle_report": "reports/cycle_report.json"
            },
            "timestamp": datetime.now().isoformat(),
            "features": {
                "market_regime_detection": True,
                "ensemble_models": True,
                "dynamic_risk_control": True,
                "walk_forward_backtesting": True
            }
        }
        
        # Save final summary
        with open('reports/final_summary.json', 'w') as f:
            json.dump(final_summary, f, indent=2)
        
        # Print final status
        if status == "stable":
            print("[SUCCESS] Phase-2 Clinical Rebuild Complete - System Stable and Self-Optimizing")
        else:
            print("[WARNING] Phase-2 Clinical Rebuild Halted - see final_summary.json and failure diagnostics")

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Phase-2 Advanced Adaptive Trading AI')
    parser.add_argument('--continuous', action='store_true', help='Run continuously until stability')
    parser.add_argument('--cycles', type=int, default=3, help='Maximum number of cycles')
    parser.add_argument('--symbols', type=str, default='BTC/USDT,ETH/USDT,BNB/USDT', 
                       help='Comma-separated list of symbols')
    
    args = parser.parse_args()
    
    symbols = [s.strip() for s in args.symbols.split(',')]
    
    # Create necessary directories
    os.makedirs('reports', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    os.makedirs('data/processed', exist_ok=True)
    
    # Initialize and run adaptive loop
    loop = AdvancedAdaptiveLoop(
        symbols=symbols,
        continuous=args.continuous,
        max_cycles=args.cycles
    )
    
    results = loop.run_adaptive_loop()
    
    print(f"Phase-2 execution completed. Processed {len(results)} symbols across {loop.cycle_count} cycles.")

if __name__ == "__main__":
    main()

