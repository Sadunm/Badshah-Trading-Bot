import time
import json
import threading
import requests
import random
import math
import logging
import numpy as np
from datetime import datetime
from typing import Dict, Iterator, List, Optional
from websocket import WebSocketApp


class LiveDataFeed:
	def __init__(self, config: Dict):
		self.symbols: List[str] = list(config.get("symbols", [config.get("symbol", "BTCUSDT")]))
		self.interval = config.get("interval", "1m")
		self.ws_enabled = bool(config.get("websocket_enabled", True))
		self.simulate = bool(config.get("simulate", False))
		self.rest_poll_interval_ms = int(config.get("rest_poll_interval_ms", 1000))
		self.reconnect_backoff = int(config.get("reconnect_backoff_seconds", 5))
		self.latency_ms = int(config.get("latency_ms", 100))
		# Fallback controls
		self._no_data_ws_count = 0
		self._no_data_rest_count = 0
		self._max_no_data_ws = int(config.get("max_no_data_ws", 50))  # ~ few seconds
		self._max_no_data_rest = int(config.get("max_no_data_rest", 15))  # ~ 15 sec if 1s poll
		# Simulation parameters
		self.simulate_mode = str(config.get("simulate_mode", "gbm"))  # "gbm" or "rw"
		self.simulate_seed = int(config.get("simulate_seed", 42))
		self.gbm_mu = float(config.get("gbm_mu", 0.0))
		self.gbm_sigma = float(config.get("gbm_sigma", 0.02))
		self.gbm_dt_ms = int(config.get("gbm_dt_ms", self.latency_ms))
		self._ticks: Dict[str, float] = {s: 0.0 for s in self.symbols}
		self._threads: List[threading.Thread] = []
		self._stop = threading.Event()
		self._sim_prices: Dict[str, float] = {s: 20000.0 for s in self.symbols}
		self._rng = random.Random(self.simulate_seed)
		self._data_lock = threading.Lock()  # Protect shared data access
		self.clear_cache()

	def start(self) -> None:
		if self.ws_enabled:
			for symbol in self.symbols:
				thread = threading.Thread(target=self._run_ws, args=(symbol,), daemon=True)
				thread.start()
				self._threads.append(thread)

	def stop(self) -> None:
		self._stop.set()

	def stream_ticks(self) -> Iterator[Dict]:
		"""Yield tick dicts: {symbol, price, ts}. Uses WS if enabled; else REST polling."""
		# Offline simulation path to avoid any live network connections
		if self.simulate:
			while not self._stop.is_set():
				for symbol in self.symbols:
					price = self._simulate_next_price(symbol)
					yield {"symbol": symbol, "price": price, "ts": int(datetime.utcnow().timestamp())}
					time.sleep(self.latency_ms / 1000.0)
			return

		if self.ws_enabled:
			self.start()
			while not self._stop.is_set():
				for symbol in self.symbols:
					# Thread-safe access to shared data
					with self._data_lock:
						price = self._ticks.get(symbol, 0.0)
					
					if price > 0:
						yield {"symbol": symbol, "price": price, "ts": int(datetime.utcnow().timestamp())}
						self._no_data_ws_count = 0
					else:
						self._no_data_ws_count += 1
					time.sleep(self.latency_ms / 1000.0)
				# Auto fallback to REST/simulate if websocket not yielding data
				if self._no_data_ws_count >= self._max_no_data_ws:
					self.ws_enabled = False
					self._no_data_ws_count = 0
					break
			return
		# REST fallback loop
		while not self._stop.is_set():
			for symbol in self.symbols:
				price = self._fetch_price(symbol)
				if price > 0:
					yield {"symbol": symbol, "price": price, "ts": int(datetime.utcnow().timestamp())}
					self._no_data_rest_count = 0
				else:
					self._no_data_rest_count += 1
			time.sleep(self.rest_poll_interval_ms / 1000.0)
			# Auto fallback to simulation if REST not yielding data
			if self._no_data_rest_count >= self._max_no_data_rest:
				self.simulate = True
				self.ws_enabled = False
				self._no_data_rest_count = 0
				# Loop back to simulation branch
				continue

	def _run_ws(self, symbol: str) -> None:
		url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"

		def on_message(_: WebSocketApp, message: str):
			try:
				data = json.loads(message)
				price = float(data.get("p", 0.0))
				if price > 0:
					# Thread-safe update of shared data
					with self._data_lock:
						self._ticks[symbol] = price
			except Exception:
				pass

		def on_error(_: WebSocketApp, error: Exception):
			logging.error(f"WebSocket error: {error}")
			# Will reconnect in outer loop

		while not self._stop.is_set():
			try:
				ws = WebSocketApp(url, on_message=on_message, on_error=on_error)
				ws.run_forever(ping_interval=20, ping_timeout=10)
			except Exception:
				time.sleep(self.reconnect_backoff)
			if self._stop.is_set():
				break

	def _simulate_next_price(self, symbol: str) -> float:
		"""Simulate next price using GBM or simple random walk.

		GBM: S_{t+dt} = S_t * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
		where dt is in seconds scaled from configured milliseconds.
		"""
		base = self._sim_prices.get(symbol, 20000.0)
		if self.simulate_mode.lower() == "gbm":
			# Convert dt to seconds for the stochastic step
			dt = max(1e-6, float(self.gbm_dt_ms) / 1000.0)
			mu = self.gbm_mu
			sigma = max(1e-9, self.gbm_sigma)
			# Box-Muller transform for standard normal
			u1 = max(1e-12, self._rng.random())
			u2 = max(1e-12, self._rng.random())
			z = ( (-2.0 * math.log(u1)) ** 0.5 ) * math.cos(2.0 * math.pi * u2 )
			growth = (mu - 0.5 * sigma * sigma) * dt + sigma * (dt ** 0.5) * z
			base = max(0.01, base * math.exp(growth))
		else:
			# Fallback to bounded random walk
			step = 1 if self._rng.random() >= 0.5 else -1
			base = max(100.0, base + step * 5)
		self._sim_prices[symbol] = base
		return base

	def _fetch_price(self, symbol: str) -> float:
		try:
			resp = requests.get(
				"https://api.binance.com/api/v3/ticker/price",
				params={"symbol": symbol}, timeout=5
			)
			resp.raise_for_status()
			data = resp.json()
			price = float(data["price"])
			if not np.isfinite(price) or price <= 0:
				logging.warning(f"Invalid price received for {symbol}: {price}")
				return 0.0
			return price
		except requests.exceptions.RequestException as e:
			logging.error(f"Network error fetching price for {symbol}: {e}")
			return 0.0
		except (ValueError, KeyError) as e:
			logging.error(f"Data parsing error for {symbol}: {e}")
			return 0.0
		except Exception as e:
			logging.exception(f"Unexpected error fetching price for {symbol}: {e}")
			return 0.0

	def backfill_klines(self, symbol: str, limit: int = 100) -> List[Dict]:
		try:
			resp = requests.get(
				"https://api.binance.com/api/v3/klines",
				params={"symbol": symbol, "interval": self.interval, "limit": limit}, timeout=10
			)
			resp.raise_for_status()
			rows = resp.json()
			if not isinstance(rows, list):
				logging.warning(f"Invalid klines data format for {symbol}")
				return []
			candles: List[Dict] = []
			for r in rows:
				try:
					# Validate data before processing
					if len(r) < 6:
						logging.warning(f"Incomplete kline data for {symbol}")
						continue
					open_price = float(r[1])
					high_price = float(r[2])
					low_price = float(r[3])
					close_price = float(r[4])
					volume = float(r[5])
					
					# Validate price data
					if not all(np.isfinite([open_price, high_price, low_price, close_price, volume])):
						logging.warning(f"Invalid price data in kline for {symbol}")
						continue
					if any(p <= 0 for p in [open_price, high_price, low_price, close_price]):
						logging.warning(f"Non-positive price in kline for {symbol}")
						continue
					
					candles.append({
						"ts": int(r[0] / 1000),
						"open": open_price,
						"high": high_price,
						"low": low_price,
						"close": close_price,
						"volume": volume,
						"symbol": symbol,
					})
				except (ValueError, IndexError) as e:
					logging.warning(f"Error processing kline data for {symbol}: {e}")
					continue
			return candles
		except requests.exceptions.RequestException as e:
			logging.error(f"Network error fetching klines for {symbol}: {e}")
			return []
		except (ValueError, KeyError) as e:
			logging.error(f"Data parsing error for klines {symbol}: {e}")
			return []
		except Exception as e:
			logging.exception(f"Unexpected error fetching klines for {symbol}: {e}")
			return []

	def clear_cache(self):
		# Thread-safe cache clear
		with self._data_lock:
			self._ticks = {s: 0.0 for s in self.symbols}
			self._sim_prices = {s: 20000.0 for s in self.symbols}