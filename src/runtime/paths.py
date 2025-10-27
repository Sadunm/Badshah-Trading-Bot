import os


def get_paths():
	root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
	return {
		"root": root,
		"config": os.path.join(root, "src", "config.yaml"),
		"log_dir": os.path.join(root, "src", "data", "logs"),
		"model_dir": os.path.join(root, "src", "data", "models"),
		"reports_dir": os.path.join(root, "src", "data", "reports"),
		"strategy_dir": os.path.join(root, "src", "strategies"),
		"strategy_file": os.path.join(root, "src", "strategies", "current_strategy.py"),
	}


def ensure_dirs(paths):
	for k in ["log_dir", "model_dir", "strategy_dir", "reports_dir"]:
		os.makedirs(paths[k], exist_ok=True)
