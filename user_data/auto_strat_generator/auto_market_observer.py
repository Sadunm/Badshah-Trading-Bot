from __future__ import annotations
import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd
from binance.spot import Spot as BinanceSpot
from rich.progress import Progress

from .common.logging_utils import setup_logger, get_log_path
from .common.storage import insert_market_rows, atomic_write_json
from .common.utils import ensure_dirs, load_env, DATA_DIR
from .common.sentiment import compute_indicators

try:
	from binance.websocket.spot.websocket_client import SpotWebsocketClient
except Exception:
	SpotWebsocketClient = None  # type: ignore


class MarketObserver:
	def __init__(self, api_key: str | None, api_secret: str | None, quote: str, timeframe: str, pairs: List[str]):
		self.api = BinanceSpot(api_key=api_key or "", api_secret=api_secret or "")
		self.quote = quote
		self.timeframe = timeframe
		self.pairs = pairs
		self.logger = setup_logger("auto_market_observer", get_log_path("auto_market_observer.log"))
		self.market_dir = DATA_DIR / "results" / "market"
		ensure_dirs([self.market_dir])
		self.ws_client = None

	def fetch_snapshot(self) -> None:
		"""Fetch recent candles via REST and persist to DB and JSON shards."""
		self.logger.info(f"Snapshot fetch for {len(self.pairs)} pairs @ {self.timeframe}")
		dry_run = (os.getenv("DRY_RUN", "true").lower() == "true")
		rows: list[dict] = []
		with Progress() as progress:
			task = progress.add_task("Fetching candles", total=len(self.pairs))
			for pair in self.pairs:
				pair_rows: list[dict] = []
				if not dry_run:
					try:
						sym = pair.replace("/", "")
						klines = self.api.klines(symbol=sym, interval=self._tf_to_binance(self.timeframe), limit=200)
						for k in klines:
							ts = int(k[0] // 1000)
							pair_rows.append({
								"pair": pair,
								"timeframe": self.timeframe,
								"timestamp": ts,
								"open": float(k[1]),
								"high": float(k[2]),
								"low": float(k[3]),
								"close": float(k[4]),
								"volume": float(k[5]),
							})
					except Exception as e:
						self.logger.warning(f"REST fetch failed for {pair} ({e}); using offline data if available")
				if not pair_rows:
					pair_rows = self._load_offline_rows(pair)
					if pair_rows:
						self.logger.info(f"Loaded {len(pair_rows)} offline candles for {pair}")
					else:
						self.logger.warning(f"No offline data available for {pair}; skipping")
				rows.extend(pair_rows)
				progress.update(task, advance=1)
		if rows:
			insert_market_rows(rows)
			self._write_json_shard(rows)
			self.logger.info(f"Inserted {len(rows)} candles (REST/offline)")

	def _load_offline_rows(self, pair: str) -> list[dict]:
		"""Load candles from local feather files as an offline fallback.
		Looks for files like 'user_data/data/binance/BTC_USDT-5m.feather'.
		If not found or unreadable, returns an empty list.
		"""
		try:
			base = DATA_DIR / "data" / "binance"
			fname = f"{pair.replace('/', '_')}-{self.timeframe}.feather"
			path = base / fname
			if not path.exists():
				# try uppercase/lowercase variations just in case
				alt = f"{pair.replace('/', '_').upper()}-{self.timeframe}.feather"
				path = base / alt if (base / alt).exists() else path
			if not path.exists():
				return []
			df = pd.read_feather(path)
			# Normalize column names
			cols = {c.lower(): c for c in df.columns}
			def col(name: str) -> str:
				return cols.get(name, name)
			# Determine timestamp column
			ts_col = None
			for candidate in ("timestamp", "ts", "date", "datetime", "time"):
				if candidate in cols:
					ts_col = cols[candidate]
					break
			if ts_col is None:
				# synthesize timestamps if missing
				df = df.reset_index().rename(columns={"index": "timestamp"})
				ts_col = "timestamp"
			# Convert timestamps to seconds
			if pd.api.types.is_datetime64_any_dtype(df[ts_col]):
				df[ts_col] = (pd.to_datetime(df[ts_col]).view("int64") // 1_000_000_000).astype("int64")
			else:
				# try to coerce
				try:
					df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
					df[ts_col] = (df[ts_col].view("int64") // 1_000_000_000).astype("int64")
				except Exception:
					pass
			# Ensure OHLCV columns
			for required in ("open", "high", "low", "close", "volume"):
				if required not in cols and required not in df.columns:
					return []
			df = df.rename(columns={
				col("open"): "open",
				col("high"): "high",
				col("low"): "low",
				col("close"): "close",
				col("volume"): "volume",
				col("timestamp"): "timestamp",
			})
			df = df.sort_values("timestamp").tail(200)
			result: list[dict] = []
			for _, r in df.iterrows():
				try:
					result.append({
						"pair": pair,
						"timeframe": self.timeframe,
						"timestamp": int(r["timestamp"]),
						"open": float(r["open"]),
						"high": float(r["high"]),
						"low": float(r["low"]),
						"close": float(r["close"]),
						"volume": float(r["volume"]),
					})
				except Exception:
					continue
			return result
		except Exception as e:
			self.logger.warning(f"Offline data load failed for {pair}: {e}")
			return []

	async def run_live(self, interval_sec: int = 60) -> None:
		if SpotWebsocketClient is None:
			self.logger.warning("WS client unavailable; falling back to polling.")
			await self._polling_loop(interval_sec)
			return
		
		self.logger.info("Starting live WS stream (1m klines per pair) with polling fallback")
		
		try:
			self.ws_client = SpotWebsocketClient(stream_url="wss://stream.binance.com:9443")
		except Exception as e:
			self.logger.error(f"Failed to create WebSocket client: {e}")
			await self._polling_loop(interval_sec)
			return

		def handle(msg):
			try:
				if not isinstance(msg, dict):
					return
					
				if msg.get("e") == "kline":
					k = msg.get("k", {})
					if not k.get("x"):
						return  # only on kline close
					
					pair = msg.get("s", "")
					if not pair:
						return
						
					pair = pair[:-4] + "/USDT" if pair.endswith("USDT") else pair
					
					# Validate required fields
					required_fields = ["t", "o", "h", "l", "c", "v"]
					if not all(field in k for field in required_fields):
						self.logger.warning(f"Missing required fields in kline data: {k}")
						return
					
					row = {
						"pair": pair,
						"timeframe": self.timeframe,
						"timestamp": int(k["t"] // 1000),
						"open": float(k["o"]),
						"high": float(k["h"]),
						"low": float(k["l"]),
						"close": float(k["c"]),
						"volume": float(k["v"]),
					}
					
					# Validate data ranges
					if row["open"] <= 0 or row["high"] <= 0 or row["low"] <= 0 or row["close"] <= 0:
						self.logger.warning(f"Invalid price data for {pair}: {row}")
						return
					
					insert_market_rows([row])
					self._write_json_shard([row])
					self.logger.info(f"WS candle stored for {row['pair']}")
					
				elif msg.get("e") == "error":
					self.logger.error(f"WebSocket error: {msg}")
					
			except Exception as e:
				self.logger.exception(f"WS handler error: {e}")

		try:
			streams = [f"{p.replace('/', '') .lower()}@kline_1m" for p in self.pairs]
			if not streams:
				self.logger.warning("No pairs configured for WebSocket streaming")
				await self._polling_loop(interval_sec)
				return
				
			self.ws_client.instant_subscribe(streams=streams, id=1, callback=handle)
			self.logger.info(f"Subscribed to {len(streams)} WebSocket streams")
			
			# Keep connection alive with periodic health checks
			last_heartbeat = time.time()
			while True:
				await asyncio.sleep(5)
				
				# Check if connection is still alive
				if time.time() - last_heartbeat > 300:  # 5 minutes
					self.logger.warning("WebSocket connection appears stale, reconnecting...")
					break
					
		except Exception as e:
			self.logger.exception(f"WS connection error: {e}")
		finally:
			try:
				if self.ws_client:
					self.ws_client.stop()
					self.logger.info("WebSocket connection closed")
			except Exception as e:
				self.logger.warning(f"Error closing WebSocket: {e}")
			
			# Fallback to polling
			self.logger.info("Falling back to polling mode")
			await self._polling_loop(interval_sec)

	async def _polling_loop(self, interval_sec: int) -> None:
		self.logger.info("Starting live polling mode")
		while True:
			try:
				self.fetch_snapshot()
			except Exception as e:
				self.logger.exception(f"Live poll failed: {e}")
			await asyncio.sleep(interval_sec)

	def _write_json_shard(self, rows: list[dict]) -> None:
		if not rows:
			return
		df = pd.DataFrame(rows)
		try:
			pair = df["pair"].iloc[0]
			pair_df = df[df["pair"] == pair].sort_values("timestamp")
			pair_df = compute_indicators(pair_df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}))
			score = float(pair_df["sentiment_score"].iloc[-1]) if not pair_df.empty else 0.0
		except Exception:
			score = 0.0
		stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
		path = self.market_dir / f"snapshot_{stamp}.json"
		atomic_write_json(path, {"rows": rows, "sentiment_sample": score})

	@staticmethod
	def _tf_to_binance(tf: str) -> str:
		return tf


def main():
	load_env()
	import os
	pairs = os.getenv("PAIR_WHITELIST", "BTC/USDT,ETH/USDT").split(",")
	mo = MarketObserver(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"), os.getenv("QUOTE", "USDT"), os.getenv("TIMEFRAME", "5m"), pairs)
	mo.fetch_snapshot()


if __name__ == "__main__":
	asyncio.run(main())
