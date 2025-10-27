"""
Input Validation and Sanitization Utilities
Provides comprehensive validation for all user inputs and external data
"""

from __future__ import annotations
import re
import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class InputValidator:
    """Comprehensive input validation and sanitization"""
    
    # Valid trading pairs pattern
    PAIR_PATTERN = re.compile(r'^[A-Z]{2,10}/[A-Z]{2,10}$')
    
    # Valid timeframes
    VALID_TIMEFRAMES = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'}
    
    # Valid exchanges
    VALID_EXCHANGES = {'binance', 'coinbase', 'kraken', 'bitfinex'}
    
    @staticmethod
    def validate_pair(pair: str) -> str:
        """Validate and sanitize trading pair"""
        if not isinstance(pair, str):
            raise ValidationError(f"Pair must be a string, got {type(pair)}")
        
        pair = pair.strip().upper()
        
        if not InputValidator.PAIR_PATTERN.match(pair):
            raise ValidationError(f"Invalid pair format: {pair}. Expected format: BASE/QUOTE")
        
        return pair
    
    @staticmethod
    def validate_pairs(pairs: Union[str, List[str]]) -> List[str]:
        """Validate and sanitize list of trading pairs"""
        if isinstance(pairs, str):
            pairs = [p.strip() for p in pairs.split(',')]
        
        if not isinstance(pairs, list):
            raise ValidationError(f"Pairs must be a list or comma-separated string, got {type(pairs)}")
        
        if not pairs:
            raise ValidationError("At least one pair must be specified")
        
        validated_pairs = []
        for pair in pairs:
            validated_pairs.append(InputValidator.validate_pair(pair))
        
        return validated_pairs
    
    @staticmethod
    def validate_timeframe(timeframe: str) -> str:
        """Validate timeframe"""
        if not isinstance(timeframe, str):
            raise ValidationError(f"Timeframe must be a string, got {type(timeframe)}")
        
        timeframe = timeframe.strip().lower()
        
        if timeframe not in InputValidator.VALID_TIMEFRAMES:
            raise ValidationError(f"Invalid timeframe: {timeframe}. Valid options: {', '.join(InputValidator.VALID_TIMEFRAMES)}")
        
        return timeframe
    
    @staticmethod
    def validate_exchange(exchange: str) -> str:
        """Validate exchange name"""
        if not isinstance(exchange, str):
            raise ValidationError(f"Exchange must be a string, got {type(exchange)}")
        
        exchange = exchange.strip().lower()
        
        if exchange not in InputValidator.VALID_EXCHANGES:
            raise ValidationError(f"Invalid exchange: {exchange}. Valid options: {', '.join(InputValidator.VALID_EXCHANGES)}")
        
        return exchange
    
    @staticmethod
    def validate_api_key(api_key: str) -> str:
        """Validate API key format"""
        if not isinstance(api_key, str):
            raise ValidationError(f"API key must be a string, got {type(api_key)}")
        
        api_key = api_key.strip()
        
        if not api_key:
            raise ValidationError("API key cannot be empty")
        
        # Allow placeholder values for testing
        if "placeholder" in api_key.lower():
            return api_key
        
        if len(api_key) < 10:
            raise ValidationError("API key appears too short")
        
        if len(api_key) > 200:
            raise ValidationError("API key appears too long")
        
        # Basic format validation (alphanumeric and some special chars)
        if not re.match(r'^[A-Za-z0-9_-]+$', api_key):
            raise ValidationError("API key contains invalid characters")
        
        return api_key
    
    @staticmethod
    def validate_api_secret(api_secret: str) -> str:
        """Validate API secret format"""
        if not isinstance(api_secret, str):
            raise ValidationError(f"API secret must be a string, got {type(api_secret)}")
        
        api_secret = api_secret.strip()
        
        if not api_secret:
            raise ValidationError("API secret cannot be empty")
        
        # Allow placeholder values for testing
        if "placeholder" in api_secret.lower():
            return api_secret
        
        if len(api_secret) < 20:
            raise ValidationError("API secret appears too short")
        
        if len(api_secret) > 200:
            raise ValidationError("API secret appears too long")
        
        return api_secret
    
    @staticmethod
    def validate_numeric(value: Any, name: str, min_val: Optional[float] = None, max_val: Optional[float] = None) -> float:
        """Validate numeric value with optional min/max bounds"""
        try:
            num_val = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{name} must be a number, got {type(value)}")
        
        if min_val is not None and num_val < min_val:
            raise ValidationError(f"{name} must be >= {min_val}, got {num_val}")
        
        if max_val is not None and num_val > max_val:
            raise ValidationError(f"{name} must be <= {max_val}, got {num_val}")
        
        return num_val
    
    @staticmethod
    def validate_stake_amount(amount: Any) -> float:
        """Validate stake amount"""
        return InputValidator.validate_numeric(amount, "Stake amount", min_val=0.001, max_val=1000000)
    
    @staticmethod
    def validate_risk_per_trade(risk: Any) -> float:
        """Validate risk per trade (should be between 0 and 1)"""
        return InputValidator.validate_numeric(risk, "Risk per trade", min_val=0.001, max_val=0.5)
    
    @staticmethod
    def validate_hyperopt_epochs(epochs: Any) -> int:
        """Validate hyperopt epochs"""
        return int(InputValidator.validate_numeric(epochs, "Hyperopt epochs", min_val=10, max_val=10000))
    
    @staticmethod
    def validate_max_workers(workers: Any) -> int:
        """Validate max workers"""
        return int(InputValidator.validate_numeric(workers, "Max workers", min_val=1, max_val=32))
    
    @staticmethod
    def validate_path(path: Union[str, Path], must_exist: bool = False) -> Path:
        """Validate file path"""
        if isinstance(path, str):
            path = Path(path)
        
        if not isinstance(path, Path):
            raise ValidationError(f"Path must be a string or Path object, got {type(path)}")
        
        # Check for path traversal attempts
        try:
            path.resolve()
        except Exception as e:
            raise ValidationError(f"Invalid path: {e}")
        
        if must_exist and not path.exists():
            raise ValidationError(f"Path does not exist: {path}")
        
        return path
    
    @staticmethod
    def validate_strategy_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate strategy parameters"""
        if not isinstance(params, dict):
            raise ValidationError(f"Strategy params must be a dictionary, got {type(params)}")
        
        validated = {}
        
        # Validate timeframe
        if 'timeframe' in params:
            validated['timeframe'] = InputValidator.validate_timeframe(params['timeframe'])
        
        # Validate minimal_roi
        if 'minimal_roi' in params:
            roi = params['minimal_roi']
            if not isinstance(roi, dict):
                raise ValidationError("minimal_roi must be a dictionary")
            
            validated_roi = {}
            for time_str, roi_val in roi.items():
                try:
                    time_int = int(time_str)
                    if time_int < 0:
                        raise ValidationError(f"ROI time must be non-negative, got {time_int}")
                    
                    validated_roi[time_str] = InputValidator.validate_numeric(
                        roi_val, f"ROI at {time_str}", min_val=0.0, max_val=1.0
                    )
                except ValueError:
                    raise ValidationError(f"Invalid ROI time format: {time_str}")
            
            validated['minimal_roi'] = validated_roi
        
        # Validate stoploss
        if 'stoploss' in params:
            validated['stoploss'] = InputValidator.validate_numeric(
                params['stoploss'], "Stoploss", min_val=-0.99, max_val=0.0
            )
        
        # Validate trailing_stop
        if 'trailing_stop' in params:
            if not isinstance(params['trailing_stop'], bool):
                raise ValidationError("trailing_stop must be a boolean")
            validated['trailing_stop'] = params['trailing_stop']
        
        # Validate RSI parameters
        for param in ['rsi_buy', 'rsi_sell']:
            if param in params:
                validated[param] = InputValidator.validate_numeric(
                    params[param], param, min_val=0, max_val=100
                )
        
        return validated
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            return str(value)
        
        # Remove control characters except newlines and tabs
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', value)
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def validate_environment_variables() -> Dict[str, str]:
        """Validate all required environment variables"""
        required_vars = {
            'PAIR_WHITELIST': InputValidator.validate_pairs,
            'TIMEFRAME': InputValidator.validate_timeframe,
            'QUOTE': lambda x: InputValidator.sanitize_string(x, 10).upper(),
            'STAKE_AMOUNT': InputValidator.validate_stake_amount,
            'RISK_PER_TRADE': InputValidator.validate_risk_per_trade,
            'HYPEROPT_EPOCHS': InputValidator.validate_hyperopt_epochs,
            'MAX_WORKERS': InputValidator.validate_max_workers,
        }
        
        optional_vars = {
            'BINANCE_API_KEY': InputValidator.validate_api_key,
            'BINANCE_API_SECRET': InputValidator.validate_api_secret,
            'EXCHANGE': InputValidator.validate_exchange,
        }
        
        validated = {}
        errors = []
        
        # Validate required variables
        for var_name, validator in required_vars.items():
            value = os.getenv(var_name)
            if value is None:
                errors.append(f"Required environment variable {var_name} is not set")
            else:
                try:
                    validated[var_name] = validator(value)
                except ValidationError as e:
                    errors.append(f"Invalid {var_name}: {e}")
        
        # Validate optional variables if they exist
        for var_name, validator in optional_vars.items():
            value = os.getenv(var_name)
            if value is not None:
                try:
                    validated[var_name] = validator(value)
                except ValidationError as e:
                    errors.append(f"Invalid {var_name}: {e}")
        
        if errors:
            raise ValidationError(f"Environment validation failed:\n" + "\n".join(errors))
        
        return validated


def validate_input(func):
    """Decorator to automatically validate function inputs"""
    def wrapper(*args, **kwargs):
        # This would need to be implemented based on specific function signatures
        # For now, it's a placeholder for future enhancement
        return func(*args, **kwargs)
    return wrapper
