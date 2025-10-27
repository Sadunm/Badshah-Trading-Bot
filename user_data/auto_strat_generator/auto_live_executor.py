from __future__ import annotations
import os
import subprocess
import time
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from .common.logging_utils import setup_logger, get_log_path
from .common.config_builder import write_config
from .common.utils import STRATS_DIR, CONFIGS_DIR, ema, compute_rsi
from .common.storage import fetch_market, open_trade, close_trade, get_open_trades, compute_equity
from .common.subprocess_wrapper import SafeSubprocessWrapper


class LiveExecutor:
	def __init__(self):
		self.logger = setup_logger("auto_live_executor", get_log_path("auto_live_executor.log"))
		self.strategy_name = "AutoGenStrategy"
		self.subprocess_wrapper = SafeSubprocessWrapper("live_executor")

	def _ensure_strategy_present(self) -> bool:
		try:
			# Look for any .py file in strategies
			has_py = any(STRATS_DIR.glob("*.py"))
			if not has_py:
				self.logger.warning("No strategy file found in strategies folder. Please run hyperopt_and_ml.bat first.")
				return False
			return True
		except Exception:
			return False

	def _run_freqtrade_live(self, cfg_path: Path) -> int:
		cmd = [
			"freqtrade", "trade",
			"--config", str(cfg_path),
			"--strategy", self.strategy_name,
			"--strategy-path", str(STRATS_DIR),
			"--logfile", str(Path("user_data") / "logs" / "freqtrade_live.log"),
			"--db-url", "sqlite:///user_data/results/trades.sqlite",
		]
		return_code, stdout, stderr = self.subprocess_wrapper.run_command(cmd, timeout=0, capture_output=False)
		return return_code

	def _simulate_dry_loop(self) -> None:
		self.logger.info("Starting simulated dry-run loop (freqtrade CLI not available). Press Ctrl + C to stop.")
		try:
			while True:
				# Paper trading loop using last candles from DB
				pairs = os.getenv("PAIR_WHITELIST", "BTC/USDT,ETH/USDT").split(",")
				tf = os.getenv("TIMEFRAME", "5m")
				for pair in pairs:
					candles = fetch_market(pair, tf, limit=200)
					if not candles:
						continue
					closes = [c.close for c in candles][::-1]
					import pandas as pd
					df = pd.DataFrame({"close": closes})
					df["ema_fast"] = ema(df["close"], 12)
					df["ema_slow"] = ema(df["close"], 26)
					df["rsi"] = compute_rsi(df["close"], 14)
					if len(df) < 30:
						continue
					ema_fast = float(df["ema_fast"].iloc[-1])
					ema_slow = float(df["ema_slow"].iloc[-1])
					rsi_val = float(df["rsi"].iloc[-1])
					price = float(df["close"].iloc[-1])
					open_positions = get_open_trades(pair)
					if not open_positions and ema_fast > ema_slow and rsi_val > 55:
						qty = max(0.0001, float(os.getenv("PAPER_QTY", "0.001")))
						trade_id = open_trade(pair, qty, price)
						self.logger.info(f"[paper] ENTER {pair} qty={qty} price={price} id={trade_id}")
					elif open_positions and (rsi_val < 45 or ema_fast < ema_slow):
						for pos in open_positions:
							close_trade(pos.id, price)
							self.logger.info(f"[paper] EXIT {pair} price={price} id={pos.id}")
					# Periodically report equity
					eq = compute_equity(starting_balance=float(os.getenv("PAPER_START_BAL", "1000")))
					self.logger.info(f"[paper] equity={eq['balance']:.2f} mdd={eq['max_drawdown']:.2%}")
				time.sleep(10)
		except KeyboardInterrupt:
			self.logger.info("Dry-run loop stopped by user")

	@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
	def run(self) -> None:
		if not self._ensure_strategy_present():
			return
		cfg_path = write_config("live_config.json")
		self.logger.info(f"Launching live (paper) with config {cfg_path}")

		# If freqtrade CLI not present, simulate continuous dry-run loop
		if not self.subprocess_wrapper.check_command_exists("freqtrade") or os.getenv("DRY_RUN", "true").lower() == "true":
			self._simulate_dry_loop()
			return

		ret = self._run_freqtrade_live(cfg_path)
		if ret != 0:
			self.logger.warning(f"Freqtrade exited with code {ret}, will retry")
			raise RuntimeError("Freqtrade trade exited non-zero")
		self.logger.info("Freqtrade exited gracefully")



def main():
	LiveExecutor().run()


if __name__ == "__main__":
	main()
