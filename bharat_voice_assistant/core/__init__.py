"""
Core infrastructure components for the Bharat Voice Assistant.

This module contains the foundational components including configuration,
logging, monitoring, error handling frameworks, security protocols,
data validation, and offline functionality including caching, request
queuing, and offline operation management.
"""

from .config import config, Config
from .logging import get_logger, setup_logging
from .monitoring import monitor, Monitor
from .exceptions import *
from .aws_client import AWSClientManager
from .cache_manager import cache_manager, CacheManager, CacheType, CachePolicy
from .request_queue import request_queue, RequestQueue, RequestStatus, RequestPriority
from .offline_manager import offline_manager, OfflineManager, ConnectivityStatus, OfflineMode
from .offline_integration import offline_integration, OfflineIntegration, OfflineConfig
from .security import (
    SecurityProtocolManager, SecurityEventType, SecurityLevel, SecurityEvent,
    DataIntegrityCheck, security_manager
)
from .data_validation import (
    DataValidationService, DataType, ValidationSeverity, ValidationRule,
    ValidationIssue, ValidationResult
)
from .security_integration import (
    IntegratedSecurityService, SecurityOperation, SecurityContext,
    SecurityResult, integrated_security
)

__all__ = [
    # Configuration and logging
    "config", "Config",
    "get_logger", "setup_logging",
    "monitor", "Monitor",
    
    # AWS integration
    "AWSClientManager",
    
    # Security and validation
    "SecurityProtocolManager", "SecurityEventType", "SecurityLevel", "SecurityEvent",
    "DataIntegrityCheck", "security_manager",
    "DataValidationService", "DataType", "ValidationSeverity", "ValidationRule",
    "ValidationIssue", "ValidationResult",
    "IntegratedSecurityService", "SecurityOperation", "SecurityContext",
    "SecurityResult", "integrated_security",
    
    # Offline functionality
    "cache_manager", "CacheManager", "CacheType", "CachePolicy",
    "request_queue", "RequestQueue", "RequestStatus", "RequestPriority", 
    "offline_manager", "OfflineManager", "ConnectivityStatus", "OfflineMode",
    "offline_integration", "OfflineIntegration", "OfflineConfig",
]