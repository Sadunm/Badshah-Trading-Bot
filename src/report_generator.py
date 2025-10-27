"""
Report Generator for Badshah Trading System
Generates comprehensive reports and final summary
"""

import json
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportGenerator:
    """Generates comprehensive reports for the trading system"""
    
    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = reports_dir
        os.makedirs(reports_dir, exist_ok=True)
    
    def generate_robustness_report(self, 
                                 evaluation_results: List[Dict],
                                 output_path: str = "reports/robustness_report.json") -> Dict:
        """Generate robustness report with walk-forward and Monte Carlo statistics"""
        try:
            robustness_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_candidates": len(evaluation_results),
                "candidate_summaries": [],
                "overall_statistics": {},
                "regime_analysis": {}
            }
            
            # Analyze each candidate
            all_wf_returns = []
            all_mc_returns = []
            all_sharpes = []
            all_drawdowns = []
            
            for result in evaluation_results:
                candidate_summary = {
                    "candidate_id": result.get("candidate_id", "unknown"),
                    "template_name": result.get("template_name", "unknown"),
                    "composite_score": result.get("composite_score", 0.0),
                    "full_backtest": result.get("full_backtest", {}),
                    "walk_forward_stats": self._calculate_wf_stats(result.get("walk_forward_results", [])),
                    "monte_carlo_stats": self._calculate_mc_stats(result.get("monte_carlo_results", []))
                }
                
                robustness_data["candidate_summaries"].append(candidate_summary)
                
                # Collect statistics
                wf_returns = [r.get("total_return_pct", 0) for r in result.get("walk_forward_results", [])]
                mc_returns = [r.get("total_return_pct", 0) for r in result.get("monte_carlo_results", [])]
                sharpes = [r.get("sharpe_ratio", 0) for r in result.get("walk_forward_results", []) if r.get("sharpe_ratio") is not None]
                drawdowns = [r.get("max_drawdown_pct", 0) for r in result.get("walk_forward_results", [])]
                
                all_wf_returns.extend(wf_returns)
                all_mc_returns.extend(mc_returns)
                all_sharpes.extend(sharpes)
                all_drawdowns.extend(drawdowns)
            
            # Overall statistics
            robustness_data["overall_statistics"] = {
                "walk_forward": {
                    "mean_return": np.mean(all_wf_returns) if all_wf_returns else 0,
                    "std_return": np.std(all_wf_returns) if all_wf_returns else 0,
                    "mean_sharpe": np.mean(all_sharpes) if all_sharpes else 0,
                    "mean_drawdown": np.mean(all_drawdowns) if all_drawdowns else 0
                },
                "monte_carlo": {
                    "mean_return": np.mean(all_mc_returns) if all_mc_returns else 0,
                    "std_return": np.std(all_mc_returns) if all_mc_returns else 0
                }
            }
            
            # Save report
            with open(output_path, 'w') as f:
                json.dump(robustness_data, f, indent=2)
            
            logger.info(f"Generated robustness report: {output_path}")
            return robustness_data
            
        except Exception as e:
            logger.error(f"Error generating robustness report: {str(e)}")
            return {}
    
    def _calculate_wf_stats(self, wf_results: List[Dict]) -> Dict:
        """Calculate walk-forward statistics"""
        if not wf_results:
            return {}
        
        returns = [r.get("total_return_pct", 0) for r in wf_results]
        sharpes = [r.get("sharpe_ratio", 0) for r in wf_results if r.get("sharpe_ratio") is not None]
        drawdowns = [r.get("max_drawdown_pct", 0) for r in wf_results]
        
        return {
            "n_folds": len(wf_results),
            "mean_return": np.mean(returns),
            "std_return": np.std(returns),
            "min_return": np.min(returns),
            "max_return": np.max(returns),
            "mean_sharpe": np.mean(sharpes) if sharpes else 0,
            "mean_drawdown": np.mean(drawdowns),
            "consistency": 1 - (np.std(returns) / (np.mean(returns) + 1e-8))
        }
    
    def _calculate_mc_stats(self, mc_results: List[Dict]) -> Dict:
        """Calculate Monte Carlo statistics"""
        if not mc_results:
            return {}
        
        returns = [r.get("total_return_pct", 0) for r in mc_results]
        sharpes = [r.get("sharpe_ratio", 0) for r in mc_results if r.get("sharpe_ratio") is not None]
        drawdowns = [r.get("max_drawdown_pct", 0) for r in mc_results]
        
        return {
            "n_runs": len(mc_results),
            "mean_return": np.mean(returns),
            "std_return": np.std(returns),
            "min_return": np.min(returns),
            "max_return": np.max(returns),
            "percentile_5": np.percentile(returns, 5),
            "percentile_95": np.percentile(returns, 95),
            "mean_sharpe": np.mean(sharpes) if sharpes else 0,
            "mean_drawdown": np.mean(drawdowns)
        }
    
    def generate_final_summary(self, 
                              adaptive_config: Dict,
                              robustness_report: Dict,
                              output_path: str = "reports/final_summary.json") -> Dict:
        """Generate final summary report"""
        try:
            selected_candidates = adaptive_config.get("selected_candidates", {})
            safety_settings = adaptive_config.get("safety_settings", {})
            regime_analysis = adaptive_config.get("regime_analysis", {})
            
            # Calculate pass rate
            total_symbols = len(regime_analysis)
            symbols_with_candidates = len([s for s in regime_analysis.keys() if s in selected_candidates])
            pass_rate = symbols_with_candidates / total_symbols if total_symbols > 0 else 0
            
            # Determine if ready for paper trading
            ready_for_paper = (
                len(selected_candidates) >= 2 and
                pass_rate >= 0.5 and  # At least 50% of symbols have candidates
                safety_settings.get("risk_per_trade", 0) <= 0.01
            )
            
            # Generate summary
            summary = {
                "timestamp": datetime.utcnow().isoformat(),
                "system_status": "ready_for_paper" if ready_for_paper else "not_ready",
                "ready_for_paper": ready_for_paper,
                "verdict": "READY" if ready_for_paper else "NOT READY",
                "reasons": self._generate_verdict_reasons(ready_for_paper, selected_candidates, pass_rate, safety_settings),
                "summary_statistics": {
                    "total_candidates": len(selected_candidates),
                    "symbols_analyzed": total_symbols,
                    "pass_rate": pass_rate,
                    "safety_compliance": self._check_safety_compliance(safety_settings)
                },
                "top_candidates": list(selected_candidates.values())[:3],  # Top 3
                "safety_settings": safety_settings,
                "regime_summary": self._summarize_regimes(regime_analysis),
                "next_steps": self._generate_next_steps(ready_for_paper),
                "approval_required": {
                    "paper_trading_start": True,
                    "live_trading_start": False,
                    "parameter_changes": True
                }
            }
            
            # Save summary
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Generated final summary: {output_path}")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating final summary: {str(e)}")
            return {}
    
    def _generate_verdict_reasons(self, ready: bool, candidates: Dict, pass_rate: float, safety: Dict) -> List[str]:
        """Generate reasons for verdict"""
        reasons = []
        
        if ready:
            reasons.append("✓ Sufficient candidates selected")
            reasons.append("✓ Pass rate meets requirements")
            reasons.append("✓ Safety settings compliant")
        else:
            if len(candidates) < 2:
                reasons.append("✗ Insufficient candidates (need ≥2)")
            if pass_rate < 0.5:
                reasons.append("✗ Low pass rate (need ≥50%)")
            if safety.get("risk_per_trade", 0) > 0.01:
                reasons.append("✗ Risk per trade too high")
        
        return reasons
    
    def _check_safety_compliance(self, safety: Dict) -> Dict:
        """Check safety settings compliance"""
        return {
            "risk_per_trade_ok": safety.get("risk_per_trade", 0) <= 0.01,
            "max_exposure_ok": safety.get("max_exposure_per_symbol", 0) <= 0.15,
            "daily_stop_ok": safety.get("daily_stop_loss", 0) <= 0.03
        }
    
    def _summarize_regimes(self, regime_analysis: Dict) -> Dict:
        """Summarize regime analysis"""
        if not regime_analysis:
            return {}
        
        regime_counts = {}
        for symbol, report in regime_analysis.items():
            regime_dist = report.get("regime_distribution", {})
            for regime, count in regime_dist.items():
                regime_counts[regime] = regime_counts.get(regime, 0) + count
        
        return {
            "total_symbols": len(regime_analysis),
            "regime_distribution": regime_counts,
            "most_common_regime": max(regime_counts.items(), key=lambda x: x[1])[0] if regime_counts else None
        }
    
    def _generate_next_steps(self, ready: bool) -> List[str]:
        """Generate next steps based on readiness"""
        if ready:
            return [
                "1. Review reports/candidates_top.json",
                "2. Review reports/robustness_report.json", 
                "3. Run: bash scripts/start_paper_trading.sh",
                "4. Monitor paper trading performance",
                "5. Adjust parameters if needed"
            ]
        else:
            return [
                "1. Check data quality in data/processed/",
                "2. Review regime analysis in reports/",
                "3. Adjust strategy parameters",
                "4. Re-run evaluation pipeline",
                "5. Check safety settings"
            ]
    
    def generate_cycle_report(self, 
                            cycle_data: Dict,
                            output_path: str = "reports/cycle_report.json") -> None:
        """Generate cycle report (appendable)"""
        try:
            cycle_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "cycle_data": cycle_data
            }
            
            # Append to cycle report
            if os.path.exists(output_path):
                with open(output_path, 'r') as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
                existing_data.append(cycle_entry)
            else:
                existing_data = [cycle_entry]
            
            with open(output_path, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            logger.info(f"Appended cycle report: {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating cycle report: {str(e)}")
    
    def log_sequence_step(self, 
                         step: str,
                         status: str,
                         details: str,
                         file_outputs: List[str] = None,
                         log_path: str = "logs/sequence_runner.log") -> None:
        """Log sequence step to runner log"""
        try:
            log_entry = {
                "step": step,
                "status": status,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
                "file_outputs": file_outputs or []
            }
            
            # Ensure logs directory exists
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            
            # Append to log file
            with open(log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            logger.info(f"Logged step: {step} - {status}")
            
        except Exception as e:
            logger.error(f"Error logging sequence step: {str(e)}")

def main():
    """Example usage of ReportGenerator"""
    generator = ReportGenerator()
    
    # Example: Generate reports
    # robustness_report = generator.generate_robustness_report(evaluation_results)
    # final_summary = generator.generate_final_summary(adaptive_config, robustness_report)
    
    print("Report generator ready")

if __name__ == "__main__":
    main()
