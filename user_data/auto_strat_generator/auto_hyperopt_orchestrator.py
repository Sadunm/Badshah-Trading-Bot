from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from rich.progress import Progress

from .common.logging_utils import setup_logger, get_log_path
from .common.strategy_builder import write_strategy
from .common.storage import atomic_write_json, save_artifact
from .common.utils import STRATS_DIR
from .common.subprocess_wrapper import SafeSubprocessWrapper


class HyperoptOrchestrator:
	def __init__(self):
		self.logger = setup_logger("auto_hyperopt_orchestrator", get_log_path("auto_hyperopt_orchestrator.log"))
		self.strategy_name = "AutoGenStrategy"
		self.subprocess_wrapper = SafeSubprocessWrapper("hyperopt_orchestrator")

	def run(self) -> Path:
		params = self._baseline_params()
		strategy_path = write_strategy(params, name=self.strategy_name)
		self.logger.info(f"Wrote baseline strategy to {strategy_path}")

		best = self._run_freqtrade_hyperopt(strategy_path)
		best_file = STRATS_DIR / "best_strategy.json"
		atomic_write_json(best_file, best)
		self.logger.info(f"Best strategy saved to {best_file}")
		save_artifact("hyperopt", "best", best, score=float(best.get("score", 0.0)))
		return best_file

	def _run_freqtrade_hyperopt(self, strategy_path: Path) -> Dict[str, Any]:
		timeframe = os.getenv("TIMEFRAME", "5m")
		epochs = int(os.getenv("HYPEROPT_EPOCHS", "200"))
		
		additional_args = [
			"--timeframe", timeframe,
			"--spaces", "buy", "sell", "roi", "stoploss", "trailing",
			"--hyperopt-loss", "SharpeHyperOptLossDaily",
			"--epochs", str(epochs),
			"--print-json",
		]
		
		self.logger.info(f"Running hyperopt with {epochs} epochs...")
		
		return_code, stdout, stderr = self.subprocess_wrapper.run_freqtrade_command(
			subcommand="hyperopt",
			strategy_name=self.strategy_name,
			strategy_path=STRATS_DIR,
			additional_args=additional_args,
			timeout=1800  # 30 minutes timeout
		)
		
		if return_code != 0:
			self.logger.error(f"Hyperopt failed with code {return_code}")
			self.logger.error(f"Stderr: {stderr}")
			raise RuntimeError(f"Hyperopt failed: {stderr}")
			
		# Parse JSON output
		try:
			best = json.loads(stdout.strip().splitlines()[-1])
		except Exception as e:
			self.logger.warning(f"Could not parse hyperopt JSON output: {e}")
			best = {"params": {}, "score": 0.0}
			
		best["generated_at"] = datetime.utcnow().isoformat()
		best["hash"] = hashlib.md5(json.dumps(best, sort_keys=True).encode()).hexdigest()
		return best

	@staticmethod
	def _baseline_params() -> Dict[str, Any]:
		return {
			"timeframe": os.getenv("TIMEFRAME", "5m"),
			"minimal_roi": {"0": 0.10, "60": 0.05, "120": 0.025, "240": 0.0},
			"stoploss": -0.10,
			"trailing_stop": False,
			"rsi_buy": 55,
			"rsi_sell": 45,
		}


def main():
	orchestrator = HyperoptOrchestrator()
	orchestrator.run()


if __name__ == "__main__":
	main()
