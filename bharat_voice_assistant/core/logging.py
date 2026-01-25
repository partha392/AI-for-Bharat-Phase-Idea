"""
Logging configuration for the Bharat Voice Assistant.

This module provides structured logging with privacy-aware formatting,
performance monitoring, and compliance with data protection requirements.
"""

import logging
import logging.config
import json
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import re

from .config import config


class PrivacyAwareFormatter(logging.Formatter):
    """Custom formatter that removes or masks sensitive information from logs."""
    
    # Patterns for sensitive data that should be masked
    SENSITIVE_PATTERNS = [
        (re.compile(r'\b\d{12}\b'), '****AADHAAR****'),  # Aadhaar numbers
        (re.compile(r'\b\d{10}\b'), '****PHONE****'),    # Phone numbers
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '****EMAIL****'),  # Email
        (re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b'), '****PAN****'),  # PAN numbers
        (re.compile(r'password["\s]*[:=]["\s]*[^"\s,}]+', re.IGNORECASE), 'password":"****"'),  # Passwords
        (re.compile(r'token["\s]*[:=]["\s]*[^"\s,}]+', re.IGNORECASE), 'token":"****"'),  # Tokens
    ]
    
    def format(self, record):
        """Format log record with privacy masking."""
        # Get the original formatted message
        formatted = super().format(record)
        
        # Apply privacy masking if enabled
        if config.security.anonymize_logs:
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                formatted = pattern.sub(replacement, formatted)
        
        return formatted


class StructuredFormatter(PrivacyAwareFormatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'session_id'):
            log_entry['session_id'] = record.session_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'language'):
            log_entry['language'] = record.language
        if hasattr(record, 'component'):
            log_entry['component'] = record.component
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Apply privacy masking to the JSON string
        json_str = json.dumps(log_entry, ensure_ascii=False)
        if config.security.anonymize_logs:
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                json_str = pattern.sub(replacement, json_str)
        
        return json_str


class PerformanceLogger:
    """Logger for performance monitoring and metrics."""
    
    def __init__(self, logger_name: str = "bharat_voice_assistant.performance"):
        self.logger = logging.getLogger(logger_name)
    
    def log_response_time(self, component: str, operation: str, duration_ms: float, 
                         user_id: Optional[str] = None, language: Optional[str] = None):
        """Log response time metrics."""
        self.logger.info(
            f"Performance metric: {component}.{operation} took {duration_ms:.2f}ms",
            extra={
                'component': component,
                'operation': operation,
                'duration_ms': duration_ms,
                'user_id': user_id,
                'language': language,
                'metric_type': 'response_time'
            }
        )
    
    def log_throughput(self, component: str, requests_per_second: float):
        """Log throughput metrics."""
        self.logger.info(
            f"Throughput metric: {component} processing {requests_per_second:.2f} req/s",
            extra={
                'component': component,
                'requests_per_second': requests_per_second,
                'metric_type': 'throughput'
            }
        )
    
    def log_error_rate(self, component: str, error_rate: float, total_requests: int):
        """Log error rate metrics."""
        self.logger.warning(
            f"Error rate metric: {component} has {error_rate:.2f}% error rate ({total_requests} total requests)",
            extra={
                'component': component,
                'error_rate': error_rate,
                'total_requests': total_requests,
                'metric_type': 'error_rate'
            }
        )


def setup_logging(log_level: str = "INFO", log_format: str = "structured") -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('structured' for JSON, 'simple' for text)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Ensure log files can be created
    try:
        (log_dir / "test.log").touch()
        (log_dir / "test.log").unlink()
    except Exception:
        # If we can't write to logs directory, use current directory
        log_dir = Path(".")
    
    # Choose formatter based on format type
    if log_format == "structured":
        formatter_class = StructuredFormatter
        formatter_format = None  # JSON formatter doesn't use format string
    else:
        formatter_class = PrivacyAwareFormatter
        formatter_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Logging configuration
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                '()': formatter_class,
                'format': formatter_format,
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'default',
                'stream': sys.stdout,
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': log_level,
                'formatter': 'default',
                'filename': log_dir / 'bharat_voice_assistant.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf-8',
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'default',
                'filename': log_dir / 'errors.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf-8',
            },
            'performance_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'INFO',
                'formatter': 'default',
                'filename': log_dir / 'performance.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'encoding': 'utf-8',
            },
        },
        'loggers': {
            'bharat_voice_assistant': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            'bharat_voice_assistant.performance': {
                'level': 'INFO',
                'handlers': ['performance_file'],
                'propagate': False,
            },
            # AWS SDK logging
            'boto3': {
                'level': 'WARNING',
                'handlers': ['console', 'file'],
                'propagate': False,
            },
            'botocore': {
                'level': 'WARNING',
                'handlers': ['console', 'file'],
                'propagate': False,
            },
        },
        'root': {
            'level': log_level,
            'handlers': ['console'],
        },
    }
    
    # Apply the configuration
    logging.config.dictConfig(logging_config)
    
    # Log the initialization
    logger = logging.getLogger('bharat_voice_assistant.core.logging')
    logger.info(f"Logging initialized with level {log_level} and format {log_format}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name, typically __name__ of the calling module
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def get_performance_logger() -> PerformanceLogger:
    """Get a performance logger instance."""
    return PerformanceLogger()


# Context manager for logging performance
class LogPerformance:
    """Context manager for logging operation performance."""
    
    def __init__(self, component: str, operation: str, 
                 user_id: Optional[str] = None, language: Optional[str] = None):
        self.component = component
        self.operation = operation
        self.user_id = user_id
        self.language = language
        self.performance_logger = get_performance_logger()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds() * 1000
            self.performance_logger.log_response_time(
                self.component, self.operation, duration, 
                self.user_id, self.language
            )


# Initialize logging on module import
try:
    setup_logging(
        log_level="INFO",  # Use INFO level by default
        log_format="simple"  # Use simple format by default
    )
except Exception:
    # If logging setup fails, use basic configuration
    import logging
    logging.basicConfig(level=logging.INFO)