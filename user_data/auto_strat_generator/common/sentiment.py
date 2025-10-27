from __future__ import annotations
import numpy as np
import pandas as pd


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
	# Assumes df has columns: open, high, low, close, volume, and is time-indexed or has date column
	out = df.copy()
	out["ema_fast"] = out["close"].ewm(span=12, adjust=False).mean()
	out["ema_slow"] = out["close"].ewm(span=26, adjust=False).mean()
	out["ema_slope"] = out["ema_fast"].diff()
	# RSI with safe handling for short inputs and zero-loss windows
	delta = out["close"].diff()
	gain = (delta.where(delta > 0, 0)).rolling(14).mean()
	loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
	rs = gain / (loss.replace(0, 1e-9))
	rsi = 100 - (100 / (1 + rs))
	# Clamp to [0, 100] and fill early NaNs with neutral 50
	out["rsi"] = rsi.clip(0, 100).fillna(50)
	# MACD
	macd_line = out["ema_fast"] - out["ema_slow"]
	signal = macd_line.ewm(span=9, adjust=False).mean()
	out["macd_hist"] = macd_line - signal
	# Volatility (realized)
	ret = out["close"].pct_change()
	out["vol_realized"] = ret.rolling(48).std().fillna(0.0)
	# Regime
	trend = (out["ema_fast"] > out["ema_slow"]).astype(int)
	chop = (out["vol_realized"] < out["vol_realized"].rolling(240).quantile(0.3).bfill()).astype(int)
	out["regime"] = np.select(
		[(trend == 1) & (chop == 0), (trend == 0) & (chop == 0)],
		[1, -1],
		default=0,
	)
	# Sentiment score in [-1, 1]
	score = (
		(np.tanh(out["ema_slope"].fillna(0)) * 0.35)
		+ (np.tanh((out["rsi"].fillna(50) - 50) / 15) * 0.25)
		+ (np.tanh(out["macd_hist"].fillna(0)) * 0.25)
		- (np.tanh(out["vol_realized"].fillna(0) * 10) * 0.15)
	)
	out["sentiment_score"] = score.clip(-1, 1)
	return out
