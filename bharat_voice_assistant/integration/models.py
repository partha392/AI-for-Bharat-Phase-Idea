"""
Data models for government system integration.

This module defines the data structures used for integrating with
government portals and APIs.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from uuid import UUID, uuid4


class PortalType(Enum):
    """Types of government portals."""
    CENTRAL_GOVERNMENT = "central_government"
    STATE_GOVERNMENT = "state_government"
    DISTRICT_PORTAL = "district_portal"
    MUNICIPAL_PORTAL = "municipal_portal"
    GRIEVANCE_PORTAL = "grievance_portal"
    SCHEME_PORTAL = "scheme_portal"
    CITIZEN_SERVICES = "citizen_services"


class AuthMethod(Enum):
    """Authentication methods for government APIs."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT_TOKEN = "jwt_token"
    CERTIFICATE = "certificate"
    BASIC_AUTH = "basic_auth"
    SAML = "saml"
    DIGITAL_SIGNATURE = "digital_signature"


class SubmissionStatus(Enum):
    """Status of grievance submission to government systems."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMEOUT = "timeout"


class DataFormat(Enum):
    """Data formats supported by government APIs."""
    JSON = "json"
    XML = "xml"
    FORM_DATA = "form_data"
    SOAP = "soap"
    CSV = "csv"
    PDF = "pdf"


@dataclass
class APICredentials:
    """Credentials for government API authentication."""
    auth_method: AuthMethod
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    certificate_path: Optional[str] = None
    private_key_path: Optional[str] = None
    token_endpoint: Optional[str] = None
    scope: Optional[str] = None
    additional_headers: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert credentials to dictionary (excluding sensitive data)."""
        return {
            'auth_method': self.auth_method.value,
            'client_id': self.client_id,
            'username': self.username,
            'token_endpoint': self.token_endpoint,
            'scope': self.scope,
            'has_api_key': bool(self.api_key),
            'has_client_secret': bool(self.client_secret),
            'has_password': bool(self.password),
            'has_certificate': bool(self.certificate_path),
            'additional_headers': list(self.additional_headers.keys())
        }


@dataclass
class APIEndpoint:
    """Government API endpoint configuration."""
    name: str
    url: str
    method: str = "POST"
    data_format: DataFormat = DataFormat.JSON
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    response_format: DataFormat = DataFormat.JSON
    success_codes: List[int] = field(default_factory=lambda: [200, 201, 202])
    headers: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate endpoint configuration."""
        # Allow relative URLs (starting with /) or absolute URLs
        if not (self.url.startswith(('http://', 'https://')) or self.url.startswith('/')):
            raise ValueError(f"Invalid URL format: {self.url}")
        
        if self.method.upper() not in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
            raise ValueError(f"Unsupported HTTP method: {self.method}")


@dataclass
class GovernmentPortal:
    """Configuration for a government portal."""
    id: str
    name: str
    portal_type: PortalType
    base_url: str
    state_code: Optional[str] = None
    district_code: Optional[str] = None
    credentials: Optional[APICredentials] = None
    endpoints: Dict[str, APIEndpoint] = field(default_factory=dict)
    is_active: bool = True
    priority: int = 1  # Lower number = higher priority
    supported_languages: List[str] = field(default_factory=lambda: ['hi', 'en'])
    rate_limit: Optional[int] = None  # Requests per minute
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_endpoint(self, endpoint_name: str) -> Optional[APIEndpoint]:
        """Get endpoint configuration by name."""
        return self.endpoints.get(endpoint_name)
    
    def add_endpoint(self, endpoint: APIEndpoint):
        """Add an endpoint to the portal."""
        self.endpoints[endpoint.name] = endpoint
    
    def is_available_for_location(self, state_code: str, district_code: str = None) -> bool:
        """Check if portal is available for given location."""
        if self.portal_type == PortalType.CENTRAL_GOVERNMENT:
            return True
        
        if self.state_code and self.state_code != state_code:
            return False
        
        if self.district_code and district_code and self.district_code != district_code:
            return False
        
        return True


@dataclass
class IntegrationConfig:
    """Configuration for government system integration."""
    portals: List[GovernmentPortal] = field(default_factory=list)
    default_timeout: int = 30
    max_concurrent_requests: int = 10
    retry_strategy: str = "exponential_backoff"
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    enable_caching: bool = True
    cache_ttl: int = 300  # 5 minutes
    enable_monitoring: bool = True
    
    def get_portals_by_type(self, portal_type: PortalType) -> List[GovernmentPortal]:
        """Get portals by type."""
        return [portal for portal in self.portals if portal.portal_type == portal_type]
    
    def get_portals_for_location(self, state_code: str, district_code: str = None) -> List[GovernmentPortal]:
        """Get available portals for a location."""
        available_portals = []
        for portal in self.portals:
            if portal.is_active and portal.is_available_for_location(state_code, district_code):
                available_portals.append(portal)
        
        # Sort by priority (lower number = higher priority)
        return sorted(available_portals, key=lambda p: p.priority)


@dataclass
class SubmissionRequest:
    """Request for submitting data to government portal."""
    portal_id: str
    endpoint_name: str
    data: Dict[str, Any]
    reference_id: Optional[str] = None
    user_id: Optional[str] = None
    language: str = "hi"
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            'portal_id': self.portal_id,
            'endpoint_name': self.endpoint_name,
            'data': self.data,
            'reference_id': self.reference_id,
            'user_id': self.user_id,
            'language': self.language,
            'priority': self.priority,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class APIResponse:
    """Response from government API."""
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    reference_number: Optional[str] = None
    response_time: Optional[float] = None
    headers: Dict[str, str] = field(default_factory=dict)
    raw_response: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.success and 200 <= self.status_code < 300
    
    def get_reference_number(self) -> Optional[str]:
        """Extract reference number from response."""
        if self.reference_number:
            return self.reference_number
        
        if self.data:
            # Try common field names for reference numbers
            ref_fields = ['reference_number', 'ref_no', 'ticket_id', 'complaint_id', 'application_id']
            for field in ref_fields:
                if field in self.data:
                    return str(self.data[field])
        
        return None


@dataclass
class StatusResponse:
    """Response for status inquiry."""
    reference_number: str
    status: SubmissionStatus
    status_message: str
    last_updated: datetime
    assigned_officer: Optional[str] = None
    department: Optional[str] = None
    estimated_resolution_date: Optional[date] = None
    actions_taken: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert status response to dictionary."""
        return {
            'reference_number': self.reference_number,
            'status': self.status.value,
            'status_message': self.status_message,
            'last_updated': self.last_updated.isoformat(),
            'assigned_officer': self.assigned_officer,
            'department': self.department,
            'estimated_resolution_date': self.estimated_resolution_date.isoformat() if self.estimated_resolution_date else None,
            'actions_taken': self.actions_taken,
            'next_steps': self.next_steps,
            'additional_info': self.additional_info
        }


@dataclass
class IntegrationResult:
    """Result of integration operation."""
    success: bool
    portal_id: str
    operation: str
    reference_number: Optional[str] = None
    status: Optional[SubmissionStatus] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'success': self.success,
            'portal_id': self.portal_id,
            'operation': self.operation,
            'reference_number': self.reference_number,
            'status': self.status.value if self.status else None,
            'message': self.message,
            'error_code': self.error_code,
            'response_data': self.response_data,
            'execution_time': self.execution_time,
            'retry_count': self.retry_count,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TransformationRule:
    """Rule for transforming data between formats."""
    source_field: str
    target_field: str
    transformation_type: str = "direct"  # direct, format, calculate, lookup
    format_pattern: Optional[str] = None
    default_value: Optional[Any] = None
    required: bool = False
    validation_pattern: Optional[str] = None
    transformation_function: Optional[str] = None
    
    def apply(self, source_data: Dict[str, Any]) -> Any:
        """Apply transformation rule to source data."""
        source_value = source_data.get(self.source_field)
        
        if source_value is None:
            if self.required:
                raise ValueError(f"Required field '{self.source_field}' is missing")
            return self.default_value
        
        if self.transformation_type == "direct":
            return source_value
        elif self.transformation_type == "format" and self.format_pattern:
            return self.format_pattern.format(source_value)
        elif self.transformation_type == "calculate" and self.transformation_function:
            # This would be implemented with a function registry
            return source_value
        else:
            return source_value


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    invalid_fields: List[str] = field(default_factory=list)
    transformed_data: Optional[Dict[str, Any]] = None
    
    def add_error(self, error: str):
        """Add validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add validation warning."""
        self.warnings.append(warning)
    
    def add_missing_field(self, field: str):
        """Add missing field."""
        self.missing_fields.append(field)
        self.is_valid = False
    
    def add_invalid_field(self, field: str):
        """Add invalid field."""
        self.invalid_fields.append(field)
        self.is_valid = False


@dataclass
class AuthToken:
    """Authentication token for government APIs."""
    token: str
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    portal_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.now() >= self.expires_at
    
    def is_valid(self) -> bool:
        """Check if token is valid."""
        return bool(self.token) and not self.is_expired()
    
    def to_header(self) -> Dict[str, str]:
        """Convert token to authorization header."""
        return {'Authorization': f'{self.token_type} {self.token}'}