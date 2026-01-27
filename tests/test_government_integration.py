"""
Unit tests for government system integration.

Tests the integration layer including API clients, authentication,
data transformation, and the main integration service.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from bharat_voice_assistant.integration.models import (
    GovernmentPortal, APICredentials, APIEndpoint, APIResponse,
    AuthMethod, DataFormat, PortalType, SubmissionStatus,
    IntegrationConfig, SubmissionRequest, AuthToken
)
from bharat_voice_assistant.integration.government_api_client import GovernmentAPIClient
from bharat_voice_assistant.integration.auth_manager import AuthenticationManager
from bharat_voice_assistant.integration.data_transformer import DataTransformer
from bharat_voice_assistant.integration.integration_service import GovernmentIntegrationService
from bharat_voice_assistant.integration.config_loader import GovernmentPortalConfigLoader
from bharat_voice_assistant.grievance.models import (
    GrievanceRecord, GrievanceDetails, ContactInformation,
    GrievanceType, GrievancePriority, GrievanceStatus
)
from bharat_voice_assistant.core.exceptions import (
    GovernmentAPIError, AuthenticationError, ValidationError
)


class TestGovernmentPortalModels:
    """Test government portal data models."""
    
    def test_api_credentials_creation(self):
        """Test APICredentials creation and validation."""
        credentials = APICredentials(
            auth_method=AuthMethod.API_KEY,
            api_key="test_key_123"
        )
        
        assert credentials.auth_method == AuthMethod.API_KEY
        assert credentials.api_key == "test_key_123"
        
        # Test to_dict method (should exclude sensitive data)
        cred_dict = credentials.to_dict()
        assert cred_dict["auth_method"] == "api_key"
        assert cred_dict["has_api_key"] is True
        assert "api_key" not in cred_dict  # Sensitive data excluded
    
    def test_api_endpoint_creation(self):
        """Test APIEndpoint creation and validation."""
        endpoint = APIEndpoint(
            name="submit_grievance",
            url="/api/v1/grievances",
            method="POST",
            data_format=DataFormat.JSON,
            required_fields=["description", "category"],
            optional_fields=["email", "phone"]
        )
        
        assert endpoint.name == "submit_grievance"
        assert endpoint.url == "/api/v1/grievances"
        assert endpoint.method == "POST"
        assert endpoint.data_format == DataFormat.JSON
        assert "description" in endpoint.required_fields
        assert "email" in endpoint.optional_fields
    
    def test_api_endpoint_invalid_url(self):
        """Test APIEndpoint with invalid URL."""
        with pytest.raises(ValueError, match="Invalid URL format"):
            APIEndpoint(
                name="test",
                url="invalid-url",
                method="POST"
            )
    
    def test_government_portal_creation(self):
        """Test GovernmentPortal creation."""
        credentials = APICredentials(
            auth_method=AuthMethod.API_KEY,
            api_key="test_key"
        )
        
        portal = GovernmentPortal(
            id="test_portal",
            name="Test Government Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in",
            credentials=credentials
        )
        
        assert portal.id == "test_portal"
        assert portal.portal_type == PortalType.CENTRAL_GOVERNMENT
        assert portal.is_active is True
        assert portal.priority == 1
    
    def test_government_portal_location_availability(self):
        """Test portal location availability checking."""
        # Central government portal (available everywhere)
        central_portal = GovernmentPortal(
            id="central",
            name="Central Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://central.gov.in"
        )
        
        assert central_portal.is_available_for_location("MH", "PUNE") is True
        assert central_portal.is_available_for_location("UP", "LUCKNOW") is True
        
        # State portal (limited to specific state)
        state_portal = GovernmentPortal(
            id="mh_portal",
            name="Maharashtra Portal",
            portal_type=PortalType.STATE_GOVERNMENT,
            base_url="https://mh.gov.in",
            state_code="MH"
        )
        
        assert state_portal.is_available_for_location("MH", "PUNE") is True
        assert state_portal.is_available_for_location("UP", "LUCKNOW") is False
    
    def test_auth_token_validation(self):
        """Test AuthToken validation and expiration."""
        from datetime import datetime, timedelta
        
        # Valid token
        token = AuthToken(
            token="valid_token_123",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        assert token.is_valid() is True
        assert token.is_expired() is False
        
        # Expired token
        expired_token = AuthToken(
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        assert expired_token.is_valid() is False
        assert expired_token.is_expired() is True
        
        # Token without expiration
        no_expiry_token = AuthToken(token="no_expiry_token")
        assert no_expiry_token.is_valid() is True
        assert no_expiry_token.is_expired() is False


class TestAuthenticationManager:
    """Test authentication manager functionality."""
    
    @pytest.fixture
    def auth_manager(self):
        """Create authentication manager for testing."""
        return AuthenticationManager()
    
    @pytest.fixture
    def sample_portal(self):
        """Create sample portal for testing."""
        credentials = APICredentials(
            auth_method=AuthMethod.API_KEY,
            api_key="test_api_key_123"
        )
        
        return GovernmentPortal(
            id="test_portal",
            name="Test Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in",
            credentials=credentials
        )
    
    @pytest.mark.asyncio
    async def test_api_key_authentication(self, auth_manager, sample_portal):
        """Test API key authentication."""
        headers = await auth_manager.get_auth_headers(sample_portal)
        
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test_api_key_123"
    
    @pytest.mark.asyncio
    async def test_basic_auth_authentication(self, auth_manager):
        """Test basic authentication."""
        credentials = APICredentials(
            auth_method=AuthMethod.BASIC_AUTH,
            username="test_user",
            password="test_pass"
        )
        
        portal = GovernmentPortal(
            id="basic_auth_portal",
            name="Basic Auth Portal",
            portal_type=PortalType.STATE_GOVERNMENT,
            base_url="https://basic.gov.in",
            credentials=credentials
        )
        
        headers = await auth_manager.get_auth_headers(portal)
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
    
    @pytest.mark.asyncio
    async def test_oauth2_authentication_mock(self, auth_manager):
        """Test OAuth2 authentication with mocked HTTP client."""
        credentials = APICredentials(
            auth_method=AuthMethod.OAUTH2,
            client_id="test_client",
            client_secret="test_secret",
            token_endpoint="https://test.gov.in/oauth/token"
        )
        
        portal = GovernmentPortal(
            id="oauth_portal",
            name="OAuth Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in",
            credentials=credentials
        )
        
        # Mock the HTTP session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "access_token": "mock_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        with patch.object(auth_manager, '_ensure_session'), \
             patch.object(auth_manager, 'session') as mock_session:
            
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            headers = await auth_manager.get_auth_headers(portal)
            
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer mock_access_token"
    
    def test_credentials_validation(self, auth_manager):
        """Test credentials validation."""
        # Valid API key credentials
        valid_credentials = APICredentials(
            auth_method=AuthMethod.API_KEY,
            api_key="valid_key"
        )
        
        result = auth_manager.validate_credentials(valid_credentials)
        assert result.is_valid is True
        assert len(result.errors) == 0
        
        # Invalid API key credentials (missing key)
        invalid_credentials = APICredentials(
            auth_method=AuthMethod.API_KEY
        )
        
        result = auth_manager.validate_credentials(invalid_credentials)
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "API key is required" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_token_caching(self, auth_manager, sample_portal):
        """Test token caching functionality."""
        # First call should create token
        headers1 = await auth_manager.get_auth_headers(sample_portal)
        
        # Check if token is cached
        token_info = auth_manager.get_cached_token_info(sample_portal.id)
        assert token_info is None  # API key auth doesn't use tokens
        
        # Test with OAuth2 portal
        oauth_credentials = APICredentials(
            auth_method=AuthMethod.OAUTH2,
            client_id="test_client",
            client_secret="test_secret",
            token_endpoint="https://test.gov.in/oauth/token"
        )
        
        oauth_portal = GovernmentPortal(
            id="oauth_test",
            name="OAuth Test",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in",
            credentials=oauth_credentials
        )
        
        # Mock token in cache
        test_token = AuthToken(
            token="cached_token",
            expires_at=datetime.now() + timedelta(hours=1)
        )
        auth_manager.token_cache[oauth_portal.id] = test_token
        
        token_info = auth_manager.get_cached_token_info(oauth_portal.id)
        assert token_info is not None
        assert token_info["is_valid"] is True


class TestDataTransformer:
    """Test data transformation functionality."""
    
    @pytest.fixture
    def data_transformer(self):
        """Create data transformer for testing."""
        return DataTransformer()
    
    @pytest.fixture
    def sample_grievance(self):
        """Create sample grievance for testing."""
        details = GrievanceDetails(
            problem_description="My pension has been delayed for 3 months",
            grievance_type=GrievanceType.PENSION_ISSUE,
            location="Mumbai, Maharashtra",
            department="Pension Department"
        )
        
        contact = ContactInformation(
            phone_number="9876543210",
            email="test@example.com",
            address="123 Test Street, Mumbai",
            preferred_language="hi"
        )
        
        return GrievanceRecord(
            details=details,
            contact_info=contact,
            priority=GrievancePriority.MEDIUM,
            language="hi"
        )
    
    @pytest.fixture
    def sample_portal(self):
        """Create sample portal for testing."""
        endpoint = APIEndpoint(
            name="submit_grievance",
            url="/api/grievances",
            method="POST",
            required_fields=["complaint_description", "category_code", "mobile_number"],
            optional_fields=["email_id", "address"]
        )
        
        portal = GovernmentPortal(
            id="test_portal",
            name="Test Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in"
        )
        portal.add_endpoint(endpoint)
        
        return portal
    
    def test_grievance_data_extraction(self, data_transformer, sample_grievance):
        """Test extraction of source data from grievance."""
        source_data = data_transformer._extract_source_data(sample_grievance)
        
        assert "details" in source_data
        assert source_data["details"]["problem_description"] == "My pension has been delayed for 3 months"
        assert source_data["details"]["grievance_type"] == "pension_issue"
        
        assert "contact_info" in source_data
        assert source_data["contact_info"]["phone_number"] == "9876543210"
        assert source_data["contact_info"]["email"] == "test@example.com"
        
        assert source_data["priority"] == "medium"
        assert source_data["language"] == "hi"
    
    def test_transformation_rules_application(self, data_transformer, sample_grievance, sample_portal):
        """Test application of transformation rules."""
        endpoint = sample_portal.get_endpoint("submit_grievance")
        result = data_transformer.transform_grievance_data(sample_grievance, sample_portal, endpoint)
        
        assert result.is_valid is True
        assert result.transformed_data is not None
        
        # Check if required transformations were applied
        data = json.loads(result.transformed_data) if isinstance(result.transformed_data, str) else result.transformed_data
        
        # Should have transformed fields based on default rules
        assert "submission_timestamp" in data
        assert "source_system" in data
        assert data["source_system"] == "bharat_voice_assistant"
    
    def test_field_validation(self, data_transformer):
        """Test field validation functionality."""
        # Valid phone number
        result = data_transformer.validate_field_value("phone_number", "9876543210")
        assert result.is_valid is True
        
        # Invalid phone number
        result = data_transformer.validate_field_value("phone_number", "123")
        assert result.is_valid is False
        assert len(result.errors) > 0
        
        # Valid email
        result = data_transformer.validate_field_value("email", "test@example.com")
        assert result.is_valid is True
        
        # Invalid email
        result = data_transformer.validate_field_value("email", "invalid-email")
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_lookup_transformations(self, data_transformer):
        """Test lookup transformations."""
        # Grievance type lookup
        result = data_transformer._apply_lookup_transformation("category_code", "pension_issue")
        assert result == "PENSION"
        
        result = data_transformer._apply_lookup_transformation("category_code", "corruption_complaint")
        assert result == "CORRUPTION"
        
        # Priority lookup
        result = data_transformer._apply_lookup_transformation("urgency_level", "high")
        assert result == "HIGH"
        
        # Language lookup
        result = data_transformer._apply_lookup_transformation("preferred_language", "hi")
        assert result == "hindi"
    
    def test_format_conversions(self, data_transformer):
        """Test data format conversions."""
        test_data = {
            "name": "Test User",
            "phone": "9876543210",
            "details": {
                "problem": "Test problem",
                "category": "TEST"
            }
        }
        
        # Test JSON conversion
        json_result = data_transformer._to_json(test_data)
        assert isinstance(json_result, str)
        parsed = json.loads(json_result)
        assert parsed["name"] == "Test User"
        
        # Test XML conversion
        xml_result = data_transformer._to_xml(test_data)
        assert isinstance(xml_result, str)
        assert "<name>Test User</name>" in xml_result
        assert "<phone>9876543210</phone>" in xml_result
        
        # Test form data conversion
        form_result = data_transformer._to_form_data(test_data)
        assert isinstance(form_result, dict)
        assert form_result["name"] == "Test User"
        assert form_result["details_problem"] == "Test problem"


class TestGovernmentAPIClient:
    """Test government API client functionality."""
    
    @pytest.fixture
    def api_client(self):
        """Create API client for testing."""
        return GovernmentAPIClient()
    
    @pytest.fixture
    def sample_portal_with_endpoint(self):
        """Create sample portal with endpoint for testing."""
        credentials = APICredentials(
            auth_method=AuthMethod.API_KEY,
            api_key="test_key"
        )
        
        endpoint = APIEndpoint(
            name="submit_grievance",
            url="/api/v1/grievances",
            method="POST",
            data_format=DataFormat.JSON,
            required_fields=["description", "category"],
            success_codes=[200, 201]
        )
        
        portal = GovernmentPortal(
            id="test_portal",
            name="Test Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in",
            credentials=credentials
        )
        portal.add_endpoint(endpoint)
        
        return portal
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self, api_client, sample_portal_with_endpoint):
        """Test circuit breaker pattern."""
        portal = sample_portal_with_endpoint
        
        # Initially circuit breaker should be closed
        cb = api_client._get_circuit_breaker(portal.id)
        assert cb.can_execute() is True
        assert cb.state == "CLOSED"
        
        # Record failures to open circuit breaker
        for _ in range(5):
            cb.record_failure()
        
        assert cb.state == "OPEN"
        assert cb.can_execute() is False
        
        # Record success to close circuit breaker
        cb.record_success()
        assert cb.state == "CLOSED"
        assert cb.can_execute() is True
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, api_client):
        """Test rate limiting functionality."""
        portal = GovernmentPortal(
            id="rate_limited_portal",
            name="Rate Limited Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://test.gov.in",
            rate_limit=2  # 2 requests per minute
        )
        
        # First two requests should pass
        assert await api_client._check_rate_limit(portal) is True
        assert await api_client._check_rate_limit(portal) is True
        
        # Third request should be rate limited
        assert await api_client._check_rate_limit(portal) is False
    
    @pytest.mark.asyncio
    async def test_submit_grievance_mock(self, api_client, sample_portal_with_endpoint):
        """Test grievance submission with mocked HTTP client."""
        portal = sample_portal_with_endpoint
        test_data = {
            "description": "Test grievance",
            "category": "TEST",
            "phone": "9876543210"
        }
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "success": True,
            "reference_number": "TEST123456",
            "message": "Grievance submitted successfully"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        
        with patch.object(api_client, '_ensure_session'), \
             patch.object(api_client, 'session') as mock_session, \
             patch.object(api_client.auth_manager, 'get_auth_headers', return_value={"X-API-Key": "test_key"}):
            
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            result = await api_client.submit_grievance(portal, "submit_grievance", test_data)
            
            assert result.success is True
            assert result.status_code == 200
            assert result.data["reference_number"] == "TEST123456"
    
    @pytest.mark.asyncio
    async def test_check_status_mock(self, api_client, sample_portal_with_endpoint):
        """Test status checking with mocked HTTP client."""
        portal = sample_portal_with_endpoint
        
        # Add status endpoint
        status_endpoint = APIEndpoint(
            name="check_status",
            url="/api/v1/grievances/{reference_number}/status",
            method="GET",
            response_format=DataFormat.JSON
        )
        portal.add_endpoint(status_endpoint)
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "reference_number": "TEST123456",
            "status": "in_progress",
            "message": "Your grievance is being processed",
            "last_updated": "2024-01-15T10:30:00Z"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        
        with patch.object(api_client, '_ensure_session'), \
             patch.object(api_client, 'session') as mock_session, \
             patch.object(api_client.auth_manager, 'get_auth_headers', return_value={"X-API-Key": "test_key"}):
            
            mock_session.get.return_value.__aenter__.return_value = mock_response
            
            result = await api_client.check_status(portal, "check_status", "TEST123456")
            
            assert result.success is True
            assert result.status_code == 200
            assert result.data["reference_number"] == "TEST123456"
            assert result.data["status"] == "in_progress"


class TestGovernmentIntegrationService:
    """Test main integration service functionality."""
    
    @pytest.fixture
    def integration_config(self):
        """Create integration configuration for testing."""
        # Create test portals
        central_portal = GovernmentPortal(
            id="central_test",
            name="Central Test Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://central.test.gov.in",
            priority=1
        )
        
        central_portal.add_endpoint(APIEndpoint(
            name="submit_grievance",
            url="/api/grievances",
            method="POST",
            required_fields=["description", "category"]
        ))
        
        state_portal = GovernmentPortal(
            id="state_test",
            name="State Test Portal",
            portal_type=PortalType.STATE_GOVERNMENT,
            base_url="https://state.test.gov.in",
            state_code="MH",
            priority=2
        )
        
        state_portal.add_endpoint(APIEndpoint(
            name="submit_grievance",
            url="/api/complaints",
            method="POST",
            required_fields=["details", "category"]
        ))
        
        return IntegrationConfig(
            portals=[central_portal, state_portal],
            default_timeout=30,
            max_concurrent_requests=5
        )
    
    @pytest.fixture
    def sample_grievance(self):
        """Create sample grievance for testing."""
        details = GrievanceDetails(
            problem_description="Test grievance for integration",
            grievance_type=GrievanceType.SERVICE_DENIAL,
            location="Mumbai, Maharashtra"
        )
        
        contact = ContactInformation(
            phone_number="9876543210",
            email="test@example.com"
        )
        
        return GrievanceRecord(
            details=details,
            contact_info=contact,
            priority=GrievancePriority.HIGH,
            language="hi"
        )
    
    @pytest.mark.asyncio
    async def test_portal_selection(self, integration_config, sample_grievance):
        """Test portal selection logic."""
        service = GovernmentIntegrationService(integration_config)
        
        # Test portal selection for Maharashtra location
        sample_grievance.details.location = "Mumbai, Maharashtra"
        target_portals = service._select_target_portals(sample_grievance)
        
        # Should include both central and state portals, with central having higher priority
        assert len(target_portals) >= 1
        assert target_portals[0].portal_type in [PortalType.CENTRAL_GOVERNMENT, PortalType.STATE_GOVERNMENT]
    
    @pytest.mark.asyncio
    async def test_submit_grievance_mock_success(self, integration_config, sample_grievance):
        """Test successful grievance submission with mocked components."""
        service = GovernmentIntegrationService(integration_config)
        
        # Mock successful API response
        mock_api_response = APIResponse(
            success=True,
            status_code=200,
            data={
                "reference_number": "MOCK123456",
                "status": "submitted",
                "message": "Grievance submitted successfully"
            }
        )
        
        # Mock successful data transformation
        mock_transformation_result = Mock()
        mock_transformation_result.is_valid = True
        mock_transformation_result.transformed_data = {"test": "data"}
        
        with patch.object(service.api_client, 'submit_grievance', return_value=mock_api_response), \
             patch.object(service.data_transformer, 'transform_grievance_data', return_value=mock_transformation_result):
            
            result = await service.submit_grievance(sample_grievance)
            
            assert result.success is True
            assert result.reference_number == "MOCK123456"
            assert result.status == SubmissionStatus.SUBMITTED
    
    @pytest.mark.asyncio
    async def test_submit_grievance_with_fallback(self, integration_config, sample_grievance):
        """Test grievance submission with fallback to local storage."""
        service = GovernmentIntegrationService(integration_config)
        
        # Mock API failure
        with patch.object(service.api_client, 'submit_grievance', side_effect=GovernmentAPIError("API Error")), \
             patch.object(service.data_transformer, 'transform_grievance_data') as mock_transform:
            
            mock_transform.return_value.is_valid = True
            mock_transform.return_value.transformed_data = {"test": "data"}
            
            result = await service.submit_grievance(sample_grievance)
            
            # Should fail but still return a result indicating fallback
            assert result.success is False
            assert "failed" in result.message.lower()
    
    def test_integration_metrics(self, integration_config):
        """Test integration metrics collection."""
        service = GovernmentIntegrationService(integration_config)
        
        # Record some performance metrics
        service._record_performance_metric("test_portal", 1.5)
        service._record_performance_metric("test_portal", 2.0)
        service._record_performance_metric("test_portal", 1.8)
        
        metrics = service.get_integration_metrics()
        
        assert "performance_metrics" in metrics
        assert "test_portal" in metrics["performance_metrics"]
        assert metrics["performance_metrics"]["test_portal"]["count"] == 3
        assert metrics["performance_metrics"]["test_portal"]["avg_time"] == pytest.approx(1.77, rel=1e-2)
    
    def test_portal_status(self, integration_config):
        """Test portal status reporting."""
        service = GovernmentIntegrationService(integration_config)
        
        status = service.get_portal_status()
        
        assert "central_test" in status
        assert "state_test" in status
        
        central_status = status["central_test"]
        assert central_status["name"] == "Central Test Portal"
        assert central_status["type"] == "central_government"
        assert central_status["is_active"] is True
        assert central_status["priority"] == 1


class TestGovernmentPortalConfigLoader:
    """Test configuration loader functionality."""
    
    @pytest.fixture
    def config_loader(self, tmp_path):
        """Create config loader with temporary directory."""
        return GovernmentPortalConfigLoader(str(tmp_path))
    
    def test_yaml_config_loading(self, config_loader, tmp_path):
        """Test loading configuration from YAML file."""
        # Create test YAML config
        yaml_content = """
portals:
  - id: "test_yaml_portal"
    name: "Test YAML Portal"
    type: "central_government"
    base_url: "https://yaml.test.gov.in"
    is_active: true
    priority: 1
    credentials:
      auth_method: "api_key"
      api_key: "yaml_test_key"
    endpoints:
      - name: "submit_grievance"
        url: "/api/grievances"
        method: "POST"
        required_fields: ["description", "category"]
"""
        
        yaml_file = tmp_path / "test_config.yaml"
        yaml_file.write_text(yaml_content)
        
        portals = config_loader._load_yaml_file(yaml_file)
        
        assert len(portals) == 1
        portal = portals[0]
        assert portal.id == "test_yaml_portal"
        assert portal.name == "Test YAML Portal"
        assert portal.portal_type == PortalType.CENTRAL_GOVERNMENT
        assert portal.credentials.auth_method == AuthMethod.API_KEY
        assert "submit_grievance" in portal.endpoints
    
    def test_json_config_loading(self, config_loader, tmp_path):
        """Test loading configuration from JSON file."""
        # Create test JSON config
        json_content = {
            "portals": [
                {
                    "id": "test_json_portal",
                    "name": "Test JSON Portal",
                    "type": "state_government",
                    "base_url": "https://json.test.gov.in",
                    "state_code": "MH",
                    "credentials": {
                        "auth_method": "basic_auth",
                        "username": "test_user",
                        "password": "test_pass"
                    },
                    "endpoints": [
                        {
                            "name": "submit_grievance",
                            "url": "/api/complaints",
                            "method": "POST",
                            "data_format": "json"
                        }
                    ]
                }
            ]
        }
        
        json_file = tmp_path / "test_config.json"
        json_file.write_text(json.dumps(json_content))
        
        portals = config_loader._load_json_file(json_file)
        
        assert len(portals) == 1
        portal = portals[0]
        assert portal.id == "test_json_portal"
        assert portal.portal_type == PortalType.STATE_GOVERNMENT
        assert portal.state_code == "MH"
        assert portal.credentials.auth_method == AuthMethod.BASIC_AUTH
    
    def test_portal_validation(self, config_loader):
        """Test portal configuration validation."""
        # Valid portal
        valid_portal = GovernmentPortal(
            id="valid_portal",
            name="Valid Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://valid.gov.in",
            credentials=APICredentials(
                auth_method=AuthMethod.API_KEY,
                api_key="valid_key"
            )
        )
        
        valid_portal.add_endpoint(APIEndpoint(
            name="test_endpoint",
            url="/api/test",
            method="POST"
        ))
        
        issues = config_loader.validate_portal_config(valid_portal)
        assert len(issues) == 0
        
        # Invalid portal (missing required fields)
        invalid_portal = GovernmentPortal(
            id="",  # Empty ID
            name="Invalid Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="invalid-url"  # Invalid URL format
        )
        
        issues = config_loader.validate_portal_config(invalid_portal)
        assert len(issues) > 0
        assert any("Portal ID is required" in issue for issue in issues)
        assert any("Base URL must start with http" in issue for issue in issues)


# Integration test markers
pytestmark = pytest.mark.integration