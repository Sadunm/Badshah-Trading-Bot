import os
import time
import subprocess
from datetime import datetime, timedelta
from typing import Dict

from loguru import logger

from src.runtime.paths import get_paths, ensure_dirs
from src.runtime.strategy_loader import ensure_strategy_or_warn
from src.runtime.evaluator import thresholds_from_config, evaluate_metrics, corrective_actions, detect_metric_imbalance
import yaml
import json
import shutil
import yaml
from datetime import datetime


def run_cmd(args: list[str], cwd: str) -> int:
	try:
		proc = subprocess.run(args, cwd=cwd, check=False)
		return int(proc.returncode)
	except Exception:
		return 1


def run_hyperopt(paths: Dict, trials: int = 50) -> int:
	return run_cmd([os.sys.executable, "-m", "src.hyperopt_ml", "--trials", str(trials)], paths["root"])


def run_dry_trading(paths: Dict, duration_seconds: int, simulate: bool = True, max_ticks: int = 0) -> int:
	args = [os.sys.executable, "-m", "src.main"]
	if simulate:
		args.append("--simulate")
	if max_ticks > 0:
		args.extend(["--max-ticks", str(max_ticks)])
	# Launch and let it run for duration, then terminate
	proc = subprocess.Popen(args, cwd=paths["root"])
	deadline = time.time() + duration_seconds
	while time.time() < deadline:
		time.sleep(5)
	ret = 0
	try:
		proc.terminate()
		proc.wait(timeout=10)
		ret = int(proc.returncode or 0)
	except Exception:
		ret = 0
	return ret


def run_backtest_quick(paths: Dict) -> Dict:
	# Use recent logs metrics as a proxy
	metrics_path = os.path.join(paths.get("reports_dir", paths["log_dir"]), "metrics.json")
	try:
		import json
		with open(metrics_path, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return {"total_profit": 0.0, "max_drawdown": 0.0}


def _find_latest_hyperopt_params(paths: Dict) -> str:
    try:
        import glob
        results_dir = os.path.join(paths["root"], "src", "data", "hyperopt_results")
        files = sorted(glob.glob(os.path.join(results_dir, "best_params_*.json")))
        return files[-1] if files else ""
    except Exception:
        return ""


def _write_lock(paths: Dict, metrics: Dict, thresholds: Dict) -> None:
    lock_dir = os.path.join(paths["root"], "src", "data", "reports")
    os.makedirs(lock_dir, exist_ok=True)
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metrics": metrics,
        "thresholds": thresholds,
        "note": "Parameters locked after stabilized multi-objective pass",
        "best_params_file": _find_latest_hyperopt_params(paths),
    }
    with open(os.path.join(lock_dir, "locked_params.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    paths = get_paths()
    ensure_dirs(paths)
    logger.add(os.path.join(paths["log_dir"], "sequence_runner.log"), rotation="10 MB")

    logger.info("[SEQ] Starting stabilized sequence controller: backtest → trade 3h → cooldown 150s → hyperopt (recent) → trade 3h → evaluate, re-opt on imbalance until thresholds met")

    with open(paths["config"], "r", encoding="utf-8") as cf:
        cfg = yaml.safe_load(cf)
    th = thresholds_from_config(cfg)
    max_cycles = int(cfg.get("stabilized_max_cycles", 6))
    cycle_history = []
    prev_metrics = {}
    for cycle_idx in range(max_cycles):
        logger.info(f"[SEQ] Cycle {cycle_idx+1}/{max_cycles}: trade 3h (simulate)")
        run_dry_trading(paths, duration_seconds=3 * 3600, simulate=True)
        logger.info("[SEQ] Cooling down for 150 seconds...")
        time.sleep(150)

        # Collect latest dataset path from last session
        try:
            live_root = os.path.join(paths["root"], "src", "data", "live_reports")
            sessions = sorted([d for d in os.listdir(live_root) if d.startswith("session_")])
            last_session = sessions[-1] if sessions else ""
            dataset_path = os.path.join(live_root, last_session, "trades.csv") if last_session else ""
        except Exception:
            dataset_path = ""

        logger.info("[SEQ] Running hyperopt on recent data...")
        if dataset_path and os.path.exists(dataset_path):
            ret = run_cmd([os.sys.executable, "-m", "src.hyperopt_ml", "--trials", str(int(cfg.get("auto_optimize_trials", 150))), "--dataset", dataset_path], paths["root"])
        else:
            logger.warning("[SEQ] Recent dataset not found; running hyperopt with default logs")
            ret = run_hyperopt(paths, trials=int(cfg.get("auto_optimize_trials", 150)))
        logger.info(f"[SEQ] Hyperopt return code: {ret}")

        # Resume trading to validate new parameters
        logger.info("[SEQ] Validating new parameters with 3h trading")
        run_dry_trading(paths, duration_seconds=3 * 3600, simulate=True)

        # Evaluate metrics
        metrics = run_backtest_quick(paths)
        passed, issues = evaluate_metrics(metrics, th)
        imbalanced, imbalance_details = (False, {}) if not prev_metrics else detect_metric_imbalance(prev_metrics, metrics)
        cycle_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "cycle": cycle_idx + 1,
            "metrics": metrics,
            "passed": passed,
            "issues": issues,
            "imbalanced": imbalanced,
            "imbalance_details": imbalance_details,
        }
        cycle_history.append(cycle_entry)

        # Persist rolling report
        report = {
            "thresholds": th,
            "cycles": cycle_history,
            "stabilized": bool(passed and (not imbalanced)),
        }
        report_path = os.path.join(paths["root"], "src", "data", "reports", "cycle_report.json")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"[SEQ] Cycle report updated: {report_path}")

        if passed and not imbalanced:
            logger.info("[SEQ] All thresholds satisfied with stability. Locking parameters.")
            _write_lock(paths, metrics, th)
            break

        # Not yet stable; apply corrective actions and continue
        logger.warning(f"[SEQ] Not stabilized (passed={passed}, imbalanced={imbalanced}). Applying corrective actions and continuing.")
        cfg = corrective_actions(cfg)
        with open(paths["config"], "w", encoding="utf-8") as cf:
            yaml.safe_dump(cfg, cf)
        th = thresholds_from_config(cfg)
        prev_metrics = metrics

if __name__ == "__main__":
    main()


