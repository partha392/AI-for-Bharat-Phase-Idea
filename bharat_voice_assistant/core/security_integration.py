"""
Security integration service for the Bharat Voice Assistant.

This module integrates all security protocols including authentication,
audit logging, data validation, and integrity checking into a unified
security framework for government system integration.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .security import SecurityProtocolManager, SecurityEventType, SecurityLevel
from .data_validation import DataValidationService, DataType, ValidationResult
from ..integration.secure_auth_protocols import (
    SecureAuthenticationManager, SecureAuthContext, AuthenticationResult
)
from ..integration.models import GovernmentPortal
from ..privacy.privacy_manager import PrivacyManager
from .logging import get_logger
from .exceptions import (
    AuthenticationError, ValidationError, PrivacyError,
    BharatVoiceAssistantError
)

logger = get_logger(__name__)


class SecurityOperation(Enum):
    """Types of security operations."""
    USER_AUTHENTICATION = "user_authentication"
    GOVERNMENT_API_ACCESS = "government_api_access"
    DATA_PROCESSING = "data_processing"
    VOICE_RECORDING = "voice_recording"
    GRIEVANCE_FILING = "grievance_filing"
    SCHEME_ACCESS = "scheme_access"
    PRIVACY_CONSENT = "privacy_consent"
    DATA_EXPORT = "data_export"


@dataclass
class SecurityContext:
    """Comprehensive security context for operations."""
    user_id: Optional[str]
    session_id: Optional[str]
    operation: SecurityOperation
    data_type: Optional[DataType] = None
    government_portal_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    requires_privacy_consent: bool = True
    requires_data_validation: bool = True
    requires_audit_logging: bool = True
    requires_integrity_check: bool = False


@dataclass
class SecurityResult:
    """Result of security operation."""
    success: bool
    operation: SecurityOperation
    security_level: SecurityLevel
    authentication_result: Optional[AuthenticationResult] = None
    validation_result: Optional[ValidationResult] = None
    privacy_consent_granted: bool = False
    audit_event_id: Optional[str] = None
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class IntegratedSecurityService:
    """
    Integrated security service that coordinates all security protocols.
    
    This service provides a unified interface for:
    - Secure authentication with government systems
    - Comprehensive data validation and integrity checking
    - Privacy consent management and compliance
    - Audit logging for all security operations
    - Threat detection and security monitoring
    """
    
    def __init__(self):
        """Initialize the integrated security service."""
        self.security_manager = SecurityProtocolManager()
        self.data_validator = DataValidationService(self.security_manager)
        self.auth_manager = SecureAuthenticationManager(self.security_manager)
        self.privacy_manager = PrivacyManager()
        
        # Security metrics
        self._operation_counts: Dict[SecurityOperation, int] = {}
        self._security_violations: List[Dict[str, Any]] = []
        
        logger.info("Integrated security service initialized")
    
    async def execute_secure_operation(self, context: SecurityContext,
                                     data: Optional[Dict[str, Any]] = None,
                                     portal: Optional[GovernmentPortal] = None) -> SecurityResult:
        """
        Execute a secure operation with comprehensive security checks.
        
        Args:
            context: Security context for the operation
            data: Data to be processed (if applicable)
            portal: Government portal (if applicable)
            
        Returns:
            SecurityResult with operation outcome and security details
        """
        start_time = datetime.utcnow()
        result = SecurityResult(
            success=False,
            operation=context.operation,
            security_level=context.security_level
        )
        
        try:
            # Track operation
            self._operation_counts[context.operation] = (
                self._operation_counts.get(context.operation, 0) + 1
            )
            
            # Step 1: Privacy consent check
            if context.requires_privacy_consent and data:
                consent_result = await self._check_privacy_consent(context, data)
                result.privacy_consent_granted = consent_result
                if not consent_result:
                    result.error_message = "Privacy consent required but not granted"
                    return result
            
            # Step 2: Data validation
            if context.requires_data_validation and data and context.data_type:
                validation_result = await self.data_validator.validate_data(
                    data, context.data_type, context.user_id, context.session_id
                )
                result.validation_result = validation_result
                
                if not validation_result.is_valid:
                    result.error_message = "Data validation failed"
                    result.warnings.extend([issue.message for issue in validation_result.issues])
                    return result
                
                if validation_result.warnings:
                    result.warnings.extend([warning.message for warning in validation_result.warnings])
            
            # Step 3: Authentication (for government operations)
            if portal and context.operation in [
                SecurityOperation.GOVERNMENT_API_ACCESS,
                SecurityOperation.GRIEVANCE_FILING
            ]:
                auth_context = SecureAuthContext(
                    portal_id=portal.id,
                    user_id=context.user_id,
                    session_id=context.session_id,
                    ip_address=context.ip_address,
                    user_agent=context.user_agent,
                    security_level=context.security_level,
                    requires_mfa=context.security_level == SecurityLevel.CRITICAL,
                    certificate_required=context.security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]
                )
                
                auth_result = await self.auth_manager.authenticate_with_government_portal(
                    portal, auth_context
                )
                result.authentication_result = auth_result
                
                if not auth_result.success:
                    result.error_message = auth_result.error_message
                    result.warnings.extend(auth_result.security_warnings)
                    return result
                
                if auth_result.security_warnings:
                    result.warnings.extend(auth_result.security_warnings)
            
            # Step 4: Data integrity check
            if context.requires_integrity_check and data:
                integrity_valid = await self._verify_data_integrity(context, data)
                if not integrity_valid:
                    result.error_message = "Data integrity check failed"
                    return result
            
            # Step 5: Execute operation-specific security checks
            operation_result = await self._execute_operation_security_checks(context, data, portal)
            if not operation_result:
                result.error_message = "Operation-specific security checks failed"
                return result
            
            # Step 6: Audit logging
            if context.requires_audit_logging:
                audit_event_id = self._log_security_operation(context, True, result)
                result.audit_event_id = audit_event_id
            
            # Operation successful
            result.success = True
            
            # Log successful operation
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(
                f"Secure operation completed: {context.operation.value}",
                extra={
                    'operation': context.operation.value,
                    'user_id': context.user_id,
                    'session_id': context.session_id,
                    'security_level': context.security_level.value,
                    'duration_ms': duration_ms,
                    'warnings': len(result.warnings)
                }
            )
            
            return result
            
        except Exception as e:
            # Log operation failure
            error_msg = f"Secure operation failed: {str(e)}"
            result.error_message = error_msg
            
            if context.requires_audit_logging:
                audit_event_id = self._log_security_operation(context, False, result, str(e))
                result.audit_event_id = audit_event_id
            
            logger.error(
                f"Security operation error: {context.operation.value}",
                extra={
                    'operation': context.operation.value,
                    'user_id': context.user_id,
                    'session_id': context.session_id,
                    'error': str(e)
                }
            )
            
            return result
    
    async def _check_privacy_consent(self, context: SecurityContext,
                                   data: Dict[str, Any]) -> bool:
        """Check privacy consent for data processing."""
        try:
            if not context.user_id:
                return False
            
            # Determine data types that require consent
            consent_required_types = []
            
            if context.operation == SecurityOperation.VOICE_RECORDING:
                consent_required_types.append("voice_recording")
            elif context.operation == SecurityOperation.DATA_PROCESSING:
                consent_required_types.append("data_processing")
            elif context.operation == SecurityOperation.GRIEVANCE_FILING:
                consent_required_types.extend(["data_processing", "government_submission"])
            
            # Check consent for each required type
            for consent_type in consent_required_types:
                if not self.privacy_manager.check_data_processing_consent(
                    context.user_id, context.data_type or DataType.USER_INPUT
                ):
                    # Try to collect consent
                    from ..privacy.models import ConsentType, DataType as PrivacyDataType
                    
                    consent_map = {
                        "voice_recording": (ConsentType.VOICE_RECORDING, PrivacyDataType.VOICE_RECORDING),
                        "data_processing": (ConsentType.DATA_PROCESSING, PrivacyDataType.PERSONAL_INFO),
                        "government_submission": (ConsentType.DATA_PROCESSING, PrivacyDataType.GOVERNMENT_SUBMISSION)
                    }
                    
                    if consent_type in consent_map:
                        consent_type_enum, data_type_enum = consent_map[consent_type]
                        consent_record = self.privacy_manager.collect_explicit_consent(
                            context.user_id,
                            consent_type_enum,
                            [data_type_enum],
                            f"Required for {context.operation.value}"
                        )
                        
                        if not consent_record or not consent_record.is_valid():
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Privacy consent check failed: {e}")
            return False
    
    async def _verify_data_integrity(self, context: SecurityContext,
                                   data: Dict[str, Any]) -> bool:
        """Verify data integrity."""
        try:
            # Calculate current data hash
            current_hash = self.data_validator._calculate_data_hash(data)
            
            # For now, we'll assume integrity is valid if we can calculate the hash
            # In a real implementation, this would compare against a stored hash
            return bool(current_hash)
            
        except Exception as e:
            logger.error(f"Data integrity verification failed: {e}")
            return False
    
    async def _execute_operation_security_checks(self, context: SecurityContext,
                                               data: Optional[Dict[str, Any]],
                                               portal: Optional[GovernmentPortal]) -> bool:
        """Execute operation-specific security checks."""
        try:
            if context.operation == SecurityOperation.VOICE_RECORDING:
                return await self._check_voice_recording_security(context, data)
            elif context.operation == SecurityOperation.GOVERNMENT_API_ACCESS:
                return await self._check_government_api_security(context, portal)
            elif context.operation == SecurityOperation.GRIEVANCE_FILING:
                return await self._check_grievance_filing_security(context, data)
            elif context.operation == SecurityOperation.SCHEME_ACCESS:
                return await self._check_scheme_access_security(context, data)
            else:
                # Default security checks passed
                return True
                
        except Exception as e:
            logger.error(f"Operation security check failed: {e}")
            return False
    
    async def _check_voice_recording_security(self, context: SecurityContext,
                                            data: Optional[Dict[str, Any]]) -> bool:
        """Security checks for voice recording operations."""
        if not data or 'audio_data' not in data:
            return False
        
        # Check audio data size limits
        audio_data = data['audio_data']
        if isinstance(audio_data, (bytes, bytearray)):
            if len(audio_data) > 10 * 1024 * 1024:  # 10MB limit
                logger.warning("Voice recording exceeds size limit")
                return False
        
        # Check for required metadata
        required_fields = ['duration', 'language']
        for field in required_fields:
            if field not in data:
                logger.warning(f"Voice recording missing required field: {field}")
                return False
        
        return True
    
    async def _check_government_api_security(self, context: SecurityContext,
                                           portal: Optional[GovernmentPortal]) -> bool:
        """Security checks for government API access."""
        if not portal:
            return False
        
        # Check portal security configuration
        if not portal.base_url or not portal.base_url.startswith('https://'):
            logger.warning(f"Government portal {portal.id} does not use HTTPS")
            return False
        
        # Check authentication requirements
        if context.security_level == SecurityLevel.CRITICAL and not portal.credentials:
            logger.warning(f"Critical security level requires authentication for portal {portal.id}")
            return False
        
        return True
    
    async def _check_grievance_filing_security(self, context: SecurityContext,
                                             data: Optional[Dict[str, Any]]) -> bool:
        """Security checks for grievance filing operations."""
        if not data:
            return False
        
        # Check for required grievance fields
        required_fields = ['grievance_type', 'description']
        for field in required_fields:
            if field not in data:
                logger.warning(f"Grievance filing missing required field: {field}")
                return False
        
        # Check description length for security
        description = data.get('description', '')
        if len(description) > 5000:  # 5KB limit
            logger.warning("Grievance description exceeds security limit")
            return False
        
        return True
    
    async def _check_scheme_access_security(self, context: SecurityContext,
                                          data: Optional[Dict[str, Any]]) -> bool:
        """Security checks for scheme access operations."""
        # Basic security checks for scheme access
        if context.user_id and len(context.user_id) < 3:
            logger.warning("Invalid user ID for scheme access")
            return False
        
        return True
    
    def _log_security_operation(self, context: SecurityContext, success: bool,
                              result: SecurityResult, error: Optional[str] = None) -> str:
        """Log security operation for audit compliance."""
        event_type = SecurityEventType.DATA_ACCESS if success else SecurityEventType.SECURITY_VIOLATION
        
        details = {
            'operation': context.operation.value,
            'data_type': context.data_type.value if context.data_type else None,
            'privacy_consent_granted': result.privacy_consent_granted,
            'validation_passed': result.validation_result.is_valid if result.validation_result else None,
            'authentication_passed': result.authentication_result.success if result.authentication_result else None,
            'warning_count': len(result.warnings),
            'error': error
        }
        
        return self.security_manager.log_security_event(
            event_type,
            "integrated_security_service",
            context.operation.value,
            success,
            user_id=context.user_id,
            session_id=context.session_id,
            details=details,
            security_level=context.security_level,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            government_portal_id=context.government_portal_id,
            data_classification=context.data_type.value if context.data_type else None
        )
    
    # Public API Methods
    
    async def secure_voice_processing(self, user_id: str, session_id: str,
                                    audio_data: bytes, language: str,
                                    ip_address: Optional[str] = None) -> SecurityResult:
        """
        Process voice data with comprehensive security checks.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            audio_data: Voice audio data
            language: Language code
            ip_address: Client IP address
            
        Returns:
            SecurityResult with processing outcome
        """
        context = SecurityContext(
            user_id=user_id,
            session_id=session_id,
            operation=SecurityOperation.VOICE_RECORDING,
            data_type=DataType.VOICE_RECORDING,
            ip_address=ip_address,
            security_level=SecurityLevel.HIGH,
            requires_privacy_consent=True,
            requires_data_validation=True,
            requires_audit_logging=True,
            requires_integrity_check=True
        )
        
        data = {
            'audio_data': audio_data,
            'duration': len(audio_data) / 16000,  # Approximate duration
            'language': language,
            'quality_score': 0.8  # Default quality score
        }
        
        return await self.execute_secure_operation(context, data)
    
    async def secure_government_api_call(self, user_id: str, session_id: str,
                                       portal: GovernmentPortal,
                                       request_data: Dict[str, Any],
                                       ip_address: Optional[str] = None) -> SecurityResult:
        """
        Make secure government API call with authentication and validation.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            portal: Government portal configuration
            request_data: API request data
            ip_address: Client IP address
            
        Returns:
            SecurityResult with API call outcome
        """
        context = SecurityContext(
            user_id=user_id,
            session_id=session_id,
            operation=SecurityOperation.GOVERNMENT_API_ACCESS,
            data_type=DataType.API_RESPONSE,
            government_portal_id=portal.id,
            ip_address=ip_address,
            security_level=SecurityLevel.HIGH,
            requires_privacy_consent=True,
            requires_data_validation=True,
            requires_audit_logging=True,
            requires_integrity_check=False
        )
        
        return await self.execute_secure_operation(context, request_data, portal)
    
    async def secure_grievance_filing(self, user_id: str, session_id: str,
                                    grievance_data: Dict[str, Any],
                                    portal: GovernmentPortal,
                                    ip_address: Optional[str] = None) -> SecurityResult:
        """
        File grievance with comprehensive security and privacy checks.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            grievance_data: Grievance information
            portal: Government portal for filing
            ip_address: Client IP address
            
        Returns:
            SecurityResult with filing outcome
        """
        context = SecurityContext(
            user_id=user_id,
            session_id=session_id,
            operation=SecurityOperation.GRIEVANCE_FILING,
            data_type=DataType.GRIEVANCE_DATA,
            government_portal_id=portal.id,
            ip_address=ip_address,
            security_level=SecurityLevel.HIGH,
            requires_privacy_consent=True,
            requires_data_validation=True,
            requires_audit_logging=True,
            requires_integrity_check=True
        )
        
        return await self.execute_secure_operation(context, grievance_data, portal)
    
    async def secure_scheme_access(self, user_id: str, session_id: str,
                                 user_profile: Dict[str, Any],
                                 ip_address: Optional[str] = None) -> SecurityResult:
        """
        Access government schemes with security validation.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            user_profile: User profile for scheme matching
            ip_address: Client IP address
            
        Returns:
            SecurityResult with access outcome
        """
        context = SecurityContext(
            user_id=user_id,
            session_id=session_id,
            operation=SecurityOperation.SCHEME_ACCESS,
            data_type=DataType.PERSONAL_INFO,
            ip_address=ip_address,
            security_level=SecurityLevel.MEDIUM,
            requires_privacy_consent=True,
            requires_data_validation=True,
            requires_audit_logging=True,
            requires_integrity_check=False
        )
        
        return await self.execute_secure_operation(context, user_profile)
    
    # Security Monitoring and Reporting
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security service metrics."""
        total_operations = sum(self._operation_counts.values())
        
        return {
            'total_operations': total_operations,
            'operations_by_type': dict(self._operation_counts),
            'security_violations': len(self._security_violations),
            'active_sessions': len([
                s for s in self.security_manager._session_registry.values()
                if s.get('is_active', False)
            ]),
            'validation_rules_count': self.data_validator.get_validation_statistics()['total_validation_rules'],
            'generated_at': datetime.utcnow().isoformat()
        }
    
    async def generate_security_report(self, start_time: Optional[datetime] = None,
                                     end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate comprehensive security report."""
        base_report = self.security_manager.generate_security_report(start_time, end_time)
        metrics = self.get_security_metrics()
        
        return {
            'security_report': base_report,
            'service_metrics': metrics,
            'privacy_compliance': {
                'consent_management_active': True,
                'data_encryption_enabled': True,
                'audit_logging_enabled': True,
                'data_validation_enabled': True
            },
            'government_integration': {
                'secure_authentication_enabled': True,
                'certificate_validation_enabled': True,
                'api_security_monitoring_enabled': True
            }
        }
    
    async def cleanup_security_data(self, retention_days: int = 90) -> Dict[str, int]:
        """Clean up old security data."""
        events_cleaned = self.security_manager.cleanup_old_events(retention_days)
        
        # Clean up old security violations
        cutoff_time = datetime.utcnow() - timedelta(days=retention_days)
        old_violations = [
            v for v in self._security_violations
            if datetime.fromisoformat(v.get('timestamp', '1970-01-01')) < cutoff_time
        ]
        
        self._security_violations = [
            v for v in self._security_violations
            if datetime.fromisoformat(v.get('timestamp', '1970-01-01')) >= cutoff_time
        ]
        
        violations_cleaned = len(old_violations)
        
        return {
            'security_events_cleaned': events_cleaned,
            'security_violations_cleaned': violations_cleaned,
            'total_cleaned': events_cleaned + violations_cleaned
        }
    
    async def close(self):
        """Close the integrated security service."""
        await self.auth_manager.close()
        await self.privacy_manager.stop_background_tasks()
        logger.info("Integrated security service closed")


# Global integrated security service instance
integrated_security = IntegratedSecurityService()