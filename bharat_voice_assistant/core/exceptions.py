"""
Custom exceptions for the Bharat Voice Assistant.

This module defines all custom exceptions used throughout the application,
providing structured error handling with proper categorization and context.
"""

from typing import Optional, Dict, Any


class BharatVoiceAssistantError(Exception):
    """Base exception for all Bharat Voice Assistant errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context
        }


# Configuration and Infrastructure Errors
class ConfigurationError(BharatVoiceAssistantError):
    """Raised when there's a configuration issue."""
    pass


class AWSServiceError(BharatVoiceAssistantError):
    """Raised when AWS service operations fail."""
    pass


class DatabaseError(BharatVoiceAssistantError):
    """Raised when database operations fail."""
    pass


class NetworkError(BharatVoiceAssistantError):
    """Raised when network operations fail."""
    pass


# Voice Processing Errors
class VoiceProcessingError(BharatVoiceAssistantError):
    """Base class for voice processing errors."""
    pass


class VoiceGatewayError(VoiceProcessingError):
    """Raised when voice gateway operations fail."""
    pass


class AudioProcessingError(VoiceProcessingError):
    """Raised when audio processing operations fail."""
    pass


class ConnectionError(VoiceProcessingError):
    """Raised when WebSocket connection operations fail."""
    pass


class SpeechRecognitionError(VoiceProcessingError):
    """Raised when speech recognition fails."""
    pass


class TextToSpeechError(VoiceProcessingError):
    """Raised when text-to-speech conversion fails."""
    pass


class AudioQualityError(VoiceProcessingError):
    """Raised when audio quality is insufficient for processing."""
    pass


class UnsupportedLanguageError(VoiceProcessingError):
    """Raised when an unsupported language is requested."""
    pass


# Language Processing Errors
class LanguageProcessingError(BharatVoiceAssistantError):
    """Base class for language processing errors."""
    pass


class IntentRecognitionError(LanguageProcessingError):
    """Raised when intent recognition fails."""
    pass


class EntityExtractionError(LanguageProcessingError):
    """Raised when entity extraction fails."""
    pass


class ContextManagementError(LanguageProcessingError):
    """Raised when conversation context management fails."""
    pass


# Scheme Discovery Errors
class SchemeDiscoveryError(BharatVoiceAssistantError):
    """Base class for scheme discovery errors."""
    pass


class SchemeNotFoundError(SchemeDiscoveryError):
    """Raised when no relevant schemes are found."""
    pass


class EligibilityCheckError(SchemeDiscoveryError):
    """Raised when eligibility checking fails."""
    pass


class SchemeDataError(SchemeDiscoveryError):
    """Raised when scheme data is invalid or corrupted."""
    pass


# Grievance Management Errors
class GrievanceError(BharatVoiceAssistantError):
    """Base class for grievance management errors."""
    pass


class GrievanceFilingError(GrievanceError):
    """Raised when grievance filing fails."""
    pass


class GrievanceValidationError(GrievanceError):
    """Raised when grievance data validation fails."""
    pass


class GrievanceStatusError(GrievanceError):
    """Raised when grievance status operations fail."""
    pass


# Government Integration Errors
class GovernmentIntegrationError(BharatVoiceAssistantError):
    """Base class for government system integration errors."""
    pass


class GovernmentAPIError(GovernmentIntegrationError):
    """Raised when government API calls fail."""
    pass


class AuthenticationError(GovernmentIntegrationError):
    """Raised when authentication with government systems fails."""
    pass


class DataSynchronizationError(GovernmentIntegrationError):
    """Raised when data synchronization with government systems fails."""
    pass


# Privacy and Security Errors
class PrivacyError(BharatVoiceAssistantError):
    """Base class for privacy-related errors."""
    pass


class ConsentError(PrivacyError):
    """Raised when user consent is missing or invalid."""
    pass


class DataEncryptionError(PrivacyError):
    """Raised when data encryption/decryption fails."""
    pass


class DataRetentionError(PrivacyError):
    """Raised when data retention policies are violated."""
    pass


# User Experience Errors
class UserExperienceError(BharatVoiceAssistantError):
    """Base class for user experience errors."""
    pass


class UserInputError(UserExperienceError):
    """Raised when user input is invalid or cannot be processed."""
    pass


class AccessibilityError(UserExperienceError):
    """Raised when accessibility requirements cannot be met."""
    pass


class BandwidthError(UserExperienceError):
    """Raised when bandwidth limitations prevent proper service."""
    pass


# Validation Errors
class ValidationError(BharatVoiceAssistantError):
    """Raised when data validation fails."""
    pass


class RequiredFieldError(ValidationError):
    """Raised when a required field is missing."""
    pass


class InvalidFormatError(ValidationError):
    """Raised when data format is invalid."""
    pass


# Rate Limiting and Throttling Errors
class RateLimitError(BharatVoiceAssistantError):
    """Raised when rate limits are exceeded."""
    pass


class ThrottlingError(BharatVoiceAssistantError):
    """Raised when service is being throttled."""
    pass


# Timeout Errors
class TimeoutError(BharatVoiceAssistantError):
    """Raised when operations timeout."""
    pass


class ResponseTimeoutError(TimeoutError):
    """Raised when response times exceed acceptable limits."""
    pass


# Error Handler Utility Functions
def handle_aws_error(error: Exception, operation: str, context: Dict[str, Any] = None) -> BharatVoiceAssistantError:
    """
    Convert AWS SDK errors to application-specific errors.
    
    Args:
        error: The original AWS error
        operation: Description of the operation that failed
        context: Additional context information
        
    Returns:
        Appropriate application-specific error
    """
    error_context = context or {}
    error_context['operation'] = operation
    error_context['original_error'] = str(error)
    
    # Map common AWS errors to application errors
    error_str = str(error).lower()
    
    if 'throttling' in error_str or 'rate' in error_str:
        return RateLimitError(
            f"AWS service rate limit exceeded during {operation}",
            error_code="AWS_RATE_LIMIT",
            context=error_context
        )
    elif 'timeout' in error_str:
        return TimeoutError(
            f"AWS service timeout during {operation}",
            error_code="AWS_TIMEOUT",
            context=error_context
        )
    elif 'credentials' in error_str or 'access' in error_str:
        return AuthenticationError(
            f"AWS authentication failed during {operation}",
            error_code="AWS_AUTH_FAILED",
            context=error_context
        )
    else:
        return AWSServiceError(
            f"AWS service error during {operation}: {error}",
            error_code="AWS_SERVICE_ERROR",
            context=error_context
        )


def handle_network_error(error: Exception, operation: str, context: Dict[str, Any] = None) -> NetworkError:
    """
    Convert network errors to application-specific errors.
    
    Args:
        error: The original network error
        operation: Description of the operation that failed
        context: Additional context information
        
    Returns:
        NetworkError with appropriate context
    """
    error_context = context or {}
    error_context['operation'] = operation
    error_context['original_error'] = str(error)
    
    return NetworkError(
        f"Network error during {operation}: {error}",
        error_code="NETWORK_ERROR",
        context=error_context
    )


def handle_validation_error(field: str, value: Any, expected: str, context: Dict[str, Any] = None) -> ValidationError:
    """
    Create a validation error with proper context.
    
    Args:
        field: Name of the field that failed validation
        value: The invalid value
        expected: Description of expected format/value
        context: Additional context information
        
    Returns:
        ValidationError with appropriate context
    """
    error_context = context or {}
    error_context.update({
        'field': field,
        'value': str(value),
        'expected': expected
    })
    
    return ValidationError(
        f"Validation failed for field '{field}': expected {expected}, got {value}",
        error_code="VALIDATION_FAILED",
        context=error_context
    )