from __future__ import annotations
from pathlib import Path
from typing import Any, Dict

from .utils import STRATS_DIR


STRAT_TEMPLATE = """
from freqtrade.strategy.interface import IStrategy
import pandas as pd

class {class_name}(IStrategy):
    timeframe = "{timeframe}"
    minimal_roi = {minimal_roi}
    stoploss = {stoploss}
    trailing_stop = {trailing_stop}
    process_only_new_candles = True
    startup_candle_count = 200

    def informative_pairs(self):
        return []

    def populate_indicators(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = df.copy()
        # Simple indicators to align with hyperopt params
        df['ema_fast'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=26, adjust=False).mean()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss.replace(0, 1e-9))
        df['rsi'] = 100 - (100 / (1 + rs))
        macd_line = df['ema_fast'] - df['ema_slow']
        signal = macd_line.ewm(span=9, adjust=False).mean()
        df['macd_hist'] = macd_line - signal
        return df

    def populate_entry_trend(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = df.copy()
        cond_buy = (
            (df['ema_fast'] > df['ema_slow']) &
            (df['rsi'] > {rsi_buy}) &
            (df['macd_hist'] > 0)
        )
        df.loc[cond_buy, 'enter_long'] = 1
        return df

    def populate_exit_trend(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = df.copy()
        cond_sell = (
            (df['rsi'] < {rsi_sell}) |
            (df['macd_hist'] < 0)
        )
        df.loc[cond_sell, 'exit_long'] = 1
        return df
"""


def write_strategy(params: Dict[str, Any], name: str = "AutoGenStrategy") -> Path:
	STRATS_DIR.mkdir(parents=True, exist_ok=True)
	minimal_roi = params.get("minimal_roi", {"0": 0.10, "60": 0.05, "120": 0.025, "240": 0})
	stoploss = params.get("stoploss", -0.10)
	trailing_stop = params.get("trailing_stop", False)
	timeframe = params.get("timeframe", "5m")
	rsi_buy = params.get("rsi_buy", 55)
	rsi_sell = params.get("rsi_sell", 45)

	content = STRAT_TEMPLATE.format(
		class_name=name,
		timeframe=timeframe,
		minimal_roi=minimal_roi,
		stoploss=stoploss,
		trailing_stop=trailing_stop,
		rsi_buy=rsi_buy,
		rsi_sell=rsi_sell,
	)
	path = STRATS_DIR / f"{name}.py"
	path.write_text(content, encoding="utf-8")
	return path
