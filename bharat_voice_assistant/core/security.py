"""
Security protocols for the Bharat Voice Assistant.

This module implements comprehensive security measures including:
- Secure authentication with government systems
- Audit logging for compliance
- Data validation and integrity checking
- Security monitoring and threat detection
"""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .logging import get_logger
from .exceptions import (
    AuthenticationError, ValidationError, PrivacyError,
    BharatVoiceAssistantError
)
from .config import config

logger = get_logger(__name__)


class SecurityEventType(Enum):
    """Types of security events for audit logging."""
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_SUCCESS = "authorization_success"
    AUTHORIZATION_FAILURE = "authorization_failure"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    PRIVACY_CONSENT_GRANTED = "privacy_consent_granted"
    PRIVACY_CONSENT_WITHDRAWN = "privacy_consent_withdrawn"
    GOVERNMENT_API_ACCESS = "government_api_access"
    SECURITY_VIOLATION = "security_violation"
    SYSTEM_CONFIGURATION_CHANGE = "system_configuration_change"
    USER_SESSION_START = "user_session_start"
    USER_SESSION_END = "user_session_end"
    VOICE_DATA_PROCESSED = "voice_data_processed"
    GRIEVANCE_FILED = "grievance_filed"
    SCHEME_ACCESSED = "scheme_accessed"


class SecurityLevel(Enum):
    """Security levels for different operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Security event for audit logging."""
    event_id: str
    event_type: SecurityEventType
    timestamp: datetime
    user_id: Optional[str]
    session_id: Optional[str]
    component: str
    operation: str
    security_level: SecurityLevel
    success: bool
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    government_portal_id: Optional[str] = None
    data_classification: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert security event to dictionary for logging."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'session_id': self.session_id,
            'component': self.component,
            'operation': self.operation,
            'security_level': self.security_level.value,
            'success': self.success,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'government_portal_id': self.government_portal_id,
            'data_classification': self.data_classification
        }


@dataclass
class DataIntegrityCheck:
    """Data integrity check result."""
    is_valid: bool
    checksum: str
    timestamp: datetime
    validation_errors: List[str]
    data_size: int
    data_type: str


class SecurityProtocolManager:
    """
    Main security protocol manager for the Bharat Voice Assistant.
    
    This class provides comprehensive security measures including:
    - Secure authentication with government systems
    - Audit logging for compliance
    - Data validation and integrity checking
    """
    
    def __init__(self):
        """Initialize the security protocol manager."""
        self.audit_logger = get_logger("bharat_voice_assistant.security.audit")
        self.security_logger = get_logger("bharat_voice_assistant.security")
        self._session_registry: Dict[str, Dict[str, Any]] = {}
        self._failed_auth_attempts: Dict[str, List[datetime]] = {}
        self._security_events: List[SecurityEvent] = []
        
        # Initialize encryption key for data integrity
        self._integrity_key = self._generate_integrity_key()
        
        logger.info("Security protocol manager initialized")
    
    def _generate_integrity_key(self) -> bytes:
        """Generate key for data integrity checking."""
        # In production, this should be loaded from secure key management
        password = b"bharat_voice_assistant_integrity_key"
        salt = b"security_salt_2024"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(password)
    
    # Audit Logging Methods
    
    def log_security_event(self, event_type: SecurityEventType, component: str,
                          operation: str, success: bool, 
                          user_id: Optional[str] = None,
                          session_id: Optional[str] = None,
                          details: Optional[Dict[str, Any]] = None,
                          security_level: SecurityLevel = SecurityLevel.MEDIUM,
                          ip_address: Optional[str] = None,
                          user_agent: Optional[str] = None,
                          government_portal_id: Optional[str] = None,
                          data_classification: Optional[str] = None) -> str:
        """
        Log a security event for audit compliance.
        
        Args:
            event_type: Type of security event
            component: Component where event occurred
            operation: Operation being performed
            success: Whether the operation was successful
            user_id: User identifier (if applicable)
            session_id: Session identifier (if applicable)
            details: Additional event details
            security_level: Security level of the operation
            ip_address: Client IP address
            user_agent: Client user agent
            government_portal_id: Government portal ID (if applicable)
            data_classification: Data classification level
            
        Returns:
            Event ID for tracking
        """
        event_id = str(uuid.uuid4())
        
        event = SecurityEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            component=component,
            operation=operation,
            security_level=security_level,
            success=success,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            government_portal_id=government_portal_id,
            data_classification=data_classification
        )
        
        # Store event for analysis
        self._security_events.append(event)
        
        # Log to audit logger
        self.audit_logger.info(
            f"Security Event: {event_type.value} - {component}.{operation}",
            extra={
                'security_event': event.to_dict(),
                'event_id': event_id,
                'event_type': event_type.value,
                'component': component,
                'operation': operation,
                'success': success,
                'security_level': security_level.value,
                'user_id': user_id,
                'session_id': session_id,
                'government_portal_id': government_portal_id
            }
        )
        
        # Check for security violations
        self._analyze_security_event(event)
        
        return event_id
    
    def _analyze_security_event(self, event: SecurityEvent) -> None:
        """Analyze security event for potential threats."""
        # Check for repeated authentication failures
        if (event.event_type == SecurityEventType.AUTHENTICATION_FAILURE and 
            event.user_id):
            
            if event.user_id not in self._failed_auth_attempts:
                self._failed_auth_attempts[event.user_id] = []
            
            self._failed_auth_attempts[event.user_id].append(event.timestamp)
            
            # Check for brute force attempts (5 failures in 15 minutes)
            recent_failures = [
                ts for ts in self._failed_auth_attempts[event.user_id]
                if (event.timestamp - ts).total_seconds() < 900  # 15 minutes
            ]
            
            if len(recent_failures) >= 5:
                self.log_security_event(
                    SecurityEventType.SECURITY_VIOLATION,
                    "security_monitor",
                    "brute_force_detection",
                    True,
                    user_id=event.user_id,
                    details={
                        'violation_type': 'brute_force_attempt',
                        'failure_count': len(recent_failures),
                        'time_window_minutes': 15
                    },
                    security_level=SecurityLevel.HIGH
                )
    
    # Secure Authentication Methods
    
    def create_secure_session(self, user_id: str, authentication_method: str,
                            government_portal_id: Optional[str] = None,
                            ip_address: Optional[str] = None,
                            user_agent: Optional[str] = None) -> str:
        """
        Create a secure session for authenticated user.
        
        Args:
            user_id: User identifier
            authentication_method: Method used for authentication
            government_portal_id: Government portal ID (if applicable)
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        session_data = {
            'user_id': user_id,
            'created_at': datetime.utcnow(),
            'last_activity': datetime.utcnow(),
            'authentication_method': authentication_method,
            'government_portal_id': government_portal_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'is_active': True
        }
        
        self._session_registry[session_id] = session_data
        
        # Log session creation
        self.log_security_event(
            SecurityEventType.USER_SESSION_START,
            "session_manager",
            "create_session",
            True,
            user_id=user_id,
            session_id=session_id,
            details={
                'authentication_method': authentication_method,
                'government_portal_id': government_portal_id
            },
            security_level=SecurityLevel.MEDIUM,
            ip_address=ip_address,
            user_agent=user_agent,
            government_portal_id=government_portal_id
        )
        
        return session_id
    
    def validate_session(self, session_id: str, 
                        required_security_level: SecurityLevel = SecurityLevel.MEDIUM) -> bool:
        """
        Validate a user session.
        
        Args:
            session_id: Session identifier
            required_security_level: Required security level for operation
            
        Returns:
            True if session is valid
        """
        if session_id not in self._session_registry:
            return False
        
        session_data = self._session_registry[session_id]
        
        # Check if session is active
        if not session_data.get('is_active', False):
            return False
        
        # Check session timeout (30 minutes)
        last_activity = session_data.get('last_activity')
        if last_activity and (datetime.utcnow() - last_activity).total_seconds() > 1800:
            self.invalidate_session(session_id, "session_timeout")
            return False
        
        # Update last activity
        session_data['last_activity'] = datetime.utcnow()
        
        return True
    
    def invalidate_session(self, session_id: str, reason: str = "user_logout") -> bool:
        """
        Invalidate a user session.
        
        Args:
            session_id: Session identifier
            reason: Reason for invalidation
            
        Returns:
            True if session was invalidated
        """
        if session_id not in self._session_registry:
            return False
        
        session_data = self._session_registry[session_id]
        session_data['is_active'] = False
        session_data['invalidated_at'] = datetime.utcnow()
        session_data['invalidation_reason'] = reason
        
        # Log session end
        self.log_security_event(
            SecurityEventType.USER_SESSION_END,
            "session_manager",
            "invalidate_session",
            True,
            user_id=session_data.get('user_id'),
            session_id=session_id,
            details={'reason': reason},
            security_level=SecurityLevel.MEDIUM
        )
        
        return True
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information."""
        return self._session_registry.get(session_id)
    
    # Data Validation and Integrity Methods
    
    def validate_user_input(self, data: Dict[str, Any], 
                           validation_rules: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate user input data against security rules.
        
        Args:
            data: Input data to validate
            validation_rules: Validation rules to apply
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Check required fields
            required_fields = validation_rules.get('required_fields', [])
            for field in required_fields:
                if field not in data or not data[field]:
                    errors.append(f"Required field '{field}' is missing or empty")
            
            # Check field types
            field_types = validation_rules.get('field_types', {})
            for field, expected_type in field_types.items():
                if field in data:
                    if expected_type == 'string' and not isinstance(data[field], str):
                        errors.append(f"Field '{field}' must be a string")
                    elif expected_type == 'integer' and not isinstance(data[field], int):
                        errors.append(f"Field '{field}' must be an integer")
                    elif expected_type == 'email' and not self._is_valid_email(data[field]):
                        errors.append(f"Field '{field}' must be a valid email address")
                    elif expected_type == 'phone' and not self._is_valid_phone(data[field]):
                        errors.append(f"Field '{field}' must be a valid phone number")
            
            # Check field lengths
            field_lengths = validation_rules.get('field_lengths', {})
            for field, length_rules in field_lengths.items():
                if field in data and isinstance(data[field], str):
                    value_length = len(data[field])
                    if 'min' in length_rules and value_length < length_rules['min']:
                        errors.append(f"Field '{field}' must be at least {length_rules['min']} characters")
                    if 'max' in length_rules and value_length > length_rules['max']:
                        errors.append(f"Field '{field}' must be at most {length_rules['max']} characters")
            
            # Check for SQL injection patterns
            sql_injection_patterns = [
                r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
                r"(--|#|/\*|\*/)",
                r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
                r"(\'\s*(OR|AND)\s*\'\w*\'\s*=\s*\'\w*\')"
            ]
            
            for field, value in data.items():
                if isinstance(value, str):
                    for pattern in sql_injection_patterns:
                        import re
                        if re.search(pattern, value, re.IGNORECASE):
                            errors.append(f"Field '{field}' contains potentially malicious content")
                            break
            
            # Check for XSS patterns
            xss_patterns = [
                r"<script[^>]*>.*?</script>",
                r"javascript:",
                r"on\w+\s*=",
                r"<iframe[^>]*>.*?</iframe>"
            ]
            
            for field, value in data.items():
                if isinstance(value, str):
                    for pattern in xss_patterns:
                        import re
                        if re.search(pattern, value, re.IGNORECASE):
                            errors.append(f"Field '{field}' contains potentially malicious script content")
                            break
            
            is_valid = len(errors) == 0
            
            # Log validation result
            self.log_security_event(
                SecurityEventType.DATA_ACCESS if is_valid else SecurityEventType.SECURITY_VIOLATION,
                "data_validator",
                "validate_user_input",
                is_valid,
                details={
                    'validation_rules': validation_rules,
                    'error_count': len(errors),
                    'field_count': len(data)
                },
                security_level=SecurityLevel.HIGH if not is_valid else SecurityLevel.MEDIUM
            )
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Error during data validation: {e}")
            return False, [f"Validation error: {str(e)}"]
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Validate Indian phone number format."""
        import re
        # Indian phone number patterns
        patterns = [
            r'^\+91[6-9]\d{9}$',  # +91 followed by 10 digits starting with 6-9
            r'^[6-9]\d{9}$',      # 10 digits starting with 6-9
            r'^0[6-9]\d{9}$'      # 0 followed by 10 digits starting with 6-9
        ]
        return any(re.match(pattern, phone) for pattern in patterns)
    
    def calculate_data_integrity_hash(self, data: Union[str, bytes, Dict[str, Any]]) -> str:
        """
        Calculate integrity hash for data.
        
        Args:
            data: Data to hash
            
        Returns:
            Hex-encoded hash
        """
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
            data_bytes = data_str.encode('utf-8')
        elif isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = data
        
        # Use HMAC for integrity checking
        return hmac.new(
            self._integrity_key,
            data_bytes,
            hashlib.sha256
        ).hexdigest()
    
    def verify_data_integrity(self, data: Union[str, bytes, Dict[str, Any]], 
                            expected_hash: str) -> DataIntegrityCheck:
        """
        Verify data integrity using hash comparison.
        
        Args:
            data: Data to verify
            expected_hash: Expected hash value
            
        Returns:
            DataIntegrityCheck result
        """
        try:
            calculated_hash = self.calculate_data_integrity_hash(data)
            is_valid = calculated_hash == expected_hash
            
            if isinstance(data, dict):
                data_size = len(json.dumps(data))
                data_type = "json"
            elif isinstance(data, str):
                data_size = len(data.encode('utf-8'))
                data_type = "string"
            else:
                data_size = len(data)
                data_type = "bytes"
            
            result = DataIntegrityCheck(
                is_valid=is_valid,
                checksum=calculated_hash,
                timestamp=datetime.utcnow(),
                validation_errors=[] if is_valid else ["Hash mismatch detected"],
                data_size=data_size,
                data_type=data_type
            )
            
            # Log integrity check
            self.log_security_event(
                SecurityEventType.DATA_ACCESS if is_valid else SecurityEventType.SECURITY_VIOLATION,
                "integrity_checker",
                "verify_data_integrity",
                is_valid,
                details={
                    'data_type': data_type,
                    'data_size': data_size,
                    'expected_hash': expected_hash[:16] + "...",  # Truncate for logging
                    'calculated_hash': calculated_hash[:16] + "..."
                },
                security_level=SecurityLevel.HIGH if not is_valid else SecurityLevel.MEDIUM,
                data_classification="integrity_check"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error during integrity verification: {e}")
            return DataIntegrityCheck(
                is_valid=False,
                checksum="",
                timestamp=datetime.utcnow(),
                validation_errors=[f"Integrity check error: {str(e)}"],
                data_size=0,
                data_type="unknown"
            )
    
    # Government System Security Methods
    
    def log_government_api_access(self, portal_id: str, operation: str, 
                                 success: bool, user_id: Optional[str] = None,
                                 session_id: Optional[str] = None,
                                 request_data: Optional[Dict[str, Any]] = None,
                                 response_status: Optional[int] = None) -> str:
        """
        Log government API access for compliance.
        
        Args:
            portal_id: Government portal identifier
            operation: API operation performed
            success: Whether the operation was successful
            user_id: User identifier
            session_id: Session identifier
            request_data: Request data (will be sanitized)
            response_status: HTTP response status
            
        Returns:
            Event ID
        """
        # Sanitize request data for logging
        sanitized_request = {}
        if request_data:
            for key, value in request_data.items():
                if key.lower() in ['password', 'token', 'secret', 'key']:
                    sanitized_request[key] = "****REDACTED****"
                else:
                    sanitized_request[key] = str(value)[:100]  # Truncate long values
        
        return self.log_security_event(
            SecurityEventType.GOVERNMENT_API_ACCESS,
            "government_integration",
            operation,
            success,
            user_id=user_id,
            session_id=session_id,
            details={
                'portal_id': portal_id,
                'request_data': sanitized_request,
                'response_status': response_status
            },
            security_level=SecurityLevel.HIGH,
            government_portal_id=portal_id,
            data_classification="government_api"
        )
    
    def validate_government_response(self, response_data: Dict[str, Any],
                                   portal_id: str) -> Tuple[bool, List[str]]:
        """
        Validate government API response for security.
        
        Args:
            response_data: Response data from government API
            portal_id: Government portal identifier
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Check for required response fields
            if 'status' not in response_data:
                errors.append("Response missing required 'status' field")
            
            # Check for suspicious content
            response_str = json.dumps(response_data)
            
            # Check for potential script injection in response
            suspicious_patterns = [
                r"<script[^>]*>.*?</script>",
                r"javascript:",
                r"eval\s*\(",
                r"document\.",
                r"window\."
            ]
            
            for pattern in suspicious_patterns:
                import re
                if re.search(pattern, response_str, re.IGNORECASE):
                    errors.append("Response contains potentially malicious script content")
                    break
            
            # Validate data types for known fields
            if 'status' in response_data and not isinstance(response_data['status'], (str, int)):
                errors.append("Invalid data type for 'status' field")
            
            is_valid = len(errors) == 0
            
            # Log validation result
            self.log_security_event(
                SecurityEventType.DATA_ACCESS if is_valid else SecurityEventType.SECURITY_VIOLATION,
                "government_response_validator",
                "validate_response",
                is_valid,
                details={
                    'portal_id': portal_id,
                    'error_count': len(errors),
                    'response_size': len(response_str)
                },
                security_level=SecurityLevel.HIGH if not is_valid else SecurityLevel.MEDIUM,
                government_portal_id=portal_id
            )
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Error during government response validation: {e}")
            return False, [f"Response validation error: {str(e)}"]
    
    # Security Monitoring and Reporting Methods
    
    def get_security_events(self, start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None,
                           event_types: Optional[List[SecurityEventType]] = None,
                           user_id: Optional[str] = None,
                           component: Optional[str] = None) -> List[SecurityEvent]:
        """
        Get security events based on filters.
        
        Args:
            start_time: Start time filter
            end_time: End time filter
            event_types: Event types to include
            user_id: User ID filter
            component: Component filter
            
        Returns:
            List of matching security events
        """
        filtered_events = []
        
        for event in self._security_events:
            # Apply time filters
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            
            # Apply event type filter
            if event_types and event.event_type not in event_types:
                continue
            
            # Apply user ID filter
            if user_id and event.user_id != user_id:
                continue
            
            # Apply component filter
            if component and event.component != component:
                continue
            
            filtered_events.append(event)
        
        return filtered_events
    
    def generate_security_report(self, start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate comprehensive security report.
        
        Args:
            start_time: Report start time
            end_time: Report end time
            
        Returns:
            Security report dictionary
        """
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=7)  # Last 7 days
        if not end_time:
            end_time = datetime.utcnow()
        
        events = self.get_security_events(start_time, end_time)
        
        # Calculate statistics
        total_events = len(events)
        successful_events = len([e for e in events if e.success])
        failed_events = total_events - successful_events
        
        # Group by event type
        event_type_counts = {}
        for event in events:
            event_type = event.event_type.value
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        # Group by security level
        security_level_counts = {}
        for event in events:
            level = event.security_level.value
            security_level_counts[level] = security_level_counts.get(level, 0) + 1
        
        # Identify top users by activity
        user_activity = {}
        for event in events:
            if event.user_id:
                user_activity[event.user_id] = user_activity.get(event.user_id, 0) + 1
        
        top_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Identify security violations
        violations = [e for e in events if e.event_type == SecurityEventType.SECURITY_VIOLATION]
        
        report = {
            'report_period': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            },
            'summary': {
                'total_events': total_events,
                'successful_events': successful_events,
                'failed_events': failed_events,
                'success_rate': (successful_events / total_events * 100) if total_events > 0 else 0
            },
            'event_types': event_type_counts,
            'security_levels': security_level_counts,
            'top_users': dict(top_users),
            'security_violations': {
                'count': len(violations),
                'details': [v.to_dict() for v in violations[-10:]]  # Last 10 violations
            },
            'active_sessions': len([s for s in self._session_registry.values() if s.get('is_active', False)]),
            'generated_at': datetime.utcnow().isoformat()
        }
        
        return report
    
    def cleanup_old_events(self, retention_days: int = 90) -> int:
        """
        Clean up old security events.
        
        Args:
            retention_days: Number of days to retain events
            
        Returns:
            Number of events cleaned up
        """
        cutoff_time = datetime.utcnow() - timedelta(days=retention_days)
        
        old_events = [e for e in self._security_events if e.timestamp < cutoff_time]
        self._security_events = [e for e in self._security_events if e.timestamp >= cutoff_time]
        
        cleaned_count = len(old_events)
        
        if cleaned_count > 0:
            self.log_security_event(
                SecurityEventType.SYSTEM_CONFIGURATION_CHANGE,
                "security_manager",
                "cleanup_old_events",
                True,
                details={
                    'cleaned_events': cleaned_count,
                    'retention_days': retention_days
                },
                security_level=SecurityLevel.LOW
            )
        
        return cleaned_count


# Global security protocol manager instance
security_manager = SecurityProtocolManager()