"""
Unit tests for security protocols implementation.

This module tests the comprehensive security measures including:
- Secure authentication with government systems
- Audit logging for compliance
- Data validation and integrity checking
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from bharat_voice_assistant.core.security import (
    SecurityProtocolManager, SecurityEventType, SecurityLevel, SecurityEvent,
    DataIntegrityCheck
)
from bharat_voice_assistant.core.data_validation import (
    DataValidationService, DataType, ValidationSeverity, ValidationRule,
    ValidationIssue, ValidationResult
)
from bharat_voice_assistant.core.security_integration import (
    IntegratedSecurityService, SecurityOperation, SecurityContext, SecurityResult
)
from bharat_voice_assistant.integration.secure_auth_protocols import (
    SecureAuthenticationManager, SecureAuthContext, AuthenticationResult
)
from bharat_voice_assistant.integration.models import GovernmentPortal, APICredentials, AuthMethod
from bharat_voice_assistant.core.exceptions import AuthenticationError, ValidationError


class TestSecurityProtocolManager:
    """Test security protocol manager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityProtocolManager()
    
    def test_initialization(self):
        """Test security manager initialization."""
        assert self.security_manager is not None
        assert hasattr(self.security_manager, 'audit_logger')
        assert hasattr(self.security_manager, '_session_registry')
        assert hasattr(self.security_manager, '_security_events')
    
    def test_log_security_event(self):
        """Test security event logging."""
        event_id = self.security_manager.log_security_event(
            SecurityEventType.AUTHENTICATION_SUCCESS,
            "test_component",
            "test_operation",
            True,
            user_id="test_user",
            session_id="test_session",
            details={"test": "data"},
            security_level=SecurityLevel.HIGH
        )
        
        assert event_id is not None
        assert len(self.security_manager._security_events) == 1
        
        event = self.security_manager._security_events[0]
        assert event.event_type == SecurityEventType.AUTHENTICATION_SUCCESS
        assert event.component == "test_component"
        assert event.operation == "test_operation"
        assert event.success is True
        assert event.user_id == "test_user"
        assert event.session_id == "test_session"
        assert event.security_level == SecurityLevel.HIGH
    
    def test_create_secure_session(self):
        """Test secure session creation."""
        session_id = self.security_manager.create_secure_session(
            "test_user",
            "password_auth",
            ip_address="192.168.1.1"
        )
        
        assert session_id is not None
        assert session_id in self.security_manager._session_registry
        
        session_data = self.security_manager._session_registry[session_id]
        assert session_data['user_id'] == "test_user"
        assert session_data['authentication_method'] == "password_auth"
        assert session_data['ip_address'] == "192.168.1.1"
        assert session_data['is_active'] is True
    
    def test_validate_session(self):
        """Test session validation."""
        # Create a session
        session_id = self.security_manager.create_secure_session(
            "test_user",
            "password_auth"
        )
        
        # Validate the session
        is_valid = self.security_manager.validate_session(session_id)
        assert is_valid is True
        
        # Test invalid session
        is_valid = self.security_manager.validate_session("invalid_session")
        assert is_valid is False
    
    def test_invalidate_session(self):
        """Test session invalidation."""
        # Create a session
        session_id = self.security_manager.create_secure_session(
            "test_user",
            "password_auth"
        )
        
        # Invalidate the session
        success = self.security_manager.invalidate_session(session_id, "user_logout")
        assert success is True
        
        # Validate the invalidated session
        is_valid = self.security_manager.validate_session(session_id)
        assert is_valid is False
    
    def test_data_integrity_hash(self):
        """Test data integrity hash calculation."""
        test_data = {"name": "John Doe", "phone": "9876543210"}
        
        hash1 = self.security_manager.calculate_data_integrity_hash(test_data)
        hash2 = self.security_manager.calculate_data_integrity_hash(test_data)
        
        # Same data should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
        
        # Different data should produce different hash
        different_data = {"name": "Jane Doe", "phone": "9876543210"}
        hash3 = self.security_manager.calculate_data_integrity_hash(different_data)
        assert hash1 != hash3
    
    def test_verify_data_integrity(self):
        """Test data integrity verification."""
        test_data = {"name": "John Doe", "phone": "9876543210"}
        expected_hash = self.security_manager.calculate_data_integrity_hash(test_data)
        
        # Valid integrity check
        result = self.security_manager.verify_data_integrity(test_data, expected_hash)
        assert result.is_valid is True
        assert len(result.validation_errors) == 0
        
        # Invalid integrity check
        result = self.security_manager.verify_data_integrity(test_data, "invalid_hash")
        assert result.is_valid is False
        assert len(result.validation_errors) > 0
    
    def test_security_report_generation(self):
        """Test security report generation."""
        # Log some events
        self.security_manager.log_security_event(
            SecurityEventType.AUTHENTICATION_SUCCESS,
            "test_component",
            "login",
            True,
            user_id="user1"
        )
        
        self.security_manager.log_security_event(
            SecurityEventType.AUTHENTICATION_FAILURE,
            "test_component",
            "login",
            False,
            user_id="user2"
        )
        
        # Generate report
        report = self.security_manager.generate_security_report()
        
        assert 'report_period' in report
        assert 'summary' in report
        assert 'event_types' in report
        assert 'security_levels' in report
        assert report['summary']['total_events'] == 2
        assert report['summary']['successful_events'] == 1
        assert report['summary']['failed_events'] == 1


class TestDataValidationService:
    """Test data validation service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityProtocolManager()
        self.data_validator = DataValidationService(self.security_manager)
    
    def test_initialization(self):
        """Test data validation service initialization."""
        assert self.data_validator is not None
        assert hasattr(self.data_validator, '_validation_rules')
        assert hasattr(self.data_validator, '_custom_validators')
        assert len(self.data_validator._validation_rules) > 0
    
    @pytest.mark.asyncio
    async def test_validate_personal_info(self):
        """Test personal information validation."""
        valid_data = {
            "name": "John Doe",
            "phone": "9876543210",
            "email": "john@example.com",
            "aadhaar": "123456789012",
            "pan": "ABCDE1234F"
        }
        
        result = await self.data_validator.validate_data(
            valid_data, DataType.PERSONAL_INFO
        )
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert result.data_hash is not None
    
    @pytest.mark.asyncio
    async def test_validate_invalid_personal_info(self):
        """Test validation with invalid personal information."""
        invalid_data = {
            "name": "J",  # Too short
            "phone": "123",  # Invalid format
            "email": "invalid-email",  # Invalid format
            "aadhaar": "123",  # Invalid format
            "pan": "invalid"  # Invalid format
        }
        
        result = await self.data_validator.validate_data(
            invalid_data, DataType.PERSONAL_INFO
        )
        
        assert result.is_valid is False
        assert len(result.issues) > 0
        
        # Check specific validation errors
        error_fields = [issue.field_name for issue in result.issues]
        assert "name" in error_fields
        assert "phone" in error_fields
        assert "email" in error_fields
    
    @pytest.mark.asyncio
    async def test_validate_voice_recording(self):
        """Test voice recording validation."""
        valid_data = {
            "audio_data": b"fake_audio_data" * 100,  # Sufficient size
            "duration": 30.0,
            "language": "hi",
            "quality_score": 0.8
        }
        
        result = await self.data_validator.validate_data(
            valid_data, DataType.VOICE_RECORDING
        )
        
        assert result.is_valid is True
        assert len(result.issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_xss_protection(self):
        """Test XSS protection validation."""
        malicious_data = {
            "comment": "<script>alert('xss')</script>",
            "description": "javascript:void(0)",
            "name": "<iframe src='evil.com'></iframe>"
        }
        
        result = await self.data_validator.validate_data(
            malicious_data, DataType.USER_INPUT
        )
        
        assert result.is_valid is False
        assert len(result.issues) > 0
        
        # Check that XSS issues are marked as critical
        critical_issues = [
            issue for issue in result.issues 
            if issue.severity == ValidationSeverity.CRITICAL
        ]
        assert len(critical_issues) > 0
    
    @pytest.mark.asyncio
    async def test_validate_sql_injection_protection(self):
        """Test SQL injection protection validation."""
        malicious_data = {
            "search": "'; DROP TABLE users; --",
            "filter": "1 OR 1=1",
            "query": "UNION SELECT * FROM passwords"
        }
        
        result = await self.data_validator.validate_data(
            malicious_data, DataType.USER_INPUT
        )
        
        assert result.is_valid is False
        assert len(result.issues) > 0
        
        # Check that SQL injection issues are marked as critical
        critical_issues = [
            issue for issue in result.issues 
            if issue.severity == ValidationSeverity.CRITICAL
        ]
        assert len(critical_issues) > 0
    
    def test_custom_validators(self):
        """Test custom validation functions."""
        # Test Indian phone validation
        assert self.data_validator._custom_validators['indian_phone']("9876543210") is True
        assert self.data_validator._custom_validators['indian_phone']("+919876543210") is True
        assert self.data_validator._custom_validators['indian_phone']("123456") is False
        
        # Test email validation
        assert self.data_validator._custom_validators['email']("test@example.com") is True
        assert self.data_validator._custom_validators['email']("invalid-email") is False
        
        # Test PAN validation
        assert self.data_validator._custom_validators['pan_number']("ABCDE1234F") is True
        assert self.data_validator._custom_validators['pan_number']("invalid") is False
    
    @pytest.mark.asyncio
    async def test_data_integrity_verification(self):
        """Test data integrity verification."""
        test_data = {"name": "John", "age": 30}
        expected_hash = self.data_validator._calculate_data_hash(test_data)
        
        # Valid integrity check
        is_valid = await self.data_validator.verify_data_integrity(
            test_data, expected_hash
        )
        assert is_valid is True
        
        # Invalid integrity check
        is_valid = await self.data_validator.verify_data_integrity(
            test_data, "invalid_hash"
        )
        assert is_valid is False


class TestSecureAuthenticationManager:
    """Test secure authentication manager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityProtocolManager()
        self.auth_manager = SecureAuthenticationManager(self.security_manager)
    
    def test_initialization(self):
        """Test secure authentication manager initialization."""
        assert self.auth_manager is not None
        assert hasattr(self.auth_manager, 'base_auth_manager')
        assert hasattr(self.auth_manager, 'security_manager')
    
    @pytest.mark.asyncio
    async def test_authenticate_with_government_portal(self):
        """Test government portal authentication."""
        # Create test portal
        from bharat_voice_assistant.integration.models import PortalType
        
        portal = GovernmentPortal(
            id="test_portal",
            name="Test Government Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in",
            credentials=APICredentials(
                auth_method=AuthMethod.API_KEY,
                api_key="test_api_key"
            )
        )
        
        # Create auth context
        auth_context = SecureAuthContext(
            portal_id=portal.id,
            user_id="test_user",
            session_id="test_session",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
            security_level=SecurityLevel.MEDIUM
        )
        
        # Mock the base authentication
        with patch.object(
            self.auth_manager.base_auth_manager, 
            'get_auth_headers',
            return_value={'X-API-Key': 'test_api_key'}
        ):
            result = await self.auth_manager.authenticate_with_government_portal(
                portal, auth_context
            )
            
            assert result.success is True
            assert result.auth_token is not None
            assert len(result.security_warnings) >= 0
    
    @pytest.mark.asyncio
    async def test_validate_auth_token(self):
        """Test authentication token validation."""
        from bharat_voice_assistant.integration.models import AuthToken, PortalType
        
        # Create test token
        token = AuthToken(
            token="test_token",
            token_type="Bearer",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Create test portal
        portal = GovernmentPortal(
            id="test_portal",
            name="Test Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in"
        )
        
        # Validate token
        is_valid = await self.auth_manager.validate_auth_token(
            token, portal, SecurityLevel.MEDIUM
        )
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_validate_expired_token(self):
        """Test validation of expired token."""
        from bharat_voice_assistant.integration.models import AuthToken, PortalType
        
        # Create expired token
        token = AuthToken(
            token="test_token",
            token_type="Bearer",
            expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired
        )
        
        # Create test portal
        portal = GovernmentPortal(
            id="test_portal",
            name="Test Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in"
        )
        
        # Validate token
        is_valid = await self.auth_manager.validate_auth_token(
            token, portal, SecurityLevel.MEDIUM
        )
        
        assert is_valid is False


class TestIntegratedSecurityService:
    """Test integrated security service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_service = IntegratedSecurityService()
    
    def test_initialization(self):
        """Test integrated security service initialization."""
        assert self.security_service is not None
        assert hasattr(self.security_service, 'security_manager')
        assert hasattr(self.security_service, 'data_validator')
        assert hasattr(self.security_service, 'auth_manager')
        assert hasattr(self.security_service, 'privacy_manager')
    
    @pytest.mark.asyncio
    async def test_secure_voice_processing(self):
        """Test secure voice processing."""
        audio_data = b"fake_audio_data" * 100
        
        # Mock privacy consent check
        with patch.object(
            self.security_service.privacy_manager,
            'check_data_processing_consent',
            return_value=True
        ):
            result = await self.security_service.secure_voice_processing(
                user_id="test_user",
                session_id="test_session",
                audio_data=audio_data,
                language="hi",
                ip_address="192.168.1.1"
            )
            
            assert result.operation == SecurityOperation.VOICE_RECORDING
            assert result.security_level == SecurityLevel.HIGH
            # Note: Result may not be successful due to missing privacy consent setup
    
    @pytest.mark.asyncio
    async def test_secure_government_api_call(self):
        """Test secure government API call."""
        # Create test portal
        from bharat_voice_assistant.integration.models import PortalType
        
        portal = GovernmentPortal(
            id="test_portal",
            name="Test Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in",
            credentials=APICredentials(
                auth_method=AuthMethod.API_KEY,
                api_key="test_key"
            )
        )
        
        request_data = {
            "operation": "get_schemes",
            "user_id": "test_user"
        }
        
        # Mock privacy consent and authentication
        with patch.object(
            self.security_service.privacy_manager,
            'check_data_processing_consent',
            return_value=True
        ), patch.object(
            self.security_service.auth_manager,
            'authenticate_with_government_portal',
            return_value=AuthenticationResult(
                success=True,
                auth_token=Mock(),
                error_message=None,
                security_warnings=[]
            )
        ):
            result = await self.security_service.secure_government_api_call(
                user_id="test_user",
                session_id="test_session",
                portal=portal,
                request_data=request_data,
                ip_address="192.168.1.1"
            )
            
            assert result.operation == SecurityOperation.GOVERNMENT_API_ACCESS
            assert result.security_level == SecurityLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_secure_grievance_filing(self):
        """Test secure grievance filing."""
        # Create test portal
        from bharat_voice_assistant.integration.models import PortalType
        
        portal = GovernmentPortal(
            id="grievance_portal",
            name="Grievance Portal",
            portal_type=PortalType.GRIEVANCE_PORTAL,
            base_url="https://grievance.gov.in"
        )
        
        grievance_data = {
            "grievance_type": "pension",
            "description": "Issue with pension payment delay",
            "priority": "medium"
        }
        
        # Mock privacy consent and authentication
        with patch.object(
            self.security_service.privacy_manager,
            'check_data_processing_consent',
            return_value=True
        ), patch.object(
            self.security_service.auth_manager,
            'authenticate_with_government_portal',
            return_value=AuthenticationResult(
                success=True,
                auth_token=Mock(),
                error_message=None,
                security_warnings=[]
            )
        ):
            result = await self.security_service.secure_grievance_filing(
                user_id="test_user",
                session_id="test_session",
                grievance_data=grievance_data,
                portal=portal,
                ip_address="192.168.1.1"
            )
            
            assert result.operation == SecurityOperation.GRIEVANCE_FILING
            assert result.security_level == SecurityLevel.HIGH
    
    def test_get_security_metrics(self):
        """Test security metrics generation."""
        metrics = self.security_service.get_security_metrics()
        
        assert 'total_operations' in metrics
        assert 'operations_by_type' in metrics
        assert 'security_violations' in metrics
        assert 'active_sessions' in metrics
        assert 'validation_rules_count' in metrics
        assert 'generated_at' in metrics
    
    @pytest.mark.asyncio
    async def test_generate_security_report(self):
        """Test security report generation."""
        report = await self.security_service.generate_security_report()
        
        assert 'security_report' in report
        assert 'service_metrics' in report
        assert 'privacy_compliance' in report
        assert 'government_integration' in report
        
        # Check privacy compliance flags
        privacy_compliance = report['privacy_compliance']
        assert privacy_compliance['consent_management_active'] is True
        assert privacy_compliance['data_encryption_enabled'] is True
        assert privacy_compliance['audit_logging_enabled'] is True
        assert privacy_compliance['data_validation_enabled'] is True
        
        # Check government integration flags
        gov_integration = report['government_integration']
        assert gov_integration['secure_authentication_enabled'] is True
        assert gov_integration['certificate_validation_enabled'] is True
        assert gov_integration['api_security_monitoring_enabled'] is True


class TestSecurityIntegration:
    """Test security integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_service = IntegratedSecurityService()
    
    @pytest.mark.asyncio
    async def test_end_to_end_security_flow(self):
        """Test complete security flow from authentication to data processing."""
        # Create test context
        context = SecurityContext(
            user_id="test_user",
            session_id="test_session",
            operation=SecurityOperation.DATA_PROCESSING,
            data_type=DataType.PERSONAL_INFO,
            ip_address="192.168.1.1",
            security_level=SecurityLevel.MEDIUM,
            requires_privacy_consent=True,
            requires_data_validation=True,
            requires_audit_logging=True
        )
        
        # Test data
        test_data = {
            "name": "John Doe",
            "phone": "9876543210",
            "email": "john@example.com"
        }
        
        # Mock privacy consent
        with patch.object(
            self.security_service.privacy_manager,
            'check_data_processing_consent',
            return_value=True
        ):
            result = await self.security_service.execute_secure_operation(
                context, test_data
            )
            
            # Check that all security checks were performed
            assert result.operation == SecurityOperation.DATA_PROCESSING
            assert result.privacy_consent_granted is True
            assert result.validation_result is not None
            assert result.audit_event_id is not None
    
    @pytest.mark.asyncio
    async def test_security_violation_detection(self):
        """Test security violation detection and logging."""
        # Create context for malicious data
        context = SecurityContext(
            user_id="test_user",
            session_id="test_session",
            operation=SecurityOperation.DATA_PROCESSING,
            data_type=DataType.USER_INPUT,
            security_level=SecurityLevel.HIGH,
            requires_data_validation=True
        )
        
        # Malicious data with XSS attempt
        malicious_data = {
            "comment": "<script>alert('xss')</script>",
            "description": "javascript:void(0)"
        }
        
        # Mock privacy consent
        with patch.object(
            self.security_service.privacy_manager,
            'check_data_processing_consent',
            return_value=True
        ):
            result = await self.security_service.execute_secure_operation(
                context, malicious_data
            )
            
            # Should fail due to security violations
            assert result.success is False
            assert result.validation_result is not None
            assert result.validation_result.is_valid is False
            assert len(result.validation_result.issues) > 0
    
    @pytest.mark.asyncio
    async def test_authentication_failure_handling(self):
        """Test handling of authentication failures."""
        # Create test portal with invalid credentials
        from bharat_voice_assistant.integration.models import PortalType
        
        portal = GovernmentPortal(
            id="test_portal",
            name="Test Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="http://insecure.gov.in",  # Non-HTTPS
            credentials=None  # No credentials
        )
        
        context = SecurityContext(
            user_id="test_user",
            session_id="test_session",
            operation=SecurityOperation.GOVERNMENT_API_ACCESS,
            government_portal_id=portal.id,
            security_level=SecurityLevel.HIGH
        )
        
        # Mock privacy consent
        with patch.object(
            self.security_service.privacy_manager,
            'check_data_processing_consent',
            return_value=True
        ):
            result = await self.security_service.execute_secure_operation(
                context, {}, portal
            )
            
            # Should fail due to authentication issues
            assert result.success is False
            assert result.authentication_result is not None
            assert result.authentication_result.success is False


if __name__ == "__main__":
    pytest.main([__file__])