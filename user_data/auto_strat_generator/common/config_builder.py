from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, Any

from .utils import CONFIGS_DIR


def build_config() -> Dict[str, Any]:
	pairs = os.getenv("PAIR_WHITELIST", "BTC/USDT,ETH/USDT").split(",")
	return {
		"max_open_trades": 3,
		"stake_currency": os.getenv("QUOTE", "USDT"),
		"stake_amount": float(os.getenv("STAKE_AMOUNT", "50")),
		"dry_run": os.getenv("DRY_RUN", "true").lower() == "true",
		"timeframe": os.getenv("TIMEFRAME", "5m"),
		"strategy": "AutoGenStrategy",
		"strategy_path": str(Path("user_data") / "strategies"),
		"dataformat_ohlcv": "jsongz",
		"cancel_open_orders_on_exit": True,
		"bid_strategy": {"price_side": "bid", "ask_last_balance": 0.0},
		"exchange": {
			"name": os.getenv("EXCHANGE", "binance"),
			"key": os.getenv("BINANCE_API_KEY", ""),
			"secret": os.getenv("BINANCE_API_SECRET", ""),
			"ccxt_config": {"enableRateLimit": True},
			"ccxt_async_config": {"enableRateLimit": True},
			"pair_whitelist": pairs,
		},
		"pairlists": [{"method": "StaticPairList"}],
		"protections": [
			{"method": "CooldownPeriod", "stop_duration": 60},
			{"method": "StoplossGuard", "lookback_period_candles": 48, "trade_limit": 3, "stop_duration_candles": 48, "only_per_pair": False},
		],
	}


def write_config(filename: str = "generated_config.json") -> Path:
	CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
	cfg = build_config()
	path = CONFIGS_DIR / filename
	path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
	return path
