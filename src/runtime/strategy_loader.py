import os
from typing import Any


def ensure_strategy_or_warn(paths: dict) -> bool:
	strategy_file = paths["strategy_file"]
	if not os.path.exists(strategy_file):
		print("Please run hyperopt_and_ml.bat first.")
		return False
	return True


def load_strategy(paths: dict) -> Any:
	# Import strategy module dynamically
	import importlib.util
	spec = importlib.util.spec_from_file_location("current_strategy", paths["strategy_file"])
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)  # type: ignore
	return module.Strategy()
