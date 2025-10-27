import os
import csv
import math
import json
from typing import Dict, List
import matplotlib.pyplot as plt


class PerformanceTracker:
	def __init__(self, paths: Dict, window_trades: int = 200):
		self.paths = paths
		self.window = window_trades
		self.num_trades = 0
		self.equity_curve: List[float] = []
		self.equity = 0.0
		self.wins = 0
		self.losses = 0
		self.returns: List[float] = []
		self.log_path = os.path.join(paths["log_dir"], "trades.csv")
		self.metrics_path = os.path.join(paths.get("reports_dir", paths["log_dir"]), "metrics.json")
		if not os.path.exists(self.log_path):
			with open(self.log_path, "w", newline="", encoding="utf-8") as f:
				w = csv.writer(f)
				w.writerow(["symbol", "side", "price", "qty", "pnl"])  # header

	def record_trade(self, order: Dict) -> None:
		self.num_trades += 1
		pnl = float(order.get("pnl", 0.0))
		self.equity += pnl
		self.equity_curve.append(self.equity)
		ret = 0.0
		if len(self.equity_curve) >= 2:
			prev = self.equity_curve[-2]
			if prev != 0:
				ret = (self.equity - prev) / abs(prev)
		self.returns.append(ret)
		if pnl >= 0:
			self.wins += 1
		else:
			self.losses += 1
		if len(self.equity_curve) > self.window:
			self.equity_curve.pop(0)
		with open(self.log_path, "a", newline="", encoding="utf-8") as f:
			w = csv.writer(f)
			w.writerow([order.get("symbol"), order.get("side"), order.get("price"), order.get("qty"), pnl])

	def compute_metrics(self) -> Dict:
		total_profit = self.equity_curve[-1] if self.equity_curve else 0.0
		max_drawdown = 0.0
		if self.equity_curve:
			peak = self.equity_curve[0]
			for val in self.equity_curve:
				if val > peak:
					peak = val
				dd = peak - val
				if dd > max_drawdown:
					max_drawdown = dd
		winrate = (self.wins / max(1, self.wins + self.losses)) * 100.0
		sharpe = 0.0
		sortino = 0.0
		if len(self.returns) >= 2:
			mean_r = sum(self.returns) / len(self.returns)
			std_r = math.sqrt(sum((r - mean_r) ** 2 for r in self.returns) / (len(self.returns) - 1)) if len(self.returns) > 1 else 0.0
			if std_r != 0:
				sharpe = (mean_r / std_r) * math.sqrt(252)
			# downside deviation for Sortino (only negative returns)
			neg = [min(0.0, r) for r in self.returns]
			if any(r < 0 for r in neg):
				dd = math.sqrt(sum((r) ** 2 for r in neg) / max(1, len([r for r in neg if r < 0])))
				if dd != 0:
					sortino = (mean_r / dd) * math.sqrt(252)
		# naive turnover = number of sells over window
		turnover = float(self.losses + self.wins) / max(1, self.window)
		return {
			"total_profit": total_profit,
			"total_profit_pct": (total_profit / 100.0) * 100.0 if total_profit != 0 else 0.0,
			"max_drawdown": max_drawdown,
			"max_drawdown_pct": (max_drawdown / 100.0) * 100.0 if max_drawdown != 0 else 0.0,
			"winrate_pct": winrate,
			"sharpe": sharpe,
			"sortino": sortino,
			"turnover": turnover,
		}

	def plot_equity(self) -> str:
		plot_path = os.path.join(self.paths["log_dir"], "equity_curve.png")
		if not self.equity_curve:
			return plot_path
		plt.figure(figsize=(8, 3))
		plt.plot(self.equity_curve, label="Equity")
		plt.legend()
		plt.tight_layout()
		plt.savefig(plot_path)
		plt.close()
		return plot_path

	def flush(self) -> None:
		self.plot_equity()
		# Persist metrics snapshot
		try:
			metrics = self.compute_metrics()
			os.makedirs(os.path.dirname(self.metrics_path), exist_ok=True)
			with open(self.metrics_path, "w", encoding="utf-8") as f:
				json.dump(metrics, f, indent=2)
		except Exception:
			pass


def should_trigger_reopt(metrics: Dict, config: Dict, volatility: float = 0.0) -> bool:
	profit_th = float(config.get("profit_threshold_pct", 0.5))
	mdd_th = float(config.get("max_drawdown_threshold_pct", 5.0))
	vol_th = float(config.get("volatility_trigger_threshold", 9999))
	return (metrics.get("total_profit_pct", 0.0) < profit_th) or (
		metrics.get("max_drawdown_pct", 0.0) > mdd_th
	) or (volatility > vol_th)
