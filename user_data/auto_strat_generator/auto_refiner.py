from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .common.logging_utils import setup_logger, get_log_path
from .common.rl_learner import BanditRL
from .common.strategy_builder import write_strategy
from .common.storage import atomic_write_json, save_artifact
from .common.utils import STRATS_DIR, RESULTS_DIR


class StrategyRefiner:
	def __init__(self):
		self.logger = setup_logger("auto_refiner", get_log_path("auto_refiner.log"))
		self.best_path = STRATS_DIR / "best_strategy.json"
		self.backtest_path = RESULTS_DIR / "backtest_summary.json"
		self.strategy_name = "AutoGenStrategy"

	def run(self) -> Path:
		best = self._load_json(self.best_path)
		back = self._load_json(self.backtest_path)
		roi_observed = float(back.get("roi", 0.0))
		drawdown = float(back.get("max_drawdown", 0.0))
		self.logger.info(f"RL update with roi={roi_observed:.4f}, dd={drawdown:.4f}")

		rl = BanditRL()
		if isinstance(best, dict):
			params = best.get("params", {})
			if isinstance(params, dict) and "minimal_roi" in params:
				try:
					rl.roi_weights = {k: float(v) for k, v in params["minimal_roi"].items()}
				except Exception:
					pass

		rl.update(roi_observed=roi_observed, drawdown=drawdown)
		new_params = {
			"timeframe": os.getenv("TIMEFRAME", "5m"),
			"minimal_roi": rl.as_minimal_roi(),
			"stoploss": min(-0.02 * rl.risk_weight, -0.04),
			"trailing_stop": False,
			"rsi_buy": 55,
			"rsi_sell": 45,
		}
		path = write_strategy(new_params, name=self.strategy_name)
		self.logger.info(f"Refined strategy written to {path}")

		best_update = {
			"params": new_params,
			"score": back.get("confidence", 0.0),
			"updated_at": datetime.utcnow().isoformat(),
		}
		atomic_write_json(self.best_path, best_update)
		save_artifact("strategy", "refined", best_update, score=float(best_update.get("score", 0.0)))
		return path

	@staticmethod
	def _load_json(path: Path) -> Dict[str, Any]:
		if not path.exists():
			return {}
		return json.loads(path.read_text(encoding="utf-8"))


def main():
	StrategyRefiner().run()


if __name__ == "__main__":
	main()
