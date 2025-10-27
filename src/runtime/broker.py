from typing import Dict, Optional
import numpy as np
import logging
from datetime import datetime


class DemoBroker:
	def __init__(self, config: Dict):
		self.start_balance = float(config.get("starting_balance", 10000.0))
		self.balance = self.start_balance
		self.fee_pct = float(config.get("fee_pct", 0.05)) / 100.0
		self.slippage_pct = float(config.get("slippage_pct", 0.01)) / 100.0
		self.risk_per_trade_pct = float(config.get("risk_per_trade_pct", 1.0)) / 100.0
		self.leverage = int(config.get("leverage", 1))
		self.positions: Dict[str, Dict] = {}  # symbol -> {qty, entry_price}
		self.trade_log: list[Dict] = []
		self.indicators: Dict = {}
		self.max_loss_per_trade = float(config.get("max_loss_per_trade", 0.02)) * self.start_balance
		self.daily_loss_limit = float(config.get("daily_loss_limit", 0.1)) * self.start_balance
		self.daily_loss_accum = 0.0
		self.current_trading_date = None  # FIX: Initialize current_trading_date!

	def get_state(self) -> Dict:
		return {
			"balance": self.balance,
			"positions": self.positions,
			"leverage": self.leverage,
			"indicators": self.indicators,
		}

	def _calc_trade_qty(self, price: float) -> float:
		risk_amount = self.balance * self.risk_per_trade_pct * self.leverage
		if price <= 0 or not np.isfinite(price):
			return 0.0
		try:
			qty = risk_amount / price
			return np.clip(qty, 0.0, self.balance / price) if np.isfinite(qty) else 0.0
		except (ZeroDivisionError, OverflowError):
			return 0.0

	def reset_daily_state(self):
		"""Reset daily state counters - MUST be called at start of each trading day"""
		if self.daily_loss_accum != 0:
			logging.info(f"Daily state reset: Previous day loss = {self.daily_loss_accum:.2f}")
		self.daily_loss_accum = 0.0
		self.current_trading_date = datetime.now().date()
	
	def check_daily_reset(self, current_timestamp=None):
		"""Check if we need to reset daily counters"""
		if current_timestamp is None:
			current_timestamp = datetime.now()
		
		current_date = current_timestamp.date() if hasattr(current_timestamp, 'date') else None
		if current_date and current_date != self.current_trading_date:
			self.reset_daily_state()
	
	def execute(self, symbol: str, action: str, price: float, timestamp=None) -> Optional[Dict]:
		try:
			# Check if daily reset is needed
			self.check_daily_reset(timestamp)
			
			# Validate inputs
			if not np.isfinite(price) or price <= 0:
				return None
			
			# FIX: Apply slippage correctly - increase for BUY, decrease for SELL
			if action == "BUY":
				px = price * (1.0 + self.slippage_pct)  # Pay more when buying
			elif action == "SELL":
				px = price * (1.0 - self.slippage_pct)  # Receive less when selling
			else:
				px = price
			
			if not np.isfinite(px) or px <= 0:
				return None
				
			pos = self.positions.get(symbol, {"qty": 0.0, "entry_price": 0.0})
			
			if action == "BUY" and pos["qty"] == 0.0 and px > 0:
				# FIX: Risk gating - stop if daily loss breached (daily_loss_accum is negative for losses)
				if abs(self.daily_loss_accum) >= self.daily_loss_limit:
					logging.warning(f"Daily loss limit reached: {self.daily_loss_accum:.2f}")
					return None
				qty = self._calc_trade_qty(px)
				if qty <= 0:
					return None
				cost = qty * px
				fee = cost * self.fee_pct
				total_cost = cost + fee
				
				if total_cost <= self.balance and qty > 0 and np.isfinite(total_cost):
					self.balance -= total_cost
					self.positions[symbol] = {"qty": qty, "entry_price": px}
					order = {"symbol": symbol, "side": "BUY", "price": px, "qty": qty}
					self.trade_log.append(order)
					return order

			# FIX: Better float comparison with tolerance
			if action == "SELL" and pos["qty"] > 0.00000001 and px > 0:
				proceeds = pos["qty"] * px
				sell_fee = proceeds * self.fee_pct
				entry_cost = pos["qty"] * pos["entry_price"]
				# FIX: Account for BOTH buy and sell fees in PnL
				buy_fee = entry_cost * self.fee_pct  # Fee paid when we bought
				pnl = proceeds - sell_fee - entry_cost - buy_fee  # True profit/loss
				
				# Enforce per-trade max loss (cap realized loss)
				if pnl < -self.max_loss_per_trade:
					logging.warning(f"Max loss per trade hit: capping PnL from {pnl:.2f} to {-self.max_loss_per_trade:.2f}")
					pnl = -self.max_loss_per_trade
				
				net_proceeds = proceeds - sell_fee
				if np.isfinite(net_proceeds) and np.isfinite(pnl):
					self.balance += net_proceeds
					order = {"symbol": symbol, "side": "SELL", "price": px, "qty": pos["qty"], "pnl": pnl}
					# FIX: Delete position instead of setting to zero to prevent memory buildup
					del self.positions[symbol]
					self.trade_log.append(order)
					self.daily_loss_accum += pnl
					return order

			return None
		except Exception as e:
			logging.exception(f"Error in broker execute: {e}")
			return None
