from __future__ import annotations
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .common.logging_utils import setup_logger, get_log_path
from .common.storage import atomic_write_json, save_artifact
from .common.utils import STRATS_DIR, RESULTS_DIR
from .common.subprocess_wrapper import SafeSubprocessWrapper


class BacktestRunner:
	def __init__(self):
		self.logger = setup_logger("auto_backtest_runner", get_log_path("auto_backtest_runner.log"))
		self.strategy_name = "AutoGenStrategy"
		self.subprocess_wrapper = SafeSubprocessWrapper("backtest_runner")

	def run(self) -> Path:
		strategy_file = STRATS_DIR / f"{self.strategy_name}.py"
		if not strategy_file.exists():
			raise FileNotFoundError("Strategy file missing; run hyperopt first")
		out = self._run_freqtrade_backtest()
		summary = self._compute_summary(out)
		path = RESULTS_DIR / "backtest_summary.json"
		atomic_write_json(path, summary)
		save_artifact("backtest", "latest", summary, score=float(summary.get("confidence", 0.0)))
		self.logger.info(f"Backtest summary written to {path}")
		return path

	def _run_freqtrade_backtest(self) -> Dict[str, Any]:
		timeframe = os.getenv("TIMEFRAME", "5m")
		
		additional_args = [
			"--timeframe", timeframe,
			"--export", "trades",
			"--print-json",
		]
		
		self.logger.info("Running backtest...")
		
		return_code, stdout, stderr = self.subprocess_wrapper.run_freqtrade_command(
			subcommand="backtesting",
			strategy_name=self.strategy_name,
			strategy_path=STRATS_DIR,
			additional_args=additional_args,
			timeout=600  # 10 minutes timeout
		)
		
		if return_code != 0:
			self.logger.error(f"Backtest failed with code {return_code}")
			self.logger.error(f"Stderr: {stderr}")
			raise RuntimeError(f"Backtest failed: {stderr}")
			
		# Parse JSON output
		try:
			data = json.loads(stdout.strip().splitlines()[-1])
		except Exception as e:
			self.logger.warning(f"Could not parse backtest JSON output: {e}")
			data = {"results": {}, "metrics": {}}
			
		return data

	def _compute_summary(self, out: Dict[str, Any]) -> Dict[str, Any]:
		metrics = out.get("metrics", {})
		# Fallbacks
		roi = float(metrics.get("profit_total", 0.0))
		sharpe = float(metrics.get("sharpe", 0.0))
		mdd = float(metrics.get("max_drawdown_abs", 0.0))
		winrate = float(metrics.get("winrate", 0.0))
		exposure = float(metrics.get("exposure", 0.0))
		confidence = max(0.0, sharpe - mdd * 0.1 + winrate * 0.01)
		return {
			"strategy_name": self.strategy_name,
			"roi": roi,
			"sharpe": sharpe,
			"max_drawdown": mdd,
			"winrate": winrate,
			"exposure": exposure,
			"confidence": confidence,
			"period": {"generated_at": datetime.utcnow().isoformat()},
			"by_pair": out.get("results", {}),
		}


def main():
	BacktestRunner().run()


if __name__ == "__main__":
	main()
