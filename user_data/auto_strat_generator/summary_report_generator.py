"""
Summary Report Generator - Creates comprehensive reports after each pipeline phase
"""

from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from .common.logging_utils import setup_logger, get_log_path
from .common.storage import load_latest_artifacts, atomic_write_json
from .common.utils import RESULTS_DIR, LOGS_DIR


class SummaryReportGenerator:
    """
    Generates comprehensive summary reports for each pipeline phase
    """
    
    def __init__(self):
        self.logger = setup_logger("summary_report_generator", get_log_path("summary_report_generator.log"))
        self.console = Console()
        
    def generate_phase_report(self, phase: str, results: Dict[str, Any]) -> Path:
        """
        Generate a detailed report for a specific phase
        
        Args:
            phase: Phase name (hyperopt, backtest, refine, ml_learn)
            results: Phase results data
            
        Returns:
            Path to the generated report file
        """
        self.logger.info(f"Generating {phase} phase report")
        
        report_data = {
            "phase": phase,
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
            "summary": self._generate_phase_summary(phase, results),
            "recommendations": self._generate_recommendations(phase, results),
            "next_steps": self._generate_next_steps(phase)
        }
        
        # Save report
        report_path = RESULTS_DIR / f"{phase}_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        atomic_write_json(report_path, report_data)
        
        # Save as latest
        latest_path = RESULTS_DIR / f"latest_{phase}_report.json"
        atomic_write_json(latest_path, report_data)
        
        # Display report in console
        self._display_phase_report(phase, report_data)
        
        return report_path
        
    def generate_pipeline_summary(self) -> Path:
        """
        Generate a comprehensive pipeline summary report
        
        Returns:
            Path to the generated summary file
        """
        self.logger.info("Generating comprehensive pipeline summary")
        
        # Load all latest artifacts
        phases = ["hyperopt", "backtest", "strategy", "ml_learning"]
        artifacts = {}
        
        for phase in phases:
            phase_artifacts = load_latest_artifacts(phase, limit=1)
            artifacts[phase] = phase_artifacts[0].payload if phase_artifacts else {}
            
        # Generate comprehensive summary
        summary_data = {
            "pipeline_summary": {
                "generated_at": datetime.utcnow().isoformat(),
                "phases_completed": list(artifacts.keys()),
                "overall_status": self._assess_overall_status(artifacts)
            },
            "phase_results": artifacts,
            "performance_analysis": self._analyze_performance(artifacts),
            "strategy_recommendations": self._generate_strategy_recommendations(artifacts),
            "risk_assessment": self._assess_risks(artifacts),
            "next_actions": self._generate_next_actions(artifacts)
        }
        
        # Save comprehensive summary
        summary_path = RESULTS_DIR / f"comprehensive_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        atomic_write_json(summary_path, summary_data)
        
        # Save as latest
        latest_path = RESULTS_DIR / "latest_comprehensive_summary.json"
        atomic_write_json(latest_path, summary_data)
        
        # Display comprehensive summary
        self._display_comprehensive_summary(summary_data)
        
        return summary_path
        
    def _generate_phase_summary(self, phase: str, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary for a specific phase"""
        summaries = {
            "hyperopt": self._summarize_hyperopt(results),
            "backtest": self._summarize_backtest(results),
            "refine": self._summarize_refinement(results),
            "ml_learn": self._summarize_ml_learning(results)
        }
        
        return summaries.get(phase, {"status": "unknown", "message": "No summary available"})
        
    def _summarize_hyperopt(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize hyperopt results"""
        params = results.get("params", {})
        score = results.get("score", 0.0)
        
        return {
            "status": "completed",
            "optimization_score": score,
            "parameters_optimized": len(params),
            "key_parameters": {
                "minimal_roi": params.get("minimal_roi", {}),
                "stoploss": params.get("stoploss", -0.10),
                "trailing_stop": params.get("trailing_stop", False)
            },
            "optimization_quality": "excellent" if score > 0.8 else "good" if score > 0.5 else "needs_improvement"
        }
        
    def _summarize_backtest(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize backtest results"""
        roi = results.get("roi", 0.0)
        sharpe = results.get("sharpe", 0.0)
        max_drawdown = results.get("max_drawdown", 0.0)
        winrate = results.get("winrate", 0.0)
        confidence = results.get("confidence", 0.0)
        
        return {
            "status": "completed",
            "performance_metrics": {
                "roi": roi,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_drawdown,
                "win_rate": winrate,
                "confidence_score": confidence
            },
            "performance_grade": self._grade_performance(roi, sharpe, max_drawdown),
            "risk_level": "low" if max_drawdown < 0.05 else "medium" if max_drawdown < 0.15 else "high"
        }
        
    def _summarize_refinement(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize refinement results"""
        updated_params = results.get("updated_params", {})
        
        return {
            "status": "completed",
            "refinement_type": "rl_based",
            "parameters_updated": len(updated_params),
            "key_changes": {
                "roi_table": updated_params.get("minimal_roi", {}),
                "stoploss": updated_params.get("stoploss", -0.10),
                "rsi_thresholds": {
                    "buy": updated_params.get("rsi_buy", 55),
                    "sell": updated_params.get("rsi_sell", 45)
                }
            },
            "refinement_impact": "significant" if len(updated_params) > 3 else "moderate"
        }
        
    def _summarize_ml_learning(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize ML learning results"""
        training_results = results.get("training_results", {})
        predictions = results.get("predictions", {})
        
        return {
            "status": "completed",
            "learning_type": "adaptive_ml",
            "models_trained": len(training_results),
            "prediction_quality": self._assess_prediction_quality(training_results),
            "key_predictions": predictions,
            "learning_effectiveness": "high" if len(training_results) > 2 else "moderate"
        }
        
    def _generate_recommendations(self, phase: str, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations for a specific phase"""
        recommendations = []
        
        if phase == "hyperopt":
            score = results.get("score", 0.0)
            if score < 0.5:
                recommendations.append("Consider increasing hyperopt epochs for better optimization")
                recommendations.append("Review strategy logic for potential improvements")
            elif score > 0.8:
                recommendations.append("Excellent optimization results - ready for live testing")
                
        elif phase == "backtest":
            roi = results.get("roi", 0.0)
            max_drawdown = results.get("max_drawdown", 0.0)
            
            if roi < 0.02:
                recommendations.append("Low ROI detected - consider strategy refinement")
            if max_drawdown > 0.15:
                recommendations.append("High drawdown risk - implement stricter risk management")
            if roi > 0.05 and max_drawdown < 0.10:
                recommendations.append("Strong performance - suitable for live deployment")
                
        elif phase == "refine":
            recommendations.append("Monitor refined parameters in next backtest")
            recommendations.append("Consider A/B testing refined vs original strategy")
            
        elif phase == "ml_learn":
            recommendations.append("Validate ML predictions with additional market data")
            recommendations.append("Consider ensemble methods for improved accuracy")
            
        return recommendations
        
    def _generate_next_steps(self, phase: str) -> List[str]:
        """Generate next steps for a specific phase"""
        next_steps_map = {
            "hyperopt": [
                "Run backtest with optimized parameters",
                "Validate strategy logic",
                "Prepare for refinement phase"
            ],
            "backtest": [
                "Analyze trade-by-trade results",
                "Run strategy refinement",
                "Prepare for ML learning phase"
            ],
            "refine": [
                "Run updated backtest",
                "Compare refined vs original performance",
                "Prepare for live deployment"
            ],
            "ml_learn": [
                "Validate ML predictions",
                "Update strategy with ML insights",
                "Prepare for final deployment"
            ]
        }
        
        return next_steps_map.get(phase, ["Continue to next phase"])
        
    def _analyze_performance(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall performance across phases"""
        backtest_data = artifacts.get("backtest", {})
        
        analysis = {
            "overall_performance": "unknown",
            "risk_assessment": "unknown",
            "deployment_readiness": "unknown"
        }
        
        if backtest_data:
            roi = backtest_data.get("roi", 0.0)
            sharpe = backtest_data.get("sharpe", 0.0)
            max_drawdown = backtest_data.get("max_drawdown", 0.0)
            
            # Overall performance
            if roi > 0.05 and sharpe > 1.0:
                analysis["overall_performance"] = "excellent"
            elif roi > 0.02 and sharpe > 0.5:
                analysis["overall_performance"] = "good"
            elif roi > 0.0:
                analysis["overall_performance"] = "acceptable"
            else:
                analysis["overall_performance"] = "poor"
                
            # Risk assessment
            if max_drawdown < 0.05:
                analysis["risk_assessment"] = "low"
            elif max_drawdown < 0.15:
                analysis["risk_assessment"] = "medium"
            else:
                analysis["risk_assessment"] = "high"
                
            # Deployment readiness
            if (analysis["overall_performance"] in ["excellent", "good"] and 
                analysis["risk_assessment"] in ["low", "medium"]):
                analysis["deployment_readiness"] = "ready"
            elif analysis["overall_performance"] == "acceptable":
                analysis["deployment_readiness"] = "conditional"
            else:
                analysis["deployment_readiness"] = "not_ready"
                
        return analysis
        
    def _generate_strategy_recommendations(self, artifacts: Dict[str, Any]) -> List[str]:
        """Generate strategy recommendations based on all phases"""
        recommendations = []
        
        backtest_data = artifacts.get("backtest", {})
        hyperopt_data = artifacts.get("hyperopt", {})
        
        if backtest_data and hyperopt_data:
            roi = backtest_data.get("roi", 0.0)
            score = hyperopt_data.get("score", 0.0)
            
            if roi > 0.05 and score > 0.7:
                recommendations.append("Strategy shows strong performance - recommend live deployment")
                recommendations.append("Consider paper trading first to validate live performance")
            elif roi > 0.02:
                recommendations.append("Strategy shows promise - continue optimization")
                recommendations.append("Consider additional hyperopt runs with different parameters")
            else:
                recommendations.append("Strategy needs significant improvement")
                recommendations.append("Review market conditions and strategy logic")
                
        return recommendations
        
    def _assess_risks(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Assess risks based on all phases"""
        backtest_data = artifacts.get("backtest", {})
        
        risk_assessment = {
            "overall_risk": "unknown",
            "key_risks": [],
            "mitigation_strategies": []
        }
        
        if backtest_data:
            max_drawdown = backtest_data.get("max_drawdown", 0.0)
            winrate = backtest_data.get("winrate", 0.0)
            
            # Overall risk
            if max_drawdown > 0.20:
                risk_assessment["overall_risk"] = "high"
                risk_assessment["key_risks"].append("Very high drawdown risk")
                risk_assessment["mitigation_strategies"].append("Implement stricter stop-loss")
            elif max_drawdown > 0.10:
                risk_assessment["overall_risk"] = "medium"
                risk_assessment["key_risks"].append("Moderate drawdown risk")
                risk_assessment["mitigation_strategies"].append("Monitor position sizing")
            else:
                risk_assessment["overall_risk"] = "low"
                
            # Win rate risk
            if winrate < 0.4:
                risk_assessment["key_risks"].append("Low win rate")
                risk_assessment["mitigation_strategies"].append("Improve entry/exit logic")
                
        return risk_assessment
        
    def _generate_next_actions(self, artifacts: Dict[str, Any]) -> List[str]:
        """Generate next actions based on all phases"""
        actions = []
        
        # Check if all phases completed
        completed_phases = [phase for phase, data in artifacts.items() if data]
        
        if len(completed_phases) >= 3:
            actions.append("All major phases completed - ready for live deployment")
            actions.append("Set up monitoring and alerting systems")
            actions.append("Prepare risk management protocols")
        else:
            actions.append("Complete remaining phases before deployment")
            
        # Performance-based actions
        backtest_data = artifacts.get("backtest", {})
        if backtest_data:
            roi = backtest_data.get("roi", 0.0)
            if roi > 0.05:
                actions.append("Strong performance detected - consider increasing position size")
            elif roi < 0.01:
                actions.append("Weak performance - review strategy parameters")
                
        return actions
        
    def _assess_overall_status(self, artifacts: Dict[str, Any]) -> str:
        """Assess overall pipeline status"""
        completed_phases = len([phase for phase, data in artifacts.items() if data])
        total_phases = len(artifacts)
        
        completion_rate = completed_phases / total_phases if total_phases > 0 else 0
        
        if completion_rate >= 0.8:
            return "excellent"
        elif completion_rate >= 0.6:
            return "good"
        elif completion_rate >= 0.4:
            return "fair"
        else:
            return "needs_improvement"
            
    def _grade_performance(self, roi: float, sharpe: float, max_drawdown: float) -> str:
        """Grade performance based on metrics"""
        if roi > 0.05 and sharpe > 1.0 and max_drawdown < 0.10:
            return "A"
        elif roi > 0.03 and sharpe > 0.5 and max_drawdown < 0.15:
            return "B"
        elif roi > 0.01 and sharpe > 0.0 and max_drawdown < 0.20:
            return "C"
        else:
            return "D"
            
    def _assess_prediction_quality(self, training_results: Dict[str, Any]) -> str:
        """Assess ML prediction quality"""
        if not training_results:
            return "unknown"
            
        # Check R² scores
        r2_scores = []
        for model_name, results in training_results.items():
            if "r2" in results:
                r2_scores.append(results["r2"])
                
        if r2_scores:
            avg_r2 = sum(r2_scores) / len(r2_scores)
            if avg_r2 > 0.7:
                return "high"
            elif avg_r2 > 0.4:
                return "medium"
            else:
                return "low"
                
        return "unknown"
        
    def _display_phase_report(self, phase: str, report_data: Dict[str, Any]) -> None:
        """Display phase report in console"""
        summary = report_data["summary"]
        
        table = Table(title=f"📊 {phase.title()} Phase Report")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        if phase == "hyperopt":
            table.add_row("Optimization Score", f"{summary.get('optimization_score', 0.0):.3f}")
            table.add_row("Quality", summary.get('optimization_quality', 'unknown'))
        elif phase == "backtest":
            metrics = summary.get('performance_metrics', {})
            table.add_row("ROI", f"{metrics.get('roi', 0.0):.2%}")
            table.add_row("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0.0):.3f}")
            table.add_row("Max Drawdown", f"{metrics.get('max_drawdown', 0.0):.2%}")
            table.add_row("Win Rate", f"{metrics.get('win_rate', 0.0):.1%}")
            table.add_row("Performance Grade", summary.get('performance_grade', 'N/A'))
            
        self.console.print(table)
        
        # Display recommendations
        recommendations = report_data.get("recommendations", [])
        if recommendations:
            self.console.print(Panel(
                "\n".join(f"• {rec}" for rec in recommendations),
                title="💡 Recommendations"
            ))
            
    def _display_comprehensive_summary(self, summary_data: Dict[str, Any]) -> None:
        """Display comprehensive summary in console"""
        pipeline_info = summary_data["pipeline_summary"]
        performance = summary_data["performance_analysis"]
        
        # Main summary table
        table = Table(title="🎯 Comprehensive Pipeline Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Overall Status", pipeline_info["overall_status"])
        table.add_row("Phases Completed", f"{len(pipeline_info['phases_completed'])}/4")
        table.add_row("Overall Performance", performance["overall_performance"])
        table.add_row("Risk Assessment", performance["risk_assessment"])
        table.add_row("Deployment Readiness", performance["deployment_readiness"])
        
        self.console.print(table)
        
        # Strategy recommendations
        recommendations = summary_data.get("strategy_recommendations", [])
        if recommendations:
            self.console.print(Panel(
                "\n".join(f"• {rec}" for rec in recommendations),
                title="🎯 Strategy Recommendations"
            ))
            
        # Next actions
        actions = summary_data.get("next_actions", [])
        if actions:
            self.console.print(Panel(
                "\n".join(f"• {action}" for action in actions),
                title="🚀 Next Actions"
            ))


def main():
    """Main entry point for summary report generator"""
    generator = SummaryReportGenerator()
    
    # Generate comprehensive summary
    summary_path = generator.generate_pipeline_summary()
    print(f"Comprehensive summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
