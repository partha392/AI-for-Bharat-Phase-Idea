"""
Government system integration layer for Bharat Voice Assistant.

This module provides integration with state and central government portals,
including API connections, authentication management, data transformation,
and error handling with retry mechanisms.
"""

from .government_api_client import (
    GovernmentAPIClient,
    APIEndpoint,
    APICredentials,
    APIResponse
)

from .auth_manager import (
    AuthenticationManager,
    AuthToken,
    AuthMethod
)

from .secure_auth_protocols import (
    SecureAuthenticationManager,
    SecureAuthMethod,
    SecureAuthContext,
    AuthenticationResult
)

from .data_transformer import (
    DataTransformer,
    TransformationRule,
    ValidationResult
)

from .integration_service import (
    GovernmentIntegrationService,
    IntegrationResult,
    SubmissionStatus
)

from .models import (
    GovernmentPortal,
    PortalType,
    IntegrationConfig,
    SubmissionRequest,
    StatusResponse
)

__all__ = [
    'GovernmentAPIClient',
    'APIEndpoint',
    'APICredentials', 
    'APIResponse',
    'AuthenticationManager',
    'AuthToken',
    'AuthMethod',
    'SecureAuthenticationManager',
    'SecureAuthMethod',
    'SecureAuthContext',
    'AuthenticationResult',
    'DataTransformer',
    'TransformationRule',
    'ValidationResult',
    'GovernmentIntegrationService',
    'IntegrationResult',
    'SubmissionStatus',
    'GovernmentPortal',
    'PortalType',
    'IntegrationConfig',
    'SubmissionRequest',
    'StatusResponse'
]