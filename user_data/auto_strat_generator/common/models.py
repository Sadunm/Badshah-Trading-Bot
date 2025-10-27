from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Regime(str, Enum):
	trend = "trend"
	mean_revert = "mean_revert"
	chop = "chop"


class Candle(BaseModel):
	timestamp: int
	open: float
	high: float
	low: float
	close: float
	volume: float
	pair: str
	timeframe: str


class MarketSnapshot(BaseModel):
	pair: str
	timeframe: str
	candles: List[Candle]
	features: Dict[str, float] = Field(default_factory=dict)
	created_at: datetime = Field(default_factory=datetime.utcnow)


class HyperoptResult(BaseModel):
	strategy_name: str
	params: Dict[str, Any]
	score: float
	period: Dict[str, str]
	samples: int
	metadata: Dict[str, Any] = Field(default_factory=dict)


class BacktestSummary(BaseModel):
	strategy_name: str
	roi: float
	sharpe: float
	max_drawdown: float
	winrate: float
	exposure: float
	confidence: float
	period: Dict[str, str]
	by_pair: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class RLState(BaseModel):
	# Simple bandit weights for ROI steps and risk controls
	roi_weights: Dict[str, float] = Field(default_factory=dict)
	risk_weight: float = 1.0
	updated_at: datetime = Field(default_factory=datetime.utcnow)


class StrategyRecord(BaseModel):
	name: str
	file_path: str
	params: Dict[str, Any]
	score: float
	created_at: datetime = Field(default_factory=datetime.utcnow)
	is_live: bool = False
