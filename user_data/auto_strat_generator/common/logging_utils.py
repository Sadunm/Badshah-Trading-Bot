import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler


def setup_logger(name: str, logfile: Path, level: int = logging.INFO) -> logging.Logger:
	logfile.parent.mkdir(parents=True, exist_ok=True)

	logger = logging.getLogger(name)
	logger.setLevel(level)
	logger.propagate = False

	# Avoid duplicate handlers on re-init
	if logger.handlers:
		return logger

	console = Console()
	rich_handler = RichHandler(console=console, show_time=True, show_path=False, rich_tracebacks=True)
	rich_handler.setLevel(level)

	file_handler = RotatingFileHandler(str(logfile), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
	file_fmt = logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
	file_handler.setFormatter(file_fmt)
	file_handler.setLevel(level)

	logger.addHandler(rich_handler)
	logger.addHandler(file_handler)
	return logger


def get_log_path(filename: str) -> Path:
	return Path("user_data") / "logs" / filename
