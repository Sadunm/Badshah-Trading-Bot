"""
Meta-learner for Badshah Trading System
Optional LightGBM model for candidate ranking assistance
"""

import pandas as pd
import numpy as np
import json
import os
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime

# Try to import LightGBM and SHAP
try:
    import lightgbm as lgb
    import shap
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("Warning: LightGBM or SHAP not available, meta-learner disabled")

from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_squared_error, r2_score
import joblib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetaLearner:
    """LightGBM meta-learner for candidate ranking assistance"""
    
    def __init__(self, model_path: str = "models/meta_learner.joblib"):
        self.model_path = model_path
        self.model = None
        self.feature_names = []
        self.is_trained = False
        
        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available, meta-learner disabled")
    
    def extract_features(self, evaluation_results: List) -> pd.DataFrame:
        """Extract meta-features from evaluation results"""
        try:
            features = []
            
            for result in evaluation_results:
                # Basic strategy features
                feature_dict = {
                    'template_name': result.template_name,
                    'n_parameters': len(result.parameters),
                    'parameter_values': list(result.parameters.values())
                }
                
                # Backtest metrics
                backtest = result.full_backtest
                feature_dict.update({
                    'total_trades': backtest.total_trades,
                    'total_return_pct': backtest.total_return_pct,
                    'winrate_pct': backtest.winrate_pct,
                    'avg_trade_pnl': backtest.avg_trade_pnl,
                    'sharpe_ratio': backtest.sharpe_ratio,
                    'max_drawdown_pct': backtest.max_drawdown_pct,
                    'expectancy': backtest.expectancy,
                    'profit_factor': backtest.profit_factor
                })
                
                # Walk-forward metrics
                if result.walk_forward_results:
                    wf_returns = [r.total_return_pct for r in result.walk_forward_results]
                    wf_sharpes = [r.sharpe_ratio for r in result.walk_forward_results if r.sharpe_ratio is not None]
                    wf_drawdowns = [r.max_drawdown_pct for r in result.walk_forward_results]
                    
                    feature_dict.update({
                        'wf_mean_return': np.mean(wf_returns),
                        'wf_std_return': np.std(wf_returns),
                        'wf_mean_sharpe': np.mean(wf_sharpes) if wf_sharpes else 0,
                        'wf_mean_drawdown': np.mean(wf_drawdowns),
                        'wf_consistency': 1 - np.std(wf_returns) / (np.mean(wf_returns) + 1e-8)
                    })
                else:
                    feature_dict.update({
                        'wf_mean_return': 0,
                        'wf_std_return': 0,
                        'wf_mean_sharpe': 0,
                        'wf_mean_drawdown': 0,
                        'wf_consistency': 0
                    })
                
                # Monte Carlo metrics
                if result.monte_carlo_results:
                    mc_returns = [r.total_return_pct for r in result.monte_carlo_results]
                    mc_sharpes = [r.sharpe_ratio for r in result.monte_carlo_results if r.sharpe_ratio is not None]
                    mc_drawdowns = [r.max_drawdown_pct for r in result.monte_carlo_results]
                    
                    feature_dict.update({
                        'mc_mean_return': np.mean(mc_returns),
                        'mc_std_return': np.std(mc_returns),
                        'mc_mean_sharpe': np.mean(mc_sharpes) if mc_sharpes else 0,
                        'mc_mean_drawdown': np.mean(mc_drawdowns),
                        'mc_consistency': 1 - np.std(mc_returns) / (np.mean(mc_returns) + 1e-8)
                    })
                else:
                    feature_dict.update({
                        'mc_mean_return': 0,
                        'mc_std_return': 0,
                        'mc_mean_sharpe': 0,
                        'mc_mean_drawdown': 0,
                        'mc_consistency': 0
                    })
                
                # Composite score as target
                feature_dict['composite_score'] = result.composite_score
                
                features.append(feature_dict)
            
            # Convert to DataFrame
            df = pd.DataFrame(features)
            
            # Encode categorical features
            if 'template_name' in df.columns:
                df = pd.get_dummies(df, columns=['template_name'], prefix='template')
            
            # Handle parameter values (flatten list)
            if 'parameter_values' in df.columns:
                # Extract individual parameter values
                max_params = max(len(pv) for pv in df['parameter_values']) if len(df) > 0 else 0
                for i in range(max_params):
                    df[f'param_{i}'] = df['parameter_values'].apply(lambda x: x[i] if i < len(x) else 0)
                df = df.drop('parameter_values', axis=1)
            
            logger.info(f"Extracted {len(df)} feature vectors with {len(df.columns)} features")
            return df
            
        except Exception as e:
            logger.error(f"Error extracting features: {str(e)}")
            return pd.DataFrame()
    
    def train_model(self, evaluation_results: List, test_size: float = 0.2) -> Dict:
        """Train LightGBM meta-learner"""
        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available, skipping training")
            return {'error': 'LightGBM not available'}
        
        try:
            # Extract features
            df = self.extract_features(evaluation_results)
            
            if len(df) < 10:
                logger.warning(f"Insufficient data for training: {len(df)} samples")
                return {'error': 'Insufficient data for training'}
            
            # Prepare features and target
            feature_cols = [col for col in df.columns if col != 'composite_score']
            X = df[feature_cols]
            y = df['composite_score']
            
            # Store feature names
            self.feature_names = feature_cols
            
            # Train-test split
            split_idx = int(len(df) * (1 - test_size))
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
            
            # Train LightGBM model
            train_data = lgb.Dataset(X_train, label=y_train)
            
            params = {
                'objective': 'regression',
                'metric': 'rmse',
                'boosting_type': 'gbdt',
                'num_leaves': 31,
                'learning_rate': 0.05,
                'feature_fraction': 0.9,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'verbose': -1
            }
            
            self.model = lgb.train(
                params,
                train_data,
                num_boost_round=100,
                valid_sets=[train_data],
                callbacks=[lgb.early_stopping(10)]
            )
            
            # Evaluate model
            y_pred = self.model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            # Cross-validation
            cv_scores = cross_val_score(
                lgb.LGBMRegressor(**params),
                X, y, cv=5, scoring='neg_mean_squared_error'
            )
            
            # Save model
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            
            self.is_trained = True
            
            training_results = {
                'model_trained': True,
                'n_samples': len(df),
                'n_features': len(feature_cols),
                'test_mse': mse,
                'test_r2': r2,
                'cv_mse_mean': -cv_scores.mean(),
                'cv_mse_std': cv_scores.std(),
                'feature_names': feature_cols
            }
            
            logger.info(f"Meta-learner trained: R² = {r2:.4f}, MSE = {mse:.4f}")
            return training_results
            
        except Exception as e:
            logger.error(f"Error training meta-learner: {str(e)}")
            return {'error': str(e)}
    
    def predict_scores(self, evaluation_results: List) -> List[float]:
        """Predict composite scores using trained model"""
        if not self.is_trained or self.model is None:
            logger.warning("Model not trained, returning original scores")
            return [r.composite_score for r in evaluation_results]
        
        try:
            # Extract features
            df = self.extract_features(evaluation_results)
            
            if len(df) == 0:
                return [r.composite_score for r in evaluation_results]
            
            # Prepare features
            feature_cols = [col for col in df.columns if col != 'composite_score']
            X = df[feature_cols]
            
            # Ensure feature order matches training
            X = X.reindex(columns=self.feature_names, fill_value=0)
            
            # Predict scores
            predicted_scores = self.model.predict(X)
            
            logger.info(f"Predicted scores for {len(predicted_scores)} candidates")
            return predicted_scores.tolist()
            
        except Exception as e:
            logger.error(f"Error predicting scores: {str(e)}")
            return [r.composite_score for r in evaluation_results]
    
    def explain_predictions(self, evaluation_results: List, top_n: int = 5) -> Dict:
        """Generate SHAP explanations for predictions"""
        if not LIGHTGBM_AVAILABLE or not self.is_trained:
            return {'error': 'SHAP explanations not available'}
        
        try:
            # Extract features for top candidates
            top_results = evaluation_results[:top_n]
            df = self.extract_features(top_results)
            
            if len(df) == 0:
                return {'error': 'No data for explanations'}
            
            # Prepare features
            feature_cols = [col for col in df.columns if col != 'composite_score']
            X = df[feature_cols]
            X = X.reindex(columns=self.feature_names, fill_value=0)
            
            # Calculate SHAP values
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(X)
            
            # Create explanations
            explanations = []
            for i, result in enumerate(top_results):
                explanation = {
                    'candidate_id': result.candidate_id,
                    'template_name': result.template_name,
                    'predicted_score': self.model.predict(X.iloc[[i]])[0],
                    'feature_importance': dict(zip(self.feature_names, shap_values[i]))
                }
                explanations.append(explanation)
            
            # Global feature importance
            global_importance = dict(zip(self.feature_names, np.abs(shap_values).mean(axis=0)))
            
            shap_results = {
                'explanations': explanations,
                'global_importance': global_importance,
                'top_features': sorted(global_importance.items(), key=lambda x: x[1], reverse=True)[:10]
            }
            
            # Save SHAP results
            shap_path = "reports/meta_shap.json"
            with open(shap_path, 'w') as f:
                json.dump(shap_results, f, indent=2)
            
            logger.info(f"Generated SHAP explanations for {len(explanations)} candidates")
            return shap_results
            
        except Exception as e:
            logger.error(f"Error generating SHAP explanations: {str(e)}")
            return {'error': str(e)}
    
    def load_model(self) -> bool:
        """Load trained model from file"""
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                logger.info(f"Loaded meta-learner from {self.model_path}")
                return True
            else:
                logger.warning(f"Model file not found: {self.model_path}")
                return False
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False
    
    def save_model_info(self, training_results: Dict) -> None:
        """Save model information and training results"""
        try:
            model_info = {
                'timestamp': datetime.utcnow().isoformat(),
                'model_path': self.model_path,
                'is_trained': self.is_trained,
                'training_results': training_results,
                'feature_names': self.feature_names
            }
            
            info_path = "reports/meta_learner_info.json"
            with open(info_path, 'w') as f:
                json.dump(model_info, f, indent=2)
            
            logger.info(f"Saved model info to {info_path}")
            
        except Exception as e:
            logger.error(f"Error saving model info: {str(e)}")

def main():
    """Example usage of MetaLearner"""
    meta_learner = MetaLearner()
    
    # Example: Train meta-learner
    # results = load_evaluation_results('reports/candidates_all.json')
    # training_results = meta_learner.train_model(results)
    # meta_learner.save_model_info(training_results)
    
    # Example: Generate explanations
    # explanations = meta_learner.explain_predictions(results, top_n=5)

if __name__ == "__main__":
    main()
