class Strategy:
	def __init__(self):
		self.rsi_buy = 55
		self.rsi_sell = 45
		self.tp_mult = 2.5870827917733457
		self.sl_mult = 0.8446952189916546

	def _ema(self, prev: float, price: float, span: int, k: float, init: float) -> float:
		# Single-step EMA update with smoothing factor k; init used for first value
		return (price * k) + (prev * (1.0 - k)) if prev > 0 else init

	def generate_signal(self, tick, broker_state):
		price = float(tick['price'])
		state = broker_state.get('indicators', {})
		f12 = float(state.get('ema_fast', 0.0))
		f26 = float(state.get('ema_slow', 0.0))
		# k for EMA spans 12 and 26 assuming per-tick smoothing
		k12 = 2.0 / (12 + 1)
		k26 = 2.0 / (26 + 1)
		f12 = self._ema(f12, price, 12, k12, price)
		f26 = self._ema(f26, price, 26, k26, price)
		# Minimal RSI proxy over ticks using price momentum gates
		momentum = 1 if price >= state.get('last_price', price) else -1
		pos = broker_state.get('positions', {}).get(tick['symbol'], {'qty': 0.0, 'entry_price': 0.0})
		gate_buy = (f12 > f26) and (momentum > 0)
		gate_sell = (f12 < f26) or (momentum < 0)
		# Decide actions
		if gate_buy and pos.get('qty', 0.0) == 0:
			return 'BUY'
		elif pos.get('qty', 0.0) > 0:
			entry = float(pos.get('entry_price', 0.0) or 0.0)
			tp = entry * (1.0 + 0.002 * self.tp_mult)
			sl = entry * (1.0 - 0.001 * self.sl_mult)
			if price >= tp or price <= sl or gate_sell:
				return 'SELL'
		return 'HOLD'
