import os
import csv
import yaml
from typing import Dict, List

from src.runtime.paths import get_paths, ensure_dirs
from src.runtime.datafeed import LiveDataFeed
import math
import random


def write_csv(path: str, rows: List[Dict]) -> None:
	if not rows:
		return
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=["ts", "open", "high", "low", "close", "volume", "symbol"])
		w.writeheader()
		for r in rows:
			w.writerow(r)


def main() -> None:
	paths = get_paths()
	ensure_dirs(paths)
	with open(paths["config"], "r", encoding="utf-8") as f:
		config = yaml.safe_load(f)
	feed = LiveDataFeed({**config, "websocket_enabled": False, "simulate": False})
	limit = int(config.get("backfill_candles", 1000))
	datasets_root = os.path.join(paths["root"], "src", "data", "datasets")
	os.makedirs(datasets_root, exist_ok=True)
	for symbol in config.get("symbols", [config.get("symbol", "BTCUSDT")]):
		rows = feed.backfill_klines(symbol, limit=limit)
		# Fallback to synthetic GBM candles if no data available
		if not rows:
			seed = int(config.get("simulate_seed", 42))
			rng = random.Random(seed)
			mu = float(config.get("gbm_mu", 0.0))
			sigma = float(config.get("gbm_sigma", 0.02))
			price = 20000.0
			rows = []
			# approximate 1m candles
			for i in range(limit):
				u1 = max(1e-12, rng.random())
				u2 = max(1e-12, rng.random())
				z = ((-2.0 * math.log(u1)) ** 0.5) * math.cos(2.0 * math.pi * u2)
				growth = (mu - 0.5 * sigma * sigma) * (1.0/1440.0) + sigma * (1.0/1440.0) ** 0.5 * z
				open_p = price
				close_p = max(0.01, price * math.exp(growth))
				high_p = max(open_p, close_p) * (1.0 + 0.001 * rng.random())
				low_p = min(open_p, close_p) * (1.0 - 0.001 * rng.random())
				vol = 100 + 50 * rng.random()
				ts = (i + 1) * 60
				rows.append({"ts": ts, "open": open_p, "high": high_p, "low": low_p, "close": close_p, "volume": vol, "symbol": symbol})
				price = close_p
		outfile = os.path.join(datasets_root, f"{symbol}_{config.get('interval','1m')}.csv")
		write_csv(outfile, rows)
		print(f"Wrote {len(rows)} rows to {outfile}")


if __name__ == "__main__":
	main()


