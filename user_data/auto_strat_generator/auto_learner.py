"""
ML Adaptive Learner - Advanced Machine Learning for Strategy Refinement
Uses ensemble methods, feature engineering, and adaptive learning to improve trading strategies
"""

from __future__ import annotations
import json
import os
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor

from .common.logging_utils import setup_logger, get_log_path
from .common.storage import load_latest_artifacts, save_artifact, atomic_write_json
from .common.utils import RESULTS_DIR, STRATS_DIR
from .common.sentiment import compute_indicators


class MLAdaptiveLearner:
    """
    Advanced ML learner that adapts strategy parameters based on market conditions
    and historical performance patterns.
    """
    
    def __init__(self):
        self.logger = setup_logger("ml_adaptive_learner", get_log_path("ml_adaptive_learner.log"))
        self.models_dir = RESULTS_DIR / "ml_models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # ML models
        self.models = {
            "roi_predictor": None,
            "stoploss_predictor": None,
            "entry_timing": None,
            "exit_timing": None
        }
        
        # Feature scalers
        self.scalers = {}
        
        # Learning history
        self.learning_history = []
        
    def run(self) -> Dict[str, Any]:
        """
        Run the complete ML learning process
        
        Returns:
            Learning results and updated strategy parameters
        """
        self.logger.info("🧠 Starting ML Adaptive Learning Process")
        
        try:
            # Load historical data
            market_data = self._load_market_data()
            performance_data = self._load_performance_data()
            
            if market_data.empty or performance_data.empty:
                self.logger.warning("Insufficient data for ML learning, using baseline")
                return self._get_baseline_result()
                
            # Prepare training data
            features, targets = self._prepare_training_data(market_data, performance_data)
            
            if len(features) < 100:  # Need minimum data for reliable ML
                self.logger.warning("Insufficient training data, using baseline")
                return self._get_baseline_result()
                
            # Train models
            training_results = self._train_models(features, targets)
            
            # Generate predictions
            predictions = self._generate_predictions(features)
            
            # Update strategy parameters
            updated_params = self._update_strategy_parameters(predictions)
            
            # Save learning results
            learning_result = {
                "training_results": training_results,
                "predictions": predictions,
                "updated_params": updated_params,
                "learning_timestamp": datetime.utcnow().isoformat(),
                "data_points": len(features)
            }
            
            self._save_learning_results(learning_result)
            
            self.logger.info("✅ ML Adaptive Learning completed successfully")
            return learning_result
            
        except Exception as e:
            self.logger.exception(f"ML learning failed: {e}")
            return self._get_baseline_result()
            
    def _load_market_data(self) -> pd.DataFrame:
        """Load historical market data for feature engineering with memory optimization"""
        try:
            # Try to load from SQLite first
            from .common.storage import fetch_market
            
            pairs = os.getenv("PAIR_WHITELIST", "BTC/USDT,ETH/USDT").split(",")
            timeframe = os.getenv("TIMEFRAME", "5m")
            
            # Limit data loading to prevent memory issues
            max_data_points = int(os.getenv("ML_MAX_DATA_POINTS", "5000"))
            limit_per_pair = max_data_points // len(pairs) if pairs else 1000
            
            all_data = []
            for pair in pairs:
                try:
                    data = fetch_market(pair, timeframe, limit=limit_per_pair)
                    if data:
                        # Process data in chunks to reduce memory usage
                        chunk_size = 500
                        for i in range(0, len(data), chunk_size):
                            chunk = data[i:i + chunk_size]
                            df_chunk = pd.DataFrame([{
                                "timestamp": d.timestamp,
                                "open": d.open,
                                "high": d.high,
                                "low": d.low,
                                "close": d.close,
                                "volume": d.volume,
                                "pair": d.pair
                            } for d in chunk])
                            all_data.append(df_chunk)
                            
                            # Clear chunk from memory
                            del df_chunk
                            
                except Exception as e:
                    self.logger.warning(f"Error loading data for {pair}: {e}")
                    continue
                    
            if all_data:
                # Combine data efficiently
                combined = pd.concat(all_data, ignore_index=True)
                # Clear all_data from memory
                del all_data
                
                # Process indicators in chunks
                result = self._compute_indicators_chunked(combined)
                del combined  # Clear combined from memory
                return result
                
        except Exception as e:
            self.logger.warning(f"Could not load market data: {e}")
            
        return pd.DataFrame()
        
    def _compute_indicators_chunked(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute indicators in chunks to reduce memory usage"""
        try:
            chunk_size = 1000
            result_chunks = []
            
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i + chunk_size].copy()
                chunk_with_indicators = compute_indicators(chunk)
                result_chunks.append(chunk_with_indicators)
                
                # Clear chunk from memory
                del chunk, chunk_with_indicators
                
            if result_chunks:
                result = pd.concat(result_chunks, ignore_index=True)
                del result_chunks
                return result
            else:
                return df
                
        except Exception as e:
            self.logger.warning(f"Error computing indicators: {e}")
            return df
        
    def _load_performance_data(self) -> pd.DataFrame:
        """Load historical performance data"""
        try:
            artifacts = load_latest_artifacts("backtest", limit=50)
            
            performance_data = []
            for artifact in artifacts:
                payload = artifact.payload
                performance_data.append({
                    "timestamp": artifact.created_at.timestamp(),
                    "roi": payload.get("roi", 0.0),
                    "sharpe": payload.get("sharpe", 0.0),
                    "max_drawdown": payload.get("max_drawdown", 0.0),
                    "winrate": payload.get("winrate", 0.0),
                    "confidence": payload.get("confidence", 0.0)
                })
                
            return pd.DataFrame(performance_data)
            
        except Exception as e:
            self.logger.warning(f"Could not load performance data: {e}")
            return pd.DataFrame()
            
    def _prepare_training_data(self, market_data: pd.DataFrame, performance_data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features and targets for ML training"""
        
        # Feature engineering from market data
        features = []
        targets = []
        
        for _, perf_row in performance_data.iterrows():
            # Get market data around this performance period
            timestamp = perf_row["timestamp"]
            window_start = timestamp - 3600  # 1 hour before
            window_end = timestamp + 3600    # 1 hour after
            
            market_window = market_data[
                (market_data["timestamp"] >= window_start) & 
                (market_data["timestamp"] <= window_end)
            ]
            
            if len(market_window) < 10:  # Need minimum data points
                continue
                
            # Extract features
            feature_vector = self._extract_features(market_window)
            if feature_vector is not None:
                features.append(feature_vector)
                
                # Target: ROI improvement potential
                target = perf_row["roi"] + perf_row["sharpe"] * 0.1  # Combined metric
                targets.append(target)
                
        return np.array(features), np.array(targets)
        
    def _extract_features(self, market_window: pd.DataFrame) -> Optional[np.ndarray]:
        """Extract ML features from market window"""
        try:
            features = []
            
            # Price-based features
            features.extend([
                market_window["close"].mean(),
                market_window["close"].std(),
                market_window["close"].pct_change().mean(),
                market_window["close"].pct_change().std(),
                market_window["volume"].mean(),
                market_window["volume"].std()
            ])
            
            # Technical indicators (if available)
            if "rsi" in market_window.columns:
                features.extend([
                    market_window["rsi"].mean(),
                    market_window["rsi"].std(),
                    market_window["rsi"].iloc[-1]  # Latest RSI
                ])
            else:
                features.extend([50.0, 10.0, 50.0])  # Default RSI values
                
            if "ema_fast" in market_window.columns and "ema_slow" in market_window.columns:
                ema_diff = (market_window["ema_fast"] - market_window["ema_slow"]).mean()
                features.append(ema_diff)
            else:
                features.append(0.0)
                
            if "macd_hist" in market_window.columns:
                features.extend([
                    market_window["macd_hist"].mean(),
                    market_window["macd_hist"].std()
                ])
            else:
                features.extend([0.0, 0.0])
                
            if "sentiment_score" in market_window.columns:
                features.extend([
                    market_window["sentiment_score"].mean(),
                    market_window["sentiment_score"].std()
                ])
            else:
                features.extend([0.0, 0.0])
                
            return np.array(features)
            
        except Exception as e:
            self.logger.warning(f"Feature extraction failed: {e}")
            return None
            
    def _train_models(self, features: np.ndarray, targets: np.ndarray) -> Dict[str, Any]:
        """Train ML models for different prediction tasks with memory optimization"""
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, targets, test_size=0.2, random_state=42
        )
        
        # Clear original arrays from memory
        del features, targets
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self.scalers["main"] = scaler
        
        # Clear unscaled data from memory
        del X_train, X_test
        
        training_results = {}
        
        # Train ROI predictor
        roi_model = RandomForestRegressor(n_estimators=100, random_state=42)
        roi_model.fit(X_train_scaled, y_train)
        roi_pred = roi_model.predict(X_test_scaled)
        roi_mse = mean_squared_error(y_test, roi_pred)
        roi_r2 = r2_score(y_test, roi_pred)
        
        self.models["roi_predictor"] = roi_model
        training_results["roi_predictor"] = {
            "mse": roi_mse,
            "r2": roi_r2,
            "feature_importance": roi_model.feature_importances_.tolist()
        }
        
        # Train stoploss predictor (predict optimal stoploss)
        stoploss_targets = np.clip(-y_train * 0.1, -0.2, -0.01)  # Convert ROI to stoploss
        stoploss_model = GradientBoostingRegressor(n_estimators=50, random_state=42)
        stoploss_model.fit(X_train_scaled, stoploss_targets)
        stoploss_pred = stoploss_model.predict(X_test_scaled)
        stoploss_mse = mean_squared_error(stoploss_targets, stoploss_pred)
        
        self.models["stoploss_predictor"] = stoploss_model
        training_results["stoploss_predictor"] = {
            "mse": stoploss_mse,
            "feature_importance": stoploss_model.feature_importances_.tolist()
        }
        
        # Train entry timing model
        entry_model = MLPRegressor(hidden_layer_sizes=(50, 25), random_state=42, max_iter=500)
        entry_targets = np.where(y_train > 0, 1, 0)  # Binary: good entry or not
        entry_model.fit(X_train_scaled, entry_targets)
        
        self.models["entry_timing"] = entry_model
        training_results["entry_timing"] = {
            "model_type": "MLPRegressor",
            "hidden_layers": [50, 25]
        }
        
        # Save models
        self._save_models()
        
        return training_results
        
    def _generate_predictions(self, features: np.ndarray) -> Dict[str, Any]:
        """Generate predictions using trained models"""
        if not self.models["roi_predictor"]:
            return self._get_baseline_predictions()
            
        # Use latest features for prediction
        latest_features = features[-1:] if len(features) > 0 else features
        latest_scaled = self.scalers["main"].transform(latest_features)
        
        predictions = {}
        
        # ROI prediction
        if self.models["roi_predictor"]:
            roi_pred = self.models["roi_predictor"].predict(latest_scaled)[0]
            predictions["predicted_roi"] = float(roi_pred)
            
        # Stoploss prediction
        if self.models["stoploss_predictor"]:
            stoploss_pred = self.models["stoploss_predictor"].predict(latest_scaled)[0]
            predictions["predicted_stoploss"] = float(np.clip(stoploss_pred, -0.2, -0.01))
            
        # Entry timing
        if self.models["entry_timing"]:
            entry_score = self.models["entry_timing"].predict(latest_scaled)[0]
            predictions["entry_score"] = float(entry_score)
            
        return predictions
        
    def _update_strategy_parameters(self, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Update strategy parameters based on ML predictions"""
        
        # Load current best strategy
        best_strategy_path = STRATS_DIR / "best_strategy.json"
        current_params = {}
        
        if best_strategy_path.exists():
            try:
                current_params = json.loads(best_strategy_path.read_text())
                current_params = current_params.get("params", {})
            except Exception:
                pass
                
        # Update parameters based on predictions
        updated_params = current_params.copy()
        
        # Update ROI table based on predicted ROI
        predicted_roi = predictions.get("predicted_roi", 0.05)
        if predicted_roi > 0:
            # Create adaptive ROI table
            roi_table = {
                "0": min(predicted_roi * 1.2, 0.15),  # Immediate ROI
                "60": min(predicted_roi * 0.8, 0.10),  # 1 hour
                "120": min(predicted_roi * 0.6, 0.05), # 2 hours
                "240": min(predicted_roi * 0.4, 0.02)  # 4 hours
            }
            updated_params["minimal_roi"] = roi_table
            
        # Update stoploss based on prediction
        predicted_stoploss = predictions.get("predicted_stoploss", -0.10)
        updated_params["stoploss"] = predicted_stoploss
        
        # Update RSI thresholds based on entry score
        entry_score = predictions.get("entry_score", 0.5)
        if entry_score > 0.7:  # High confidence entry
            updated_params["rsi_buy"] = 45  # More aggressive
            updated_params["rsi_sell"] = 55  # Earlier exit
        elif entry_score < 0.3:  # Low confidence
            updated_params["rsi_buy"] = 65  # More conservative
            updated_params["rsi_sell"] = 35  # Later exit
        else:  # Medium confidence
            updated_params["rsi_buy"] = 55
            updated_params["rsi_sell"] = 45
            
        # Ensure timeframe is set
        updated_params["timeframe"] = os.getenv("TIMEFRAME", "5m")
        
        return updated_params
        
    def _save_models(self) -> None:
        """Save trained models to disk"""
        for model_name, model in self.models.items():
            if model is not None:
                model_path = self.models_dir / f"{model_name}.pkl"
                with open(model_path, "wb") as f:
                    pickle.dump(model, f)
                    
        # Save scalers
        scaler_path = self.models_dir / "scalers.pkl"
        with open(scaler_path, "wb") as f:
            pickle.dump(self.scalers, f)
            
    def _save_learning_results(self, results: Dict[str, Any]) -> None:
        """Save learning results"""
        # Save detailed results
        results_path = RESULTS_DIR / f"ml_learning_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        atomic_write_json(results_path, results)
        
        # Save as latest
        latest_path = RESULTS_DIR / "latest_ml_learning.json"
        atomic_write_json(latest_path, results)
        
        # Save artifact
        save_artifact("ml_learning", "latest", results, score=float(results.get("training_results", {}).get("roi_predictor", {}).get("r2", 0.0)))
        
    def _get_baseline_result(self) -> Dict[str, Any]:
        """Get baseline result when ML learning fails"""
        return {
            "status": "baseline",
            "message": "Using baseline parameters due to insufficient data",
            "updated_params": {
                "timeframe": os.getenv("TIMEFRAME", "5m"),
                "minimal_roi": {"0": 0.10, "60": 0.05, "120": 0.025, "240": 0.0},
                "stoploss": -0.10,
                "trailing_stop": False,
                "rsi_buy": 55,
                "rsi_sell": 45
            },
            "learning_timestamp": datetime.utcnow().isoformat()
        }
        
    def _get_baseline_predictions(self) -> Dict[str, Any]:
        """Get baseline predictions when models are not available"""
        return {
            "predicted_roi": 0.05,
            "predicted_stoploss": -0.10,
            "entry_score": 0.5
        }


def main():
    """Main entry point for ML adaptive learner"""
    learner = MLAdaptiveLearner()
    result = learner.run()
    print(f"ML Learning completed: {result['status']}")


if __name__ == "__main__":
    main()
