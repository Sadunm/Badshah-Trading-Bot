from __future__ import annotations
import os
import subprocess
from typing import List

from binance.spot import Spot

from .logging_utils import setup_logger, get_log_path
from .utils import try_import_or_install
from .input_validator import InputValidator, ValidationError


def validate_environment() -> None:
    logger = setup_logger("validator", get_log_path("validator.log"))
    logger.info("Validating environment...")
    
    # Validate environment variables
    try:
        validated_env = InputValidator.validate_environment_variables()
        logger.info("Environment variables validated successfully")
    except ValidationError as e:
        logger.error(f"Environment validation failed: {e}")
        raise
    
    # Ensure critical packages
    try_import_or_install([
        "pandas", "numpy", "rich", "python-dotenv", "SQLAlchemy", "pydantic", "orjson", "tenacity", "joblib", "scikit-learn", "psutil",
    ])
    
    # Freqtrade presence (optional check)
    try:
        res = subprocess.run(["freqtrade", "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            logger.warning("Freqtrade not found or not in PATH. Continuing without freqtrade validation.")
        else:
            logger.info(f"Freqtrade version: {res.stdout.strip()}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("Freqtrade not found or not in PATH. Continuing without freqtrade validation.")
    
    # Exchange public connectivity
    try:
        Spot().ping()
        logger.info("Binance public ping OK")
    except Exception as e:
        logger.warning(f"Binance ping failed: {e}")
    
    # API keys validation (only warn if missing)
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        logger.warning("API keys missing. Live trading will run in dry-run unless keys are provided.")
    else:
        try:
            InputValidator.validate_api_key(api_key)
            InputValidator.validate_api_secret(api_secret)
            logger.info("API keys format validated successfully")
        except ValidationError as e:
            logger.warning(f"API key validation warning: {e}")
    
    logger.info("Environment validation completed successfully")
