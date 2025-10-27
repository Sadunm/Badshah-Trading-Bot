from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict
import math


@dataclass
class BanditRL:
	alpha: float = 0.2  # learning rate
	decay: float = 0.995
	roi_weights: Dict[str, float] = field(default_factory=lambda: {"0": 0.10, "60": 0.05, "120": 0.025, "240": 0.0})
	risk_weight: float = 1.0

	def update(self, roi_observed: float, drawdown: float) -> None:
		reward = roi_observed - 0.5 * drawdown
		# Adjust earlier ROI steps more aggressively
		for k in sorted(self.roi_weights.keys(), key=lambda x: int(x)):
			w = self.roi_weights[k]
			grad = self.alpha * reward * (1.0 if int(k) <= 120 else 0.5)
			self.roi_weights[k] = max(0.0, w + grad)
		self.risk_weight = max(0.2, min(2.0, self.risk_weight * (1.0 - self.alpha * drawdown)))
		self.alpha *= self.decay

	def as_minimal_roi(self) -> Dict[str, float]:
		return dict(sorted(self.roi_weights.items(), key=lambda kv: int(kv[0])))
