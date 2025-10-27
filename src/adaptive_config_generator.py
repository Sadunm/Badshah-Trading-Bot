"""
Adaptive Configuration Generator for Badshah Trading System
Generates adaptive_config.json with safety settings and selected candidates
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdaptiveConfigGenerator:
    """Generates adaptive configuration with safety settings"""
    
    def __init__(self, config_path: str = "adaptive_config.json"):
        self.config_path = config_path
        self.default_safety_settings = {
            "risk_per_trade": 0.005,  # 0.5% per trade
            "max_exposure_per_symbol": 0.15,  # 15% max exposure
            "daily_stop_loss": 0.03,  # 3% daily stop loss
            "max_positions": 5,
            "position_sizing_method": "fixed_risk",
            "slippage": 0.0002,
            "fee": 0.0004
        }
    
    def load_top_candidates(self, candidates_path: str = "reports/candidates_top.json") -> List[Dict]:
        """Load top candidates from evaluation results"""
        try:
            if not os.path.exists(candidates_path):
                logger.warning(f"Top candidates file not found: {candidates_path}")
                return []
            
            with open(candidates_path, 'r') as f:
                data = json.load(f)
            
            candidates = data.get('top_candidates', [])
            logger.info(f"Loaded {len(candidates)} top candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"Error loading top candidates: {str(e)}")
            return []
    
    def load_regime_reports(self, reports_dir: str = "reports") -> Dict:
        """Load regime analysis reports for all symbols"""
        try:
            regime_reports = {}
            
            for filename in os.listdir(reports_dir):
                if filename.startswith('regime_') and filename.endswith('.json'):
                    symbol = filename.replace('regime_', '').replace('.json', '')
                    
                    try:
                        with open(os.path.join(reports_dir, filename), 'r') as f:
                            report = json.load(f)
                        regime_reports[symbol] = report
                    except Exception as e:
                        logger.warning(f"Error loading regime report for {symbol}: {str(e)}")
                        continue
            
            logger.info(f"Loaded regime reports for {len(regime_reports)} symbols")
            return regime_reports
            
        except Exception as e:
            logger.error(f"Error loading regime reports: {str(e)}")
            return {}
    
    def select_candidates_by_regime(self, 
                                  candidates: List[Dict], 
                                  regime_reports: Dict) -> Dict:
        """Select best candidates per symbol and regime"""
        try:
            selected_candidates = {}
            
            # Group candidates by symbol (assuming symbol info is available)
            # For now, we'll use a simple selection strategy
            for candidate in candidates:
                template_name = candidate.get('template_name', 'Unknown')
                composite_score = candidate.get('composite_score', 0.0)
                
                # Create a simple key for now (in practice, you'd have symbol info)
                key = f"{template_name}_{composite_score:.4f}"
                
                if key not in selected_candidates or composite_score > selected_candidates[key]['composite_score']:
                    selected_candidates[key] = {
                        'template_name': template_name,
                        'parameters': candidate.get('parameters', {}),
                        'composite_score': composite_score,
                        'required_tf': candidate.get('required_tf', '1H'),
                        'description': candidate.get('description', '')
                    }
            
            logger.info(f"Selected {len(selected_candidates)} candidates by regime")
            return selected_candidates
            
        except Exception as e:
            logger.error(f"Error selecting candidates by regime: {str(e)}")
            return {}
    
    def generate_adaptive_config(self, 
                               candidates: List[Dict] = None,
                               regime_reports: Dict = None,
                               safety_settings: Dict = None) -> Dict:
        """Generate adaptive configuration"""
        try:
            # Load data if not provided
            if candidates is None:
                candidates = self.load_top_candidates()
            
            if regime_reports is None:
                regime_reports = self.load_regime_reports()
            
            if safety_settings is None:
                safety_settings = self.default_safety_settings.copy()
            
            # Select candidates by regime
            selected_candidates = self.select_candidates_by_regime(candidates, regime_reports)
            
            # Generate configuration
            config = {
                "version": "1.0",
                "generated_at": datetime.utcnow().isoformat(),
                "system_info": {
                    "name": "Badshah Trading System",
                    "description": "Auto Best Strategy Builder Pipeline",
                    "version": "1.0.0"
                },
                "safety_settings": safety_settings,
                "execution_settings": {
                    "auto_start_paper": False,  # Manual approval required
                    "paper_trading_enabled": True,
                    "live_trading_enabled": False,
                    "testnet_connection_required": True
                },
                "selected_candidates": selected_candidates,
                "regime_analysis": regime_reports,
                "symbols": list(regime_reports.keys()),
                "timeframes": ["5T", "15T", "1H", "4H", "1D"],
                "risk_management": {
                    "max_daily_loss": safety_settings["daily_stop_loss"],
                    "max_position_size": safety_settings["max_exposure_per_symbol"],
                    "stop_loss_per_trade": safety_settings["risk_per_trade"],
                    "position_sizing": "fixed_risk"
                },
                "monitoring": {
                    "log_level": "INFO",
                    "performance_tracking": True,
                    "regime_monitoring": True,
                    "alert_thresholds": {
                        "drawdown_warning": 0.15,
                        "drawdown_critical": 0.25,
                        "daily_loss_warning": 0.02,
                        "daily_loss_critical": 0.03
                    }
                },
                "approval_required": {
                    "paper_trading_start": True,
                    "live_trading_start": True,
                    "parameter_changes": True,
                    "risk_adjustments": True
                }
            }
            
            logger.info("Generated adaptive configuration")
            return config
            
        except Exception as e:
            logger.error(f"Error generating adaptive config: {str(e)}")
            return {}
    
    def save_adaptive_config(self, config: Dict) -> None:
        """Save adaptive configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved adaptive configuration to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Error saving adaptive config: {str(e)}")
            raise
    
    def validate_config(self, config: Dict) -> Dict:
        """Validate configuration for safety and completeness"""
        try:
            validation_results = {
                "is_valid": True,
                "warnings": [],
                "errors": [],
                "safety_checks": {}
            }
            
            # Check required sections
            required_sections = ["safety_settings", "execution_settings", "selected_candidates"]
            for section in required_sections:
                if section not in config:
                    validation_results["errors"].append(f"Missing required section: {section}")
                    validation_results["is_valid"] = False
            
            # Check safety settings
            safety_settings = config.get("safety_settings", {})
            safety_checks = {
                "risk_per_trade": safety_settings.get("risk_per_trade", 0) <= 0.01,
                "max_exposure": safety_settings.get("max_exposure_per_symbol", 0) <= 0.15,
                "daily_stop_loss": safety_settings.get("daily_stop_loss", 0) <= 0.03
            }
            
            validation_results["safety_checks"] = safety_checks
            
            # Check if any safety limits are exceeded
            for check, passed in safety_checks.items():
                if not passed:
                    validation_results["warnings"].append(f"Safety limit exceeded: {check}")
            
            # Check execution settings
            execution_settings = config.get("execution_settings", {})
            if execution_settings.get("auto_start_paper", False):
                validation_results["warnings"].append("Auto start enabled - manual approval recommended")
            
            # Check selected candidates
            selected_candidates = config.get("selected_candidates", {})
            if len(selected_candidates) == 0:
                validation_results["warnings"].append("No candidates selected")
            
            logger.info(f"Configuration validation: {'PASSED' if validation_results['is_valid'] else 'FAILED'}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating config: {str(e)}")
            return {"is_valid": False, "errors": [str(e)]}
    
    def generate_summary_report(self, config: Dict) -> Dict:
        """Generate summary report for the configuration"""
        try:
            selected_candidates = config.get("selected_candidates", {})
            regime_reports = config.get("regime_analysis", {})
            safety_settings = config.get("safety_settings", {})
            
            # Count candidates by template
            template_counts = {}
            for candidate in selected_candidates.values():
                template = candidate.get("template_name", "Unknown")
                template_counts[template] = template_counts.get(template, 0) + 1
            
            # Analyze regime distribution
            regime_summary = {}
            for symbol, report in regime_reports.items():
                regime_dist = report.get("regime_distribution", {})
                regime_summary[symbol] = regime_dist
            
            summary = {
                "generated_at": datetime.utcnow().isoformat(),
                "total_candidates": len(selected_candidates),
                "template_distribution": template_counts,
                "symbols_analyzed": len(regime_reports),
                "regime_summary": regime_summary,
                "safety_settings": safety_settings,
                "ready_for_paper": len(selected_candidates) >= 2,  # At least 2 candidates
                "recommendations": []
            }
            
            # Add recommendations
            if len(selected_candidates) < 2:
                summary["recommendations"].append("Need at least 2 candidates for paper trading")
            
            if len(regime_reports) < 2:
                summary["recommendations"].append("Need regime analysis for at least 2 symbols")
            
            if safety_settings.get("risk_per_trade", 0) > 0.01:
                summary["recommendations"].append("Consider reducing risk per trade")
            
            logger.info("Generated configuration summary")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return {}

def main():
    """Example usage of AdaptiveConfigGenerator"""
    generator = AdaptiveConfigGenerator()
    
    # Generate configuration
    config = generator.generate_adaptive_config()
    
    # Validate configuration
    validation = generator.validate_config(config)
    
    # Generate summary
    summary = generator.generate_summary_report(config)
    
    # Save configuration
    generator.save_adaptive_config(config)
    
    print(f"Configuration generated: {len(config.get('selected_candidates', {}))} candidates")
    print(f"Validation: {'PASSED' if validation['is_valid'] else 'FAILED'}")

if __name__ == "__main__":
    main()
