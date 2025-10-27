import os
import time
import threading
from typing import Dict

import psutil
import requests
from loguru import logger


class ResourceMonitor:
	def __init__(self, log_dir: str, cpu_limit: float = 90.0, ram_limit: float = 90.0, net_url: str = "https://www.google.com", interval_sec: float = 5.0):
		self.cpu_limit = float(cpu_limit)
		self.ram_limit = float(ram_limit)
		self.net_url = net_url
		self.interval = float(interval_sec)
		self._stop = threading.Event()
		self._cooldown = threading.Event()
		self.alerts_path = os.path.join(log_dir, "alerts.log")
		os.makedirs(log_dir, exist_ok=True)
		logger.add(self.alerts_path, rotation="1 MB")

	def start(self) -> None:
		threading.Thread(target=self._run, daemon=True).start()

	def stop(self) -> None:
		self._stop.set()

	def should_cooldown(self) -> bool:
		# Disabled for simulation mode
		return False

	def _log_alert(self, msg: str) -> None:
		logger.warning(msg)

	def _run(self) -> None:
		# Prime CPU percent
		psutil.cpu_percent(interval=None)
		while not self._stop.is_set():
			try:
				cpu = float(psutil.cpu_percent(interval=None))
				ram = float(psutil.virtual_memory().percent)
				ok_net = True
				try:
					requests.get(self.net_url, timeout=3)
				except Exception:
					ok_net = False
				cpu_breach = (self.cpu_limit > 0) and (cpu >= self.cpu_limit)
				ram_breach = (self.ram_limit > 0) and (ram >= self.ram_limit)
				if cpu_breach or ram_breach or not ok_net:
					self._cooldown.set()
					reason = []
					if cpu_breach:
						reason.append(f"CPU {cpu:.1f}% >= {self.cpu_limit:.1f}%")
					if ram_breach:
						reason.append(f"RAM {ram:.1f}% >= {self.ram_limit:.1f}%")
					if not ok_net:
						reason.append("Connectivity check failed")
					self._log_alert("; ".join(["Cooldown triggered"] + reason))
				else:
					self._cooldown.clear()
			except Exception:
				# Avoid stopping the monitor due to unexpected errors
				pass
			time.sleep(self.interval)


