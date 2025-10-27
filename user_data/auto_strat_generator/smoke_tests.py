from __future__ import annotations
import subprocess
from binance.spot import Spot

from .common.logging_utils import setup_logger, get_log_path


def run_smoke_tests() -> None:
	logger = setup_logger("smoke_tests", get_log_path("smoke_tests.log"))
	ok = True
	# Strategy discovery
	try:
		res = subprocess.run(["freqtrade", "list-strategies"], capture_output=True, text=True, check=False)
		if res.returncode != 0:
			logger.warning(f"Strategy listing failed: {res.stderr.strip()}")
			ok = False
		else:
			logger.info("Freqtrade strategy listing OK")
	except Exception as e:
		logger.warning(f"Freqtrade not available: {e}")
		ok = False
	# Binance public ping
	try:
		Spot().ping()
		logger.info("Binance ping OK")
	except Exception as e:
		logger.warning(f"Binance ping failed: {e}")
		ok = False
	if ok:
		logger.info("Smoke tests passed")
	else:
		logger.warning("Smoke tests completed with warnings")


if __name__ == "__main__":
	run_smoke_tests()
