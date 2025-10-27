"""
Centralized Error Handling and Recovery Utilities
Provides comprehensive error handling, logging, and recovery mechanisms
"""

from __future__ import annotations
import traceback
import sys
from typing import Any, Callable, Dict, Optional, Type, Union
from functools import wraps
import logging
from datetime import datetime

from .logging_utils import setup_logger, get_log_path


class TradingSystemError(Exception):
    """Base exception for trading system errors"""
    pass


class DataError(TradingSystemError):
    """Data-related errors"""
    pass


class NetworkError(TradingSystemError):
    """Network connectivity errors"""
    pass


class ConfigurationError(TradingSystemError):
    """Configuration-related errors"""
    pass


class ValidationError(TradingSystemError):
    """Data validation errors"""
    pass


class SystemError(TradingSystemError):
    """System-level errors"""
    pass


class ErrorHandler:
    """Centralized error handling and recovery"""
    
    def __init__(self, logger_name: str = "error_handler"):
        self.logger = setup_logger(logger_name, get_log_path(f"{logger_name}.log"))
        self.error_counts: Dict[str, int] = {}
        self.max_retries = 3
        
    def handle_error(
        self, 
        error: Exception, 
        context: str = "", 
        recoverable: bool = True,
        retry_count: int = 0
    ) -> bool:
        """
        Handle an error with appropriate logging and recovery
        
        Args:
            error: The exception that occurred
            context: Context where the error occurred
            recoverable: Whether this error is recoverable
            retry_count: Current retry count
            
        Returns:
            True if error was handled successfully, False otherwise
        """
        error_type = type(error).__name__
        error_key = f"{error_type}_{context}"
        
        # Track error frequency
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Log error details
        self.logger.error(
            f"Error in {context}: {error_type}: {str(error)}",
            extra={
                "error_type": error_type,
                "context": context,
                "retry_count": retry_count,
                "error_count": self.error_counts[error_key],
                "traceback": traceback.format_exc()
            }
        )
        
        # Determine if we should retry
        if recoverable and retry_count < self.max_retries:
            if self.error_counts[error_key] <= self.max_retries:
                self.logger.info(f"Retrying {context} (attempt {retry_count + 1}/{self.max_retries})")
                return True
            else:
                self.logger.error(f"Too many errors for {context}, giving up")
                return False
        else:
            self.logger.error(f"Non-recoverable error in {context}")
            return False
    
    def safe_execute(
        self, 
        func: Callable, 
        *args, 
        context: str = "", 
        default_return: Any = None,
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """
        Safely execute a function with error handling and retries
        
        Args:
            func: Function to execute
            *args: Function arguments
            context: Context for error logging
            default_return: Value to return on failure
            max_retries: Maximum number of retries
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or default_return on failure
        """
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not self.handle_error(e, context, retry_count=attempt):
                    return default_return
                
                if attempt < max_retries:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        return default_return
    
    def validate_data(self, data: Any, data_type: str, required_fields: list = None) -> bool:
        """
        Validate data with comprehensive error checking
        
        Args:
            data: Data to validate
            data_type: Type of data for context
            required_fields: List of required fields
            
        Returns:
            True if data is valid, False otherwise
        """
        try:
            if data is None:
                raise ValidationError(f"{data_type} is None")
            
            if isinstance(data, dict) and required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    raise ValidationError(f"{data_type} missing required fields: {missing_fields}")
            
            return True
            
        except Exception as e:
            self.handle_error(e, f"data_validation_{data_type}")
            return False
    
    def cleanup_resources(self, resources: Dict[str, Any]) -> None:
        """
        Clean up resources safely
        
        Args:
            resources: Dictionary of resources to clean up
        """
        for name, resource in resources.items():
            try:
                if hasattr(resource, 'close'):
                    resource.close()
                elif hasattr(resource, 'disconnect'):
                    resource.disconnect()
                elif hasattr(resource, 'stop'):
                    resource.stop()
                self.logger.debug(f"Cleaned up resource: {name}")
            except Exception as e:
                self.handle_error(e, f"cleanup_{name}")


def error_handler(
    context: str = "",
    default_return: Any = None,
    max_retries: int = 3,
    recoverable: bool = True
):
    """
    Decorator for automatic error handling
    
    Args:
        context: Context for error logging
        default_return: Value to return on failure
        max_retries: Maximum number of retries
        recoverable: Whether errors are recoverable
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler()
            return handler.safe_execute(
                func, *args, 
                context=context or func.__name__,
                default_return=default_return,
                max_retries=max_retries,
                **kwargs
            )
        return wrapper
    return decorator


def validate_environment_setup() -> bool:
    """Validate that the environment is properly set up"""
    handler = ErrorHandler()
    
    try:
        # Check Python version
        if sys.version_info < (3, 8):
            raise SystemError(f"Python 3.8+ required, got {sys.version}")
        
        # Check required modules
        required_modules = [
            'pandas', 'numpy', 'sqlalchemy', 'rich', 
            'tenacity', 'scikit-learn', 'binance'
        ]
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError as e:
                raise SystemError(f"Required module {module} not found: {e}")
        
        # Check file permissions
        import os
        if not os.access('.', os.W_OK):
            raise SystemError("No write permission in current directory")
        
        handler.logger.info("Environment validation passed")
        return True
        
    except Exception as e:
        handler.handle_error(e, "environment_validation")
        return False


def create_error_report() -> Dict[str, Any]:
    """Create a comprehensive error report"""
    handler = ErrorHandler()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "error_counts": handler.error_counts,
        "total_errors": sum(handler.error_counts.values()),
        "most_common_error": max(handler.error_counts.items(), key=lambda x: x[1]) if handler.error_counts else None,
        "system_info": {
            "python_version": sys.version,
            "platform": sys.platform
        }
    }


# Global error handler instance
global_error_handler = ErrorHandler("global_error_handler")

