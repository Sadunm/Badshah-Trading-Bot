import os
import subprocess
import sys
import shlex
from pathlib import Path
from typing import Iterable
from dotenv import load_dotenv
import pandas as pd


def ensure_dirs(paths: Iterable[Path]) -> None:
	for p in paths:
		p.mkdir(parents=True, exist_ok=True)


def load_env() -> None:
	# Load .env if present
	try:
		load_dotenv(override=False)
	except (UnicodeDecodeError, FileNotFoundError):
		# Skip .env loading if file is corrupted or doesn't exist
		pass


def require_env(keys: list[str]) -> dict[str, str]:
	values: dict[str, str] = {}
	for k in keys:
		v = os.getenv(k)
		if v is None or v == "":
			raise RuntimeError(f"Missing required environment variable: {k}")
		values[k] = v
	return values


def try_import_or_install(packages: list[str]) -> None:
	missing = []
	for pkg in packages:
		mod = pkg.split("==")[0].split("[")[0]
		try:
			__import__(mod)
		except Exception:
			missing.append(pkg)
	if missing:
		subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


# ✅ Safe subprocess wrapper to always use the correct Python from venv
def safe_subprocess(cmd, cwd=None, timeout=600):
	"""
	Run subprocess safely using same Python interpreter as the current venv.
	Prevents 'did not find executable at C:\\Windows\\system32\\python.exe' errors.
	"""
	if isinstance(cmd, str):
		cmd = shlex.split(cmd)

	env = os.environ.copy()
	env["PATH"] = f"{sys.prefix}\\Scripts;{env['PATH']}"
	env["PYTHONHOME"] = sys.prefix

	process = subprocess.run(
		cmd,
		cwd=cwd,
		env=env,
		timeout=timeout,
		text=True,
		capture_output=True
	)

	return {
		"code": process.returncode,
		"stdout": process.stdout,
		"stderr": process.stderr
	}


# Directories
DATA_DIR = Path(os.getenv("FREQTRADE_DATA_DIR", "user_data"))
RESULTS_DIR = DATA_DIR / "results"
LOGS_DIR = DATA_DIR / "logs"
STRATS_DIR = DATA_DIR / "strategies"
CONFIGS_DIR = DATA_DIR / "configs"
DB_PATH = RESULTS_DIR / "factory.sqlite"


def ema(series: pd.Series, span: int) -> pd.Series:
	return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
	delta = series.diff()
	gain = delta.clip(lower=0).rolling(period).mean()
	loss = (-delta.clip(upper=0)).rolling(period).mean()
	rs = gain / (loss.replace(0, 1e-9))
	return 100 - (100 / (1 + rs))
