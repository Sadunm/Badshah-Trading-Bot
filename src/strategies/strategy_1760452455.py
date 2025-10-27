class Strategy:
	def __init__(self):
		self.threshold = 2.9904323155910024

	def generate_signal(self, tick, broker_state):
		price = float(tick['price'])
		pos = broker_state.get('positions', {}).get(tick['symbol'], {'qty': 0.0})
		if (price % 10) > (self.threshold + 5):
			return 'BUY' if pos.get('qty', 0.0) == 0 else 'HOLD'
		elif pos.get('qty', 0.0) > 0:
			return 'SELL'
		return 'HOLD'
