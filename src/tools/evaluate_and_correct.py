import os
import json
import time
from typing import Dict

from loguru import logger

from src.runtime.paths import get_paths, ensure_dirs
from src.runtime.evaluator import thresholds_from_config, evaluate_metrics, corrective_actions
from src.sequence_runner import run_cmd, run_dry_trading
import yaml


def load_config(paths: Dict) -> Dict:
	with open(paths["config"], "r", encoding="utf-8") as f:
		return yaml.safe_load(f)


def find_latest_session(paths: Dict) -> str:
	live_root = os.path.join(paths["root"], "src", "data", "live_reports")
	if not os.path.exists(live_root):
		return ""
	dirs = [os.path.join(live_root, d) for d in os.listdir(live_root) if d.startswith("session_")]
	if not dirs:
		return ""
	dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
	return dirs[0]


def load_metrics_from_session(session_dir: str) -> Dict:
	metrics_file = os.path.join(session_dir, "metrics.json")
	if os.path.exists(metrics_file):
		with open(metrics_file, "r", encoding="utf-8") as f:
			return json.load(f)
	return {}


def write_cycle_report(paths: Dict, payload: Dict) -> str:
	report_path = os.path.join(paths["root"], "src", "data", "reports", "cycle_report.json")
	os.makedirs(os.path.dirname(report_path), exist_ok=True)
	with open(report_path, "w", encoding="utf-8") as f:
		json.dump(payload, f, indent=2)
	return report_path


def emergency_rollback_snapshot(paths: Dict) -> str:
	"""Save current strategy/model to an emergency snapshot directory."""
	import shutil
	snap_dir = os.path.join(paths["root"], "src", "data", "artifacts", f"emergency_snapshot_{int(time.time())}")
	os.makedirs(snap_dir, exist_ok=True)
	try:
		shutil.copy2(paths["strategy_file"], os.path.join(snap_dir, "current_strategy.py"))
		model_dir = os.path.join(paths["model_dir"]) 
		for f in os.listdir(model_dir):
			fp = os.path.join(model_dir, f)
			if os.path.isfile(fp):
				shutil.copy2(fp, os.path.join(snap_dir, f))
	except Exception:
		pass
	return snap_dir


def _load_latest_best_params(paths: Dict) -> Dict:
	results_dir = os.path.join(paths["root"], "src", "data", "hyperopt_results")
	if not os.path.exists(results_dir):
		return {}
	files = [os.path.join(results_dir, f) for f in os.listdir(results_dir) if f.startswith("best_params_") and f.endswith(".json")]
	if not files:
		return {}
	files.sort(key=os.path.getmtime, reverse=True)
	try:
		with open(files[0], "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return {}


def _freeze_final(paths: Dict, final_params: Dict, summary: Dict) -> str:
	out_dir = os.path.join(paths["root"], "src", "data", "hyperopt_results")
	os.makedirs(out_dir, exist_ok=True)
	freeze = {
		"final_params": final_params,
		"summary": summary,
	}
	out_path = os.path.join(out_dir, "final_strategy_set.json")
	with open(out_path, "w", encoding="utf-8") as f:
		json.dump(freeze, f, indent=2)
	return out_path


def main():
	paths = get_paths()
	ensure_dirs(paths)
	logger.add(os.path.join(paths["log_dir"], "evaluate_and_correct.log"), rotation="5 MB")

	cfg = load_config(paths)
	th = thresholds_from_config(cfg)
	session_dir = find_latest_session(paths)
	metrics = load_metrics_from_session(session_dir) if session_dir else {}
	passed, issues = evaluate_metrics(metrics or {}, th)
	payload = {
		"timestamp": int(time.time()),
		"session_dir": session_dir,
		"metrics": metrics,
		"thresholds": th,
		"passed": passed,
		"issues": issues,
		"steps": [],
	}

	# Adaptive multi-cycle stabilization: require 3 consecutive passes
	consecutive_needed = 3
	consec = 1 if passed else 0
	max_rounds = int(cfg.get("stabilize_max_rounds", 10))
	first_metrics = metrics or {}
	for round_idx in range(max_rounds):
		if consec >= consecutive_needed:
			break
		# Apply corrective actions and re-run a shorter cycle
		payload["steps"].append({"action": "corrective_actions_apply", "issues": issues})
		new_cfg = corrective_actions(cfg)
		with open(paths["config"], "w", encoding="utf-8") as f:
			yaml.safe_dump(new_cfg, f)
		payload["steps"].append({"action": "corrective_trade_block", "duration_sec": 900})
		run_dry_trading(paths, duration_seconds=900, simulate=True)
		# Hyperopt on recent data
		latest = find_latest_session(paths)
		dataset_path = os.path.join(latest, "trades.csv") if latest else ""
		payload["steps"].append({"action": "corrective_hyperopt", "dataset": dataset_path})
		trials = int(new_cfg.get("auto_optimize_trials", 200))
		if dataset_path and os.path.exists(dataset_path):
			ret = run_cmd([os.sys.executable, "-m", "src.hyperopt_ml", "--trials", str(trials), "--dataset", dataset_path], paths["root"])
		else:
			ret = run_cmd([os.sys.executable, "-m", "src.hyperopt_ml", "--trials", str(trials)], paths["root"])
		payload["steps"].append({"action": "corrective_hyperopt_rc", "rc": ret})
		# Re-evaluate after corrective pass
		latest2 = find_latest_session(paths)
		metrics = load_metrics_from_session(latest2) if latest2 else {}
		passed, issues = evaluate_metrics(metrics or {}, th)
		payload.setdefault("stabilization_checks", []).append({
			"round": round_idx + 1,
			"metrics": metrics,
			"passed": passed,
			"issues": issues,
		})
		consec = (consec + 1) if passed else 0
		cfg = new_cfg
		# Emergency rollback if catastrophic after corrective
		if (not passed) and ((float(metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 0.0))) >= th["max_mdd_max_pct"]) or (float(metrics.get("sharpe", 0.0)) < th["sharpe_min"])):
			payload["steps"].append({"action": "emergency_rollback_snapshot"})
			payload["rollback_snapshot"] = emergency_rollback_snapshot(paths)

	# Finalize report
	report_path = write_cycle_report(paths, payload)
	# Freeze params if stabilized
	if consec >= consecutive_needed:
		best = _load_latest_best_params(paths)
		freeze_path = _freeze_final(paths, best, {"first": first_metrics, "last": metrics})
		print(freeze_path)
	print(report_path)


if __name__ == "__main__":
	main()


