"""
Unified Orchestrator - Master Controller for the Complete Trading Pipeline
Handles the full workflow: Hyperopt → Refine → Backtest → ML Learn → Summary Save
"""

from __future__ import annotations
import asyncio
import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from tenacity import retry, stop_after_attempt, wait_exponential

from .common.logging_utils import setup_logger, get_log_path
from .common.storage import init_db, save_artifact, load_latest_artifacts, atomic_write_json
from .common.utils import ensure_dirs, load_env, DATA_DIR, RESULTS_DIR, LOGS_DIR, STRATS_DIR
from .common.validator import validate_environment
from .auto_market_observer import MarketObserver
from .auto_hyperopt_orchestrator import HyperoptOrchestrator
from .auto_backtest_runner import BacktestRunner
from .auto_refiner import StrategyRefiner
from .auto_live_executor import LiveExecutor
from .auto_learner import MLAdaptiveLearner


class UnifiedOrchestrator:
    """
    Master controller for the complete trading pipeline.
    Orchestrates: Hyperopt → Refine → Backtest → ML Learn → Summary Save
    """
    
    def __init__(self):
        self.console = Console()
        self.logger = setup_logger("unified_orchestrator", get_log_path("unified_orchestrator.log"))
        self.errlog = setup_logger("orchestrator_errors", get_log_path("orchestrator_errors.log"))
        
        # Pipeline configuration
        self.pipeline_steps = [
            "market_observe",
            "hyperopt", 
            "backtest",
            "refine",
            "ml_learn",
            "summary_save",
            "live_deploy"
        ]
        
        # Results tracking
        self.pipeline_results: Dict[str, Any] = {}
        self.start_time = datetime.utcnow()
        
        # Ensure all directories exist
        self._ensure_directories()
        
        # Initialize database
        init_db()
        
    def _ensure_directories(self) -> None:
        """Ensure all required directories exist"""
        required_dirs = [
            DATA_DIR,
            RESULTS_DIR,
            LOGS_DIR,
            STRATS_DIR,
            DATA_DIR / "hyperopts",
            DATA_DIR / "backtest_results",
            DATA_DIR / "plot",
            DATA_DIR / "notebooks"
        ]
        ensure_dirs(required_dirs)
        
    def run_full_pipeline(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Execute the complete trading pipeline
        
        Args:
            dry_run: If True, skip live deployment
            
        Returns:
            Complete pipeline results
        """
        self.logger.info("🚀 Starting Unified Trading Pipeline")
        self.console.print(Panel.fit(
            "[bold blue]🤖 Unified Trading Pipeline Starting[/bold blue]\n"
            f"Timestamp: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Dry Run: {dry_run}",
            title="Pipeline Status"
        ))
        
        try:
            # Validate environment first
            self._validate_environment()
            self._check_strategy_presence()
            
            # Execute pipeline steps
            for step in self.pipeline_steps:
                if step == "live_deploy" and dry_run:
                    self.logger.info("Skipping live deployment (dry run mode)")
                    continue
                    
                self._execute_step(step)

                # Self-intelligence trigger: after backtest, check KPIs and auto-run hyperopt+ML if degraded
                if step == "backtest":
                    if self._should_retrain():
                        self.logger.info("📉 Performance degraded (ROI/MDD). Triggering auto hyperopt + ML...")
                        self._execute_step("hyperopt")
                        self._execute_step("refine")
                        self._execute_step("ml_learn")
                
            # Generate final summary
            summary = self._generate_final_summary()
            
            self.logger.info("✅ Pipeline completed successfully")
            self._display_success_summary(summary)
            
            return summary
            
        except Exception as e:
            self.errlog.exception(f"Pipeline failed: {e}")
            self.console.print(f"[bold red]❌ Pipeline failed: {e}[/bold red]")
            raise
            
    def _validate_environment(self) -> None:
        """Validate environment and dependencies"""
        self.logger.info("🔍 Validating environment...")
        validate_environment()
        self.logger.info("✅ Environment validation passed")

    def _check_strategy_presence(self) -> None:
        """Warn user to run hyperopt if no strategy file exists."""
        try:
            strat_files = list(STRATS_DIR.glob("*.py"))
            if not strat_files:
                self.logger.warning("No strategy file found in strategies folder. Please run hyperopt_and_ml.bat first.")
        except Exception:
            pass
        
    def _execute_step(self, step: str) -> None:
        """Execute a single pipeline step with retry logic"""
        self.logger.info(f"🔄 Executing step: {step}")
        
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[bold blue]{step}[/bold blue]"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task(f"Running {step}", total=None)
            
            try:
                if step == "market_observe":
                    result = self._run_market_observation()
                elif step == "hyperopt":
                    result = self._run_hyperopt()
                elif step == "backtest":
                    result = self._run_backtest()
                elif step == "refine":
                    result = self._run_refinement()
                elif step == "ml_learn":
                    result = self._run_ml_learning()
                elif step == "summary_save":
                    result = self._run_summary_save()
                elif step == "live_deploy":
                    result = self._run_live_deployment()
                else:
                    raise ValueError(f"Unknown step: {step}")
                    
                self.pipeline_results[step] = result
                progress.update(task, completed=True)
                self.logger.info(f"✅ Step {step} completed successfully")
                
            except Exception as e:
                self.errlog.exception(f"Step {step} failed: {e}")
                raise
                
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=60))
    def _run_market_observation(self) -> Dict[str, Any]:
        """Run market observation step"""
        pairs = os.getenv("PAIR_WHITELIST", "BTC/USDT,ETH/USDT").split(",")
        observer = MarketObserver(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_API_SECRET"),
            quote=os.getenv("QUOTE", "USDT"),
            timeframe=os.getenv("TIMEFRAME", "5m"),
            pairs=pairs
        )
        
        observer.fetch_snapshot()
        
        return {
            "status": "success",
            "pairs_observed": len(pairs),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=60))
    def _run_hyperopt(self) -> Dict[str, Any]:
        """Run hyperoptimization step"""
        orchestrator = HyperoptOrchestrator()
        result_path = orchestrator.run()
        
        return {
            "status": "success",
            "result_path": str(result_path),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=60))
    def _run_backtest(self) -> Dict[str, Any]:
        """Run backtesting step"""
        runner = BacktestRunner()
        result_path = runner.run()
        
        return {
            "status": "success",
            "result_path": str(result_path),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=60))
    def _run_refinement(self) -> Dict[str, Any]:
        """Run strategy refinement step"""
        refiner = StrategyRefiner()
        result_path = refiner.run()
        
        return {
            "status": "success",
            "result_path": str(result_path),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=60))
    def _run_ml_learning(self) -> Dict[str, Any]:
        """Run ML adaptive learning step"""
        learner = MLAdaptiveLearner()
        result = learner.run()
        
        return {
            "status": "success",
            "learning_result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    def _run_summary_save(self) -> Dict[str, Any]:
        """Save comprehensive pipeline summary"""
        summary = self._generate_final_summary()
        
        # Save to multiple formats
        summary_path = RESULTS_DIR / f"pipeline_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        atomic_write_json(summary_path, summary)
        
        # Save as latest
        latest_path = RESULTS_DIR / "latest_pipeline_summary.json"
        atomic_write_json(latest_path, summary)
        
        # Save artifact
        save_artifact("pipeline", "latest", summary, score=float(summary.get("overall_score", 0.0)))
        
        return {
            "status": "success",
            "summary_path": str(summary_path),
            "latest_path": str(latest_path),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=60))
    def _run_live_deployment(self) -> Dict[str, Any]:
        """Run live deployment step"""
        executor = LiveExecutor()
        executor.run()
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    def _generate_final_summary(self) -> Dict[str, Any]:
        """Generate comprehensive pipeline summary"""
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()
        
        # Load latest artifacts
        hyperopt_arts = load_latest_artifacts("hyperopt", limit=1)
        backtest_arts = load_latest_artifacts("backtest", limit=1)
        strategy_arts = load_latest_artifacts("strategy", limit=1)
        
        summary = {
            "pipeline_info": {
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "steps_completed": list(self.pipeline_results.keys()),
                "overall_status": "success"
            },
            "step_results": self.pipeline_results,
            "latest_artifacts": {
                "hyperopt": hyperopt_arts[0].payload if hyperopt_arts else {},
                "backtest": backtest_arts[0].payload if backtest_arts else {},
                "strategy": strategy_arts[0].payload if strategy_arts else {}
            },
            "performance_metrics": self._calculate_performance_metrics(),
            "overall_score": self._calculate_overall_score()
        }
        
        return summary
        
    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calculate overall performance metrics"""
        metrics = {
            "total_steps": len(self.pipeline_steps),
            "completed_steps": len(self.pipeline_results),
            "success_rate": len(self.pipeline_results) / len(self.pipeline_steps),
            "pipeline_duration": (datetime.utcnow() - self.start_time).total_seconds()
        }
        
        # Add step-specific metrics if available
        if "backtest" in self.pipeline_results:
            backtest_arts = load_latest_artifacts("backtest", limit=1)
            if backtest_arts:
                backtest_data = backtest_arts[0].payload
                metrics.update({
                    "roi": backtest_data.get("roi", 0.0),
                    "sharpe": backtest_data.get("sharpe", 0.0),
                    "max_drawdown": backtest_data.get("max_drawdown", 0.0),
                    "winrate": backtest_data.get("winrate", 0.0)
                })
                
        return metrics
        
    def _calculate_overall_score(self) -> float:
        """Calculate overall pipeline score"""
        score = 0.0
        
        # Base score for completion
        completion_rate = len(self.pipeline_results) / len(self.pipeline_steps)
        score += completion_rate * 0.3
        
        # Performance score from backtest
        backtest_arts = load_latest_artifacts("backtest", limit=1)
        if backtest_arts:
            backtest_data = backtest_arts[0].payload
            roi = backtest_data.get("roi", 0.0)
            sharpe = backtest_data.get("sharpe", 0.0)
            score += min(roi * 0.1, 0.3)  # Cap ROI contribution
            score += min(sharpe * 0.1, 0.2)  # Cap Sharpe contribution
            
        return min(score, 1.0)  # Cap at 1.0

    def _should_retrain(self) -> bool:
        """Decide whether to trigger auto hyperopt/ML based on latest backtest KPIs."""
        try:
            # Thresholds (conservative to avoid overfitting during demo)
            min_roi = float(os.getenv("RETRAIN_MIN_ROI", "0.0"))  # e.g., 0.0 means retrain on negative ROI
            max_mdd = float(os.getenv("RETRAIN_MAX_MDD", "0.2"))  # 20% drawdown threshold
            min_sharpe = float(os.getenv("RETRAIN_MIN_SHARPE", "0.0"))

            backtest_arts = load_latest_artifacts("backtest", limit=1)
            if not backtest_arts:
                return False

            kpis = backtest_arts[0].payload
            roi = float(kpis.get("roi", 0.0))
            mdd = float(kpis.get("max_drawdown", 0.0))
            sharpe = float(kpis.get("sharpe", 0.0))

            if roi < min_roi or mdd > max_mdd or sharpe < min_sharpe:
                return True
        except Exception:
            return False
        return False
        
    def _display_success_summary(self, summary: Dict[str, Any]) -> None:
        """Display success summary in console"""
        metrics = summary["performance_metrics"]
        
        table = Table(title="🎉 Pipeline Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Duration", f"{metrics['pipeline_duration']:.1f}s")
        table.add_row("Steps Completed", f"{metrics['completed_steps']}/{metrics['total_steps']}")
        table.add_row("Success Rate", f"{metrics['success_rate']:.1%}")
        table.add_row("Overall Score", f"{summary['overall_score']:.3f}")
        
        if "roi" in metrics:
            table.add_row("ROI", f"{metrics['roi']:.2%}")
            table.add_row("Sharpe Ratio", f"{metrics['sharpe']:.3f}")
            table.add_row("Max Drawdown", f"{metrics['max_drawdown']:.2%}")
            table.add_row("Win Rate", f"{metrics['winrate']:.1%}")
            
        self.console.print(table)
        
    def run_continuous(self, dry_run: bool = True, cooldown_hours: int = 1) -> None:
        """Run pipeline continuously with cooldown"""
        self.logger.info(f"🔄 Starting continuous pipeline (cooldown: {cooldown_hours}h)")
        
        while True:
            try:
                self.run_full_pipeline(dry_run=dry_run)
                
                # Cooldown period
                cooldown_seconds = cooldown_hours * 3600
                self.logger.info(f"😴 Cooldown for {cooldown_hours} hours...")
                time.sleep(cooldown_seconds)
                
            except KeyboardInterrupt:
                self.logger.info("🛑 Pipeline stopped by user")
                break
            except Exception as e:
                self.errlog.exception(f"Continuous pipeline error: {e}")
                self.logger.info(f"⏳ Retrying in 5 minutes...")
                time.sleep(300)  # 5 minute retry delay


def main():
    """Main entry point for unified orchestrator"""
    load_env()
    
    # Parse command line arguments
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    continuous = "--continuous" in sys.argv
    cooldown_hours = 1
    
    if "--cooldown" in sys.argv:
        try:
            idx = sys.argv.index("--cooldown")
            cooldown_hours = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            pass
            
    orchestrator = UnifiedOrchestrator()
    
    if continuous:
        orchestrator.run_continuous(dry_run=dry_run, cooldown_hours=cooldown_hours)
    else:
        orchestrator.run_full_pipeline(dry_run=dry_run)


if __name__ == "__main__":
    main()
