from typing import Dict, Tuple


def thresholds_from_config(cfg: Dict) -> Dict:
	return {
		"weekly_profit_min_pct": float(cfg.get("weekly_profit_min_pct", 2.0)),
		"monthly_roi_min_pct": float(cfg.get("monthly_roi_min_pct", 14.0)),
		"max_mdd_max_pct": float(cfg.get("max_mdd_max_pct", 18.0)),
		"sharpe_min": float(cfg.get("sharpe_min", 2.0)),
		"winrate_min": float(cfg.get("winrate_min", 60.0)),
	}


def evaluate_metrics(metrics: Dict, th: Dict) -> Tuple[bool, Dict]:
	# We use available metrics (PnL/ROI proxy, MDD, Sharpe). Weekly/monthly are longer-horizon targets; enforce core ones here.
	passed = True
	issues: Dict[str, str] = {}
	# enforce MDD and Sharpe
	if float(metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 0.0))) > th["max_mdd_max_pct"]:
		passed = False
		issues["mdd"] = f"MDD {metrics.get('max_drawdown_pct', metrics.get('max_drawdown', 0.0)):.2f}% > {th['max_mdd_max_pct']:.2f}%"
	if float(metrics.get("sharpe", 0.0)) < th["sharpe_min"]:
		passed = False
		issues["sharpe"] = f"Sharpe {metrics.get('sharpe', 0.0):.2f} < {th['sharpe_min']:.2f}"
	# Positive pnl proxy
	if float(metrics.get("total_profit", 0.0)) <= 0.0 and float(metrics.get("total_profit_pct", 0.0)) <= 0.0:
		passed = False
		issues["pnl"] = "Non-positive Net PnL"
	# Winrate
	wr = float(metrics.get("winrate_pct", 0.0))
	if wr < th.get("winrate_min", 60.0):
		passed = False
		issues["winrate"] = f"Winrate {wr:.1f}% < {th.get('winrate_min', 60.0):.1f}%"
	return passed, issues


def corrective_actions(cfg: Dict) -> Dict:
	# Tighter risk and lower turnover defaults to guide next optimization/trade run
	new_cfg = dict(cfg)
	new_cfg["risk_per_trade_pct"] = max(0.25, float(cfg.get("risk_per_trade_pct", 1.0)) * 0.75)
	new_cfg["max_loss_per_trade"] = max(0.01, float(cfg.get("max_loss_per_trade", 0.02)) * 0.75)
	new_cfg["min_ticks_between_reopt"] = int(float(cfg.get("min_ticks_between_reopt", 500)) * 0.9)
	new_cfg["min_seconds_between_reopt"] = int(float(cfg.get("min_seconds_between_reopt", 60)) * 0.9)
	# Encourage larger ATR trailing and longer cooldown in strategy search
	new_cfg["auto_optimize_trials"] = int(float(cfg.get("auto_optimize_trials", 200)) * 1.5)
	new_cfg["auto_optimize_max_iters"] = int(float(cfg.get("auto_optimize_max_iters", 8)) + 2)
	return new_cfg


def detect_metric_imbalance(prev: Dict, curr: Dict, tolerances: Dict | None = None) -> Tuple[bool, Dict]:
    """Detect instability where one core metric improves while others degrade materially.

    Core metrics considered: total_profit (or total_profit_pct), max_drawdown/max_drawdown_pct, winrate_pct, sharpe.
    tolerances can specify minimal improvements/degradations to consider (pct for winrate/mdd, absolute for sharpe, profit).
    Returns (is_imbalanced, details)
    """
    tolerances = tolerances or {}
    tol_profit = float(tolerances.get("profit_abs_min", 0.0))  # require any improvement by at least this
    tol_mdd_pct = float(tolerances.get("mdd_pct_min", 0.25))    # degrades if worsens by at least this percent point
    tol_wr_pct = float(tolerances.get("winrate_pct_min", 1.0))  # degrades if worsens by at least this percent point
    tol_sharpe = float(tolerances.get("sharpe_abs_min", 0.05))  # absolute sharpe change

    def _get_num(d: Dict, keys: list[str], default: float = 0.0) -> float:
        for k in keys:
            if k in d:
                try:
                    return float(d.get(k, default))
                except Exception:
                    continue
        return default

    prev_profit = _get_num(prev, ["total_profit", "total_profit_pct", "roi"], 0.0)
    curr_profit = _get_num(curr, ["total_profit", "total_profit_pct", "roi"], 0.0)
    prev_mdd = _get_num(prev, ["max_drawdown_pct", "max_drawdown"], 0.0)
    curr_mdd = _get_num(curr, ["max_drawdown_pct", "max_drawdown"], 0.0)
    prev_wr = _get_num(prev, ["winrate_pct", "winrate"], 0.0)
    curr_wr = _get_num(curr, ["winrate_pct", "winrate"], 0.0)
    prev_sharpe = _get_num(prev, ["sharpe"], 0.0)
    curr_sharpe = _get_num(curr, ["sharpe"], 0.0)

    improvements = {
        "profit_up": (curr_profit - prev_profit) >= tol_profit,
        "mdd_down": (prev_mdd - curr_mdd) >= tol_mdd_pct,  # lower is better
        "wr_up": (curr_wr - prev_wr) >= tol_wr_pct,
        "sharpe_up": (curr_sharpe - prev_sharpe) >= tol_sharpe,
    }
    degradations = {
        "profit_down": (prev_profit - curr_profit) >= tol_profit,
        "mdd_up": (curr_mdd - prev_mdd) >= tol_mdd_pct,  # higher is worse
        "wr_down": (prev_wr - curr_wr) >= tol_wr_pct,
        "sharpe_down": (prev_sharpe - curr_sharpe) >= tol_sharpe,
    }

    # Imbalance if at least one improvement and at least one degradation across core metrics
    improved_any = any(improvements.values())
    degraded_any = any(degradations.values())
    is_imbalanced = bool(improved_any and degraded_any)
    details = {"improvements": improvements, "degradations": degradations}
    return is_imbalanced, details


