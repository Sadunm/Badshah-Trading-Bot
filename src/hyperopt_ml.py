import os
import csv
import yaml
import time
import json
import argparse
import random
import numpy as np
import pandas as pd
from loguru import logger
from typing import Dict, List
from hyperopt import fmin, tpe, hp, Trials
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from joblib import dump
from src.runtime.paths import get_paths, ensure_dirs


REQUIRED_COLS = ["symbol", "side", "price", "qty", "pnl"]


def read_config(paths: Dict) -> Dict:
	with open(paths["config"], "r", encoding="utf-8") as f:
		return yaml.safe_load(f)


def ensure_logs_exist(paths: Dict, config: Dict) -> str:
	log_path = os.path.join(paths["log_dir"], "trades.csv")
	if os.path.exists(log_path):
		return log_path
	os.makedirs(paths["log_dir"], exist_ok=True)
	with open(log_path, "w", newline="", encoding="utf-8") as f:
		w = csv.writer(f)
		w.writerow(REQUIRED_COLS)
		for _ in range(int(config.get("backfill_candles", 500))):
			price = 20000 + random.random() * 1000
			pnl = random.uniform(-5, 5)
			w.writerow(["BTCUSDT", "SELL", price, 0.01, pnl])
	return log_path


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
	cols = [c.strip().lower() for c in df.columns]
	mapping = {c: c for c in df.columns}
	# Map known variations
	for i, c in enumerate(cols):
		if c in ("symbol",):
			mapping[df.columns[i]] = "symbol"
		elif c in ("side",):
			mapping[df.columns[i]] = "side"
		elif c in ("price",):
			mapping[df.columns[i]] = "price"
		elif c in ("qty", "quantity"):
			mapping[df.columns[i]] = "qty"
		elif c in ("pnl", "profit", "p_l"):
			mapping[df.columns[i]] = "pnl"
	df = df.rename(columns=mapping)
	# If legacy 4-column logs (side,price,qty,pnl), synthesize symbol
	if set(df.columns) >= {"side", "price", "qty", "pnl"} and "symbol" not in df.columns:
		df["symbol"] = "BTCUSDT"
	# Keep only required cols
	missing = [c for c in REQUIRED_COLS if c not in df.columns]
	for m in missing:
		if m == "symbol":
			df[m] = "BTCUSDT"
		elif m == "side":
			df[m] = "SELL"
		else:
			df[m] = 0.0
	return df[REQUIRED_COLS].copy()


def load_dataset(log_path: str) -> pd.DataFrame:
	# Be tolerant to malformed lines and schema drift
	df = pd.read_csv(log_path, engine="python", on_bad_lines="skip")
	if df.empty:
		df = pd.DataFrame([{c: 0 for c in REQUIRED_COLS}])
		df["symbol"] = "BTCUSDT"
		return df
	return _normalize_df(df)


def objective(params: Dict, df: pd.DataFrame) -> float:
    """Risk-aware objective combining profitability and tail risk.

    Maximizes: Net PnL, ROI, Sharpe, Profit Factor; Minimizes: CVaR(5%), Max Loss size.
    Returns loss for hyperopt (lower is better).
    """
    threshold = float(params.get("threshold", 0.0))
    tp_mult = float(params.get("tp_mult", 1.5))
    sl_mult = float(params.get("sl_mult", 1.0))
    atr_mult = float(params.get("atr_mult", 2.0))
    cooldown = int(params.get("cooldown_ticks", 10))

    # Use threshold to filter low-quality trades
    s = df[df["pnl"] > threshold]
    if s.empty:
        return 1.0

    profits = s[s["pnl"] > 0]["pnl"].values.tolist()
    losses = s[s["pnl"] < 0]["pnl"].values.tolist()
    net = float(s["pnl"].sum())
    roi = float(net)  # trades.csv is PnL units; relative ROI proxy
    sharpe = 0.0
    if len(s) > 1:
        r = s["pnl"].astype(float).values
        mu = float(r.mean())
        std = float(r.std() or 0.0)
        if std > 0:
            sharpe = (mu / std) * (252 ** 0.5)
    # Profit Factor
    pf = (sum(profits) / max(1e-9, abs(sum(losses)))) if losses else 10.0
    # CVaR(5%) of losses (negative tail)
    tail = sorted([abs(x) for x in losses], reverse=True)
    k = max(1, int(len(tail) * 0.05))
    cvar = float(sum(tail[:k]) / k) if tail else 0.0
    # Max single loss
    max_loss = float(max(tail) if tail else 0.0)
    # Turnover penalty (favor fewer but better trades when cooldown/atr active)
    turnover = min(1.0, len(s) / max(1.0, len(df)))

    # Win rate
    winrate = float(len(profits) / max(1, len(s)))

    # Directional exposure balance (BUY vs SELL) — penalize gaps > 5%
    buy_ct = int((s["side"] == "BUY").sum()) if "side" in s.columns else 0
    sell_ct = int((s["side"] == "SELL").sum()) if "side" in s.columns else 0
    total_ct = max(1, buy_ct + sell_ct)
    side_gap = abs(buy_ct - sell_ct) / float(total_ct)
    balance_penalty = max(0.0, side_gap - 0.05)  # only penalize beyond 5% gap

    # Utility: weights prioritizing net pnl, sharpe, PF, winrate; penalize CVaR/max loss/turnover and side imbalance; small preference for stronger tp vs sl and reasonable atr/cooldown
    utility = (
        1.0 * net +
        0.5 * roi +
        0.3 * sharpe +
        0.4 * pf +
        0.6 * (winrate - 0.6) -
        0.5 * cvar -
        0.5 * max_loss -
        0.1 * (-turnover) +
        2.0 * (-(balance_penalty)) +
        0.02 * (tp_mult - sl_mult) +
        0.01 * (atr_mult) -
        0.005 * max(0, cooldown - 5)
    )
    return -float(utility)


def run_hyperopt(df: pd.DataFrame, trials_n: int) -> Dict:
	space = {
		"threshold": hp.uniform("threshold", -1.0, 2.0),
		"tp_mult": hp.uniform("tp_mult", 0.5, 4.0),
		"sl_mult": hp.uniform("sl_mult", 0.2, 2.5),
		"atr_mult": hp.uniform("atr_mult", 0.5, 5.0),
		"cooldown_ticks": hp.randint("cooldown_ticks", 30),
	}
	trials = Trials()
	best = fmin(fn=lambda p: objective(p, df), space=space, algo=tpe.suggest, max_evals=trials_n, trials=trials, rstate=np.random.default_rng(42))
	return best


def classify_regime(df: pd.DataFrame) -> str:
	vol = float(df["pnl"].std()) if not df["pnl"].empty else 0.0
	return "high_vol" if vol > 2.5 else "low_vol"


def train_ml(df: pd.DataFrame) -> Dict:
	X = df[["price", "qty", "pnl"]].fillna(0.0)
	y = (df["pnl"] > df["pnl"].median()).astype(int)
	X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
	clf = RandomForestClassifier(n_estimators=200, random_state=42)
	clf.fit(X_train, y_train)
	acc = float(clf.score(X_test, y_test))
	regime = classify_regime(df)
	return {"model": clf, "accuracy": acc, "regime": regime}


def write_strategy(paths: Dict, best_params: Dict, model_info: Dict) -> List[str]:
	os.makedirs(paths["strategy_dir"], exist_ok=True)
	artifacts_dir = os.path.join(paths["root"], "src", "data", "artifacts", "strategy_versions")
	os.makedirs(artifacts_dir, exist_ok=True)
	ts = int(time.time())
	strategy_path = paths["strategy_file"]
	versioned = os.path.join(artifacts_dir, f"strategy_{ts}.py")
	content: List[str] = []
	content.append("class Strategy:\n")
	content.append("\tdef __init__(self):\n")
	content.append(f"\t\tself.rsi_buy = {int(55 + (best_params.get('conf_gate', 0.0) * 20))}\n")
	content.append(f"\t\tself.rsi_sell = {int(45 - (best_params.get('conf_gate', 0.0) * 15))}\n")
	content.append(f"\t\tself.tp_mult = {best_params.get('tp_mult', 1.5)}\n")
	content.append(f"\t\tself.sl_mult = {best_params.get('sl_mult', 1.0)}\n")
	content.append("\n")
	content.append("\tdef _ema(self, prev: float, price: float, span: int, k: float, init: float) -> float:\n")
	content.append("\t\t# Single-step EMA update with smoothing factor k; init used for first value\n")
	content.append("\t\treturn (price * k) + (prev * (1.0 - k)) if prev > 0 else init\n")
	content.append("\n")
	content.append("\tdef generate_signal(self, tick, broker_state):\n")
	content.append("\t\tprice = float(tick['price'])\n")
	content.append("\t\tstate = broker_state.get('indicators', {})\n")
	content.append("\t\tf12 = float(state.get('ema_fast', 0.0))\n")
	content.append("\t\tf26 = float(state.get('ema_slow', 0.0))\n")
	content.append("\t\t# k for EMA spans 12 and 26 assuming per-tick smoothing\n")
	content.append("\t\tk12 = 2.0 / (12 + 1)\n")
	content.append("\t\tk26 = 2.0 / (26 + 1)\n")
	content.append("\t\tf12 = self._ema(f12, price, 12, k12, price)\n")
	content.append("\t\tf26 = self._ema(f26, price, 26, k26, price)\n")
	content.append("\t\t# Minimal RSI proxy over ticks using price momentum gates\n")
	content.append("\t\tmomentum = 1 if price >= state.get('last_price', price) else -1\n")
	content.append("\t\tpos = broker_state.get('positions', {}).get(tick['symbol'], {'qty': 0.0, 'entry_price': 0.0})\n")
	content.append("\t\tgate_buy = (f12 > f26) and (momentum > 0)\n")
	content.append("\t\tgate_sell = (f12 < f26) or (momentum < 0)\n")
	content.append("\t\t# Decide actions\n")
	content.append("\t\tif gate_buy and pos.get('qty', 0.0) == 0:\n")
	content.append("\t\t\treturn 'BUY'\n")
	content.append("\t\telif pos.get('qty', 0.0) > 0:\n")
	content.append("\t\t\tentry = float(pos.get('entry_price', 0.0) or 0.0)\n")
	content.append("\t\t\ttp = entry * (1.0 + 0.002 * self.tp_mult)\n")
	content.append("\t\t\tsl = entry * (1.0 - 0.001 * self.sl_mult)\n")
	content.append("\t\t\tif price >= tp or price <= sl or gate_sell:\n")
	content.append("\t\t\t\treturn 'SELL'\n")
	content.append("\t\treturn 'HOLD'\n")
	with open(strategy_path, "w", encoding="utf-8") as f:
		f.writelines(content)
	with open(versioned, "w", encoding="utf-8") as f:
		f.writelines(content)
	model_path = os.path.join(paths["model_dir"], "rf_model.joblib")
	dump(model_info["model"], model_path)
	return [strategy_path, versioned, model_path]


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser()
	p.add_argument("--trials", type=int, default=30)
	p.add_argument("--dataset", type=str, default="", help="Path to CSV of recent trades to use for hyperopt")
	p.add_argument("--test-mode", action="store_true")
	return p.parse_args()


def main():
	args = parse_args()
	paths = get_paths()
	ensure_dirs(paths)
	config = read_config(paths)
	os.makedirs(os.path.join(paths["root"], "src", "data", "artifacts"), exist_ok=True)
	logger.add(os.path.join(paths["log_dir"], "hyperopt.log"), rotation="10 MB")

	log_path = args.dataset if args.dataset else ensure_logs_exist(paths, config)
	df = load_dataset(log_path)

	logger.info("Running hyperopt...")
	trials_n = max(3, min(200, args.trials)) if args.test_mode else max(10, args.trials)
	best_params = run_hyperopt(df, trials_n=trials_n)
	logger.info(f"Best params: {best_params}")

	logger.info("Training ML model...")
	model_info = train_ml(df)
	logger.info(f"Model accuracy: {model_info['accuracy']:.4f}, regime={model_info['regime']}")

	# Save results to hyperopt_results dir (convert numpy scalars to native types)
	def _to_native(obj):
		if isinstance(obj, (np.integer,)):
			return int(obj)
		if isinstance(obj, (np.floating,)):
			return float(obj)
		return obj
	results_dir = os.path.join(paths["root"], "src", "data", "hyperopt_results")
	os.makedirs(results_dir, exist_ok=True)
	native_params = {k: _to_native(v) for k, v in best_params.items()}
	with open(os.path.join(results_dir, f"best_params_{int(time.time())}.json"), "w", encoding="utf-8") as f:
		json.dump(native_params, f, indent=2)

	logger.info("Writing new strategy file...")
	artifacts = write_strategy(paths, best_params, model_info)
	logger.info(f"Strategy updated and versioned: {json.dumps(artifacts)}")


if __name__ == "__main__":
	main()
