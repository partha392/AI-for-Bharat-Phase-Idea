"""
Data validation and integrity checking service.

This module provides comprehensive data validation and integrity checking
for all data flowing through the Bharat Voice Assistant system, ensuring
data quality, security, and compliance with government standards.
"""

import asyncio
import hashlib
import hmac
import json
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

from .security import SecurityProtocolManager, SecurityEventType, SecurityLevel
from .logging import get_logger
from .exceptions import ValidationError, DataEncryptionError
from .config import config

logger = get_logger(__name__)


class DataType(Enum):
    """Types of data for validation."""
    PERSONAL_INFO = "personal_info"
    VOICE_RECORDING = "voice_recording"
    GOVERNMENT_DOCUMENT = "government_document"
    SCHEME_DATA = "scheme_data"
    GRIEVANCE_DATA = "grievance_data"
    USER_INPUT = "user_input"
    API_RESPONSE = "api_response"
    FINANCIAL_DATA = "financial_data"
    LOCATION_DATA = "location_data"
    BIOMETRIC_DATA = "biometric_data"


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationRule:
    """Data validation rule definition."""
    field_name: str
    rule_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required: bool = True
    severity: ValidationSeverity = ValidationSeverity.ERROR
    error_message: Optional[str] = None
    custom_validator: Optional[Callable] = None


@dataclass
class ValidationIssue:
    """Data validation issue."""
    field_name: str
    rule_type: str
    severity: ValidationSeverity
    message: str
    value: Any
    expected: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    data_hash: Optional[str] = None
    validation_timestamp: datetime = field(default_factory=datetime.utcnow)
    data_type: Optional[DataType] = None
    
    def add_issue(self, issue: ValidationIssue):
        """Add a validation issue."""
        if issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
            self.issues.append(issue)
            self.is_valid = False
        else:
            self.warnings.append(issue)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of validation errors."""
        return {
            'is_valid': self.is_valid,
            'error_count': len(self.issues),
            'warning_count': len(self.warnings),
            'critical_issues': len([i for i in self.issues if i.severity == ValidationSeverity.CRITICAL]),
            'validation_timestamp': self.validation_timestamp.isoformat(),
            'data_type': self.data_type.value if self.data_type else None
        }


class DataValidationService:
    """
    Comprehensive data validation and integrity checking service.
    
    This service provides:
    - Field-level validation with custom rules
    - Data type validation and conversion
    - Security validation (XSS, SQL injection, etc.)
    - Government data format validation
    - Data integrity checking with checksums
    - Compliance validation for privacy regulations
    """
    
    def __init__(self, security_manager: SecurityProtocolManager):
        """Initialize data validation service."""
        self.security_manager = security_manager
        self._validation_rules: Dict[DataType, List[ValidationRule]] = {}
        self._custom_validators: Dict[str, Callable] = {}
        
        # Initialize built-in validation rules
        self._initialize_validation_rules()
        self._initialize_custom_validators()
        
        logger.info("Data validation service initialized")
    
    def _initialize_validation_rules(self):
        """Initialize built-in validation rules for different data types."""
        
        # Personal Information Validation Rules
        self._validation_rules[DataType.PERSONAL_INFO] = [
            ValidationRule(
                field_name="name",
                rule_type="string_length",
                parameters={"min_length": 2, "max_length": 100},
                required=True,
                error_message="Name must be between 2 and 100 characters"
            ),
            ValidationRule(
                field_name="phone",
                rule_type="indian_phone",
                required=True,
                error_message="Invalid Indian phone number format"
            ),
            ValidationRule(
                field_name="email",
                rule_type="email",
                required=False,
                error_message="Invalid email address format"
            ),
            ValidationRule(
                field_name="aadhaar",
                rule_type="aadhaar_number",
                required=False,
                error_message="Invalid Aadhaar number format"
            ),
            ValidationRule(
                field_name="pan",
                rule_type="pan_number",
                required=False,
                error_message="Invalid PAN number format"
            ),
            ValidationRule(
                field_name="address",
                rule_type="string_length",
                parameters={"min_length": 10, "max_length": 500},
                required=False,
                error_message="Address must be between 10 and 500 characters"
            )
        ]
        
        # Voice Recording Validation Rules
        self._validation_rules[DataType.VOICE_RECORDING] = [
            ValidationRule(
                field_name="audio_data",
                rule_type="binary_data",
                parameters={"min_size": 1024, "max_size": 10485760},  # 1KB to 10MB
                required=True,
                error_message="Audio data must be between 1KB and 10MB"
            ),
            ValidationRule(
                field_name="duration",
                rule_type="numeric_range",
                parameters={"min_value": 1, "max_value": 300},  # 1 second to 5 minutes
                required=True,
                error_message="Audio duration must be between 1 and 300 seconds"
            ),
            ValidationRule(
                field_name="language",
                rule_type="supported_language",
                required=True,
                error_message="Language must be one of the supported languages"
            ),
            ValidationRule(
                field_name="quality_score",
                rule_type="numeric_range",
                parameters={"min_value": 0.0, "max_value": 1.0},
                required=False,
                error_message="Quality score must be between 0.0 and 1.0"
            )
        ]
        
        # Government Document Validation Rules
        self._validation_rules[DataType.GOVERNMENT_DOCUMENT] = [
            ValidationRule(
                field_name="document_type",
                rule_type="government_document_type",
                required=True,
                error_message="Invalid government document type"
            ),
            ValidationRule(
                field_name="document_number",
                rule_type="alphanumeric",
                parameters={"min_length": 5, "max_length": 50},
                required=True,
                error_message="Document number must be 5-50 alphanumeric characters"
            ),
            ValidationRule(
                field_name="issuing_authority",
                rule_type="string_length",
                parameters={"min_length": 3, "max_length": 200},
                required=True,
                error_message="Issuing authority must be 3-200 characters"
            ),
            ValidationRule(
                field_name="issue_date",
                rule_type="date",
                required=True,
                error_message="Valid issue date is required"
            ),
            ValidationRule(
                field_name="expiry_date",
                rule_type="date",
                required=False,
                error_message="Expiry date must be a valid date"
            )
        ]
        
        # Scheme Data Validation Rules
        self._validation_rules[DataType.SCHEME_DATA] = [
            ValidationRule(
                field_name="scheme_id",
                rule_type="alphanumeric",
                parameters={"min_length": 5, "max_length": 20},
                required=True,
                error_message="Scheme ID must be 5-20 alphanumeric characters"
            ),
            ValidationRule(
                field_name="scheme_name",
                rule_type="string_length",
                parameters={"min_length": 5, "max_length": 200},
                required=True,
                error_message="Scheme name must be 5-200 characters"
            ),
            ValidationRule(
                field_name="eligibility_criteria",
                rule_type="json_object",
                required=True,
                error_message="Eligibility criteria must be a valid JSON object"
            ),
            ValidationRule(
                field_name="benefit_amount",
                rule_type="currency",
                required=False,
                error_message="Benefit amount must be a valid currency value"
            ),
            ValidationRule(
                field_name="application_deadline",
                rule_type="future_date",
                required=False,
                error_message="Application deadline must be a future date"
            )
        ]
        
        # Grievance Data Validation Rules
        self._validation_rules[DataType.GRIEVANCE_DATA] = [
            ValidationRule(
                field_name="grievance_type",
                rule_type="grievance_category",
                required=True,
                error_message="Invalid grievance category"
            ),
            ValidationRule(
                field_name="description",
                rule_type="string_length",
                parameters={"min_length": 20, "max_length": 2000},
                required=True,
                error_message="Grievance description must be 20-2000 characters"
            ),
            ValidationRule(
                field_name="priority",
                rule_type="enum",
                parameters={"allowed_values": ["low", "medium", "high", "urgent"]},
                required=True,
                error_message="Priority must be low, medium, high, or urgent"
            ),
            ValidationRule(
                field_name="supporting_documents",
                rule_type="document_list",
                required=False,
                error_message="Supporting documents must be a valid list"
            )
        ]
        
        # User Input Validation Rules
        self._validation_rules[DataType.USER_INPUT] = [
            ValidationRule(
                field_name="*",  # Apply to all fields
                rule_type="xss_protection",
                required=False,
                severity=ValidationSeverity.CRITICAL,
                error_message="Input contains potentially malicious script content"
            ),
            ValidationRule(
                field_name="*",
                rule_type="sql_injection_protection",
                required=False,
                severity=ValidationSeverity.CRITICAL,
                error_message="Input contains potentially malicious SQL content"
            ),
            ValidationRule(
                field_name="*",
                rule_type="command_injection_protection",
                required=False,
                severity=ValidationSeverity.CRITICAL,
                error_message="Input contains potentially malicious command content"
            )
        ]
    
    def _initialize_custom_validators(self):
        """Initialize custom validation functions."""
        
        def validate_indian_phone(value: str) -> bool:
            """Validate Indian phone number."""
            patterns = [
                r'^\+91[6-9]\d{9}$',  # +91 followed by 10 digits starting with 6-9
                r'^[6-9]\d{9}$',      # 10 digits starting with 6-9
                r'^0[6-9]\d{9}$'      # 0 followed by 10 digits starting with 6-9
            ]
            return any(re.match(pattern, value) for pattern in patterns)
        
        def validate_email(value: str) -> bool:
            """Validate email address."""
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(pattern, value))
        
        def validate_aadhaar_number(value: str) -> bool:
            """Validate Aadhaar number."""
            # Remove spaces and hyphens
            clean_value = re.sub(r'[\s-]', '', value)
            # Check if it's 12 digits
            if not re.match(r'^\d{12}$', clean_value):
                return False
            # Simple checksum validation (Verhoeff algorithm would be more accurate)
            return True
        
        def validate_pan_number(value: str) -> bool:
            """Validate PAN number."""
            pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
            return bool(re.match(pattern, value.upper()))
        
        def validate_supported_language(value: str) -> bool:
            """Validate supported language code."""
            supported_languages = config.voice.supported_languages.keys()
            return value.lower() in supported_languages
        
        def validate_government_document_type(value: str) -> bool:
            """Validate government document type."""
            valid_types = [
                'aadhaar', 'pan', 'voter_id', 'passport', 'driving_license',
                'ration_card', 'income_certificate', 'caste_certificate',
                'domicile_certificate', 'birth_certificate', 'death_certificate'
            ]
            return value.lower() in valid_types
        
        def validate_grievance_category(value: str) -> bool:
            """Validate grievance category."""
            valid_categories = [
                'pension', 'healthcare', 'education', 'employment', 'housing',
                'water_supply', 'electricity', 'transport', 'agriculture',
                'social_welfare', 'corruption', 'other'
            ]
            return value.lower() in valid_categories
        
        # Register custom validators
        self._custom_validators.update({
            'indian_phone': validate_indian_phone,
            'email': validate_email,
            'aadhaar_number': validate_aadhaar_number,
            'pan_number': validate_pan_number,
            'supported_language': validate_supported_language,
            'government_document_type': validate_government_document_type,
            'grievance_category': validate_grievance_category
        })
    
    async def validate_data(self, data: Dict[str, Any], data_type: DataType,
                          user_id: Optional[str] = None,
                          session_id: Optional[str] = None) -> ValidationResult:
        """
        Validate data according to specified data type rules.
        
        Args:
            data: Data to validate
            data_type: Type of data being validated
            user_id: User identifier for audit logging
            session_id: Session identifier for audit logging
            
        Returns:
            ValidationResult with validation status and issues
        """
        start_time = datetime.utcnow()
        result = ValidationResult(is_valid=True, data_type=data_type)
        
        try:
            # Get validation rules for data type
            rules = self._validation_rules.get(data_type, [])
            
            # Calculate data hash for integrity checking
            result.data_hash = self._calculate_data_hash(data)
            
            # Apply validation rules
            for rule in rules:
                await self._apply_validation_rule(data, rule, result)
            
            # Apply security validations for user input
            if data_type == DataType.USER_INPUT:
                await self._apply_security_validations(data, result)
            
            # Log validation result
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self.security_manager.log_security_event(
                SecurityEventType.DATA_ACCESS if result.is_valid else SecurityEventType.SECURITY_VIOLATION,
                "data_validation_service",
                "validate_data",
                result.is_valid,
                user_id=user_id,
                session_id=session_id,
                details={
                    'data_type': data_type.value,
                    'field_count': len(data),
                    'error_count': len(result.issues),
                    'warning_count': len(result.warnings),
                    'duration_ms': duration_ms,
                    'data_hash': result.data_hash[:16] + "..." if result.data_hash else None
                },
                security_level=SecurityLevel.HIGH if not result.is_valid else SecurityLevel.MEDIUM,
                data_classification=data_type.value
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Data validation failed: {e}")
            
            # Log validation error
            self.security_manager.log_security_event(
                SecurityEventType.SECURITY_VIOLATION,
                "data_validation_service",
                "validate_data",
                False,
                user_id=user_id,
                session_id=session_id,
                details={
                    'data_type': data_type.value,
                    'error': str(e)
                },
                security_level=SecurityLevel.CRITICAL,
                data_classification=data_type.value
            )
            
            result.is_valid = False
            result.add_issue(ValidationIssue(
                field_name="validation_system",
                rule_type="system_error",
                severity=ValidationSeverity.CRITICAL,
                message=f"Validation system error: {str(e)}",
                value=None
            ))
            
            return result
    
    async def _apply_validation_rule(self, data: Dict[str, Any], 
                                   rule: ValidationRule, 
                                   result: ValidationResult):
        """Apply a single validation rule to data."""
        try:
            # Handle wildcard field names
            fields_to_check = []
            if rule.field_name == "*":
                fields_to_check = list(data.keys())
            elif rule.field_name in data:
                fields_to_check = [rule.field_name]
            elif rule.required:
                # Required field is missing
                result.add_issue(ValidationIssue(
                    field_name=rule.field_name,
                    rule_type=rule.rule_type,
                    severity=rule.severity,
                    message=rule.error_message or f"Required field '{rule.field_name}' is missing",
                    value=None,
                    expected="Required field"
                ))
                return
            
            # Apply rule to each field
            for field_name in fields_to_check:
                field_value = data[field_name]
                is_valid = await self._validate_field(field_value, rule)
                
                if not is_valid:
                    result.add_issue(ValidationIssue(
                        field_name=field_name,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        message=rule.error_message or f"Validation failed for field '{field_name}'",
                        value=field_value,
                        expected=self._get_expected_format(rule)
                    ))
                    
        except Exception as e:
            logger.error(f"Error applying validation rule {rule.rule_type}: {e}")
            result.add_issue(ValidationIssue(
                field_name=rule.field_name,
                rule_type=rule.rule_type,
                severity=ValidationSeverity.ERROR,
                message=f"Rule application error: {str(e)}",
                value=data.get(rule.field_name)
            ))
    
    async def _validate_field(self, value: Any, rule: ValidationRule) -> bool:
        """Validate a single field value against a rule."""
        try:
            # Handle None values
            if value is None:
                return not rule.required
            
            # Apply validation based on rule type
            if rule.rule_type == "string_length":
                return self._validate_string_length(value, rule.parameters)
            elif rule.rule_type == "numeric_range":
                return self._validate_numeric_range(value, rule.parameters)
            elif rule.rule_type == "binary_data":
                return self._validate_binary_data(value, rule.parameters)
            elif rule.rule_type == "alphanumeric":
                return self._validate_alphanumeric(value, rule.parameters)
            elif rule.rule_type == "date":
                return self._validate_date(value)
            elif rule.rule_type == "future_date":
                return self._validate_future_date(value)
            elif rule.rule_type == "currency":
                return self._validate_currency(value)
            elif rule.rule_type == "json_object":
                return self._validate_json_object(value)
            elif rule.rule_type == "enum":
                return self._validate_enum(value, rule.parameters)
            elif rule.rule_type == "document_list":
                return self._validate_document_list(value)
            elif rule.rule_type == "xss_protection":
                return self._validate_xss_protection(value)
            elif rule.rule_type == "sql_injection_protection":
                return self._validate_sql_injection_protection(value)
            elif rule.rule_type == "command_injection_protection":
                return self._validate_command_injection_protection(value)
            elif rule.custom_validator:
                return rule.custom_validator(value)
            elif rule.rule_type in self._custom_validators:
                return self._custom_validators[rule.rule_type](value)
            else:
                logger.warning(f"Unknown validation rule type: {rule.rule_type}")
                return True
                
        except Exception as e:
            logger.error(f"Field validation error for rule {rule.rule_type}: {e}")
            return False
    
    def _validate_string_length(self, value: Any, params: Dict[str, Any]) -> bool:
        """Validate string length."""
        if not isinstance(value, str):
            return False
        
        length = len(value)
        min_length = params.get('min_length', 0)
        max_length = params.get('max_length', float('inf'))
        
        return min_length <= length <= max_length
    
    def _validate_numeric_range(self, value: Any, params: Dict[str, Any]) -> bool:
        """Validate numeric range."""
        try:
            num_value = float(value)
            min_value = params.get('min_value', float('-inf'))
            max_value = params.get('max_value', float('inf'))
            
            return min_value <= num_value <= max_value
        except (ValueError, TypeError):
            return False
    
    def _validate_binary_data(self, value: Any, params: Dict[str, Any]) -> bool:
        """Validate binary data size."""
        if not isinstance(value, (bytes, bytearray)):
            return False
        
        size = len(value)
        min_size = params.get('min_size', 0)
        max_size = params.get('max_size', float('inf'))
        
        return min_size <= size <= max_size
    
    def _validate_alphanumeric(self, value: Any, params: Dict[str, Any]) -> bool:
        """Validate alphanumeric string."""
        if not isinstance(value, str):
            return False
        
        if not value.replace('_', '').replace('-', '').isalnum():
            return False
        
        length = len(value)
        min_length = params.get('min_length', 0)
        max_length = params.get('max_length', float('inf'))
        
        return min_length <= length <= max_length
    
    def _validate_date(self, value: Any) -> bool:
        """Validate date format."""
        try:
            if isinstance(value, str):
                datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, (datetime, date)):
                pass  # Already a date object
            else:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_future_date(self, value: Any) -> bool:
        """Validate future date."""
        try:
            if isinstance(value, str):
                date_obj = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, datetime):
                date_obj = value
            elif isinstance(value, date):
                date_obj = datetime.combine(value, datetime.min.time())
            else:
                return False
            
            return date_obj > datetime.utcnow()
        except (ValueError, TypeError):
            return False
    
    def _validate_currency(self, value: Any) -> bool:
        """Validate currency value."""
        try:
            if isinstance(value, str):
                # Remove currency symbols and commas
                clean_value = re.sub(r'[₹$,\s]', '', value)
                Decimal(clean_value)
            elif isinstance(value, (int, float, Decimal)):
                pass  # Already numeric
            else:
                return False
            return True
        except (ValueError, InvalidOperation):
            return False
    
    def _validate_json_object(self, value: Any) -> bool:
        """Validate JSON object."""
        try:
            if isinstance(value, str):
                json.loads(value)
            elif isinstance(value, dict):
                json.dumps(value)  # Ensure it's serializable
            else:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_enum(self, value: Any, params: Dict[str, Any]) -> bool:
        """Validate enum value."""
        allowed_values = params.get('allowed_values', [])
        return value in allowed_values
    
    def _validate_document_list(self, value: Any) -> bool:
        """Validate document list."""
        if not isinstance(value, list):
            return False
        
        for doc in value:
            if not isinstance(doc, dict):
                return False
            if 'document_type' not in doc or 'document_number' not in doc:
                return False
        
        return True
    
    def _validate_xss_protection(self, value: Any) -> bool:
        """Validate against XSS attacks."""
        if not isinstance(value, str):
            return True
        
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>',
            r'<link[^>]*>',
            r'<meta[^>]*>',
            r'<style[^>]*>.*?</style>'
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, value, re.IGNORECASE | re.DOTALL):
                return False
        
        return True
    
    def _validate_sql_injection_protection(self, value: Any) -> bool:
        """Validate against SQL injection attacks."""
        if not isinstance(value, str):
            return True
        
        sql_patterns = [
            r'\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b',
            r'(--|#|/\*|\*/)',
            r'\b(OR|AND)\s+\d+\s*=\s*\d+',
            r"'\s*(OR|AND)\s*'\w*'\s*=\s*'\w*'",
            r'\bUNION\s+SELECT\b',
            r'\bINTO\s+OUTFILE\b',
            r'\bLOAD_FILE\b'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        return True
    
    def _validate_command_injection_protection(self, value: Any) -> bool:
        """Validate against command injection attacks."""
        if not isinstance(value, str):
            return True
        
        command_patterns = [
            r'[;&|`$]',
            r'\b(rm|del|format|shutdown|reboot)\b',
            r'\b(cat|type|more|less)\b',
            r'\b(wget|curl|nc|netcat)\b',
            r'\b(chmod|chown|sudo)\b'
        ]
        
        for pattern in command_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        return True
    
    async def _apply_security_validations(self, data: Dict[str, Any], 
                                        result: ValidationResult):
        """Apply additional security validations."""
        # Check for suspicious patterns in all string fields
        for field_name, field_value in data.items():
            if isinstance(field_value, str):
                # Check for encoded payloads
                if self._contains_encoded_payload(field_value):
                    result.add_issue(ValidationIssue(
                        field_name=field_name,
                        rule_type="encoded_payload_detection",
                        severity=ValidationSeverity.CRITICAL,
                        message="Field contains potentially encoded malicious payload",
                        value=field_value
                    ))
                
                # Check for excessive length (potential DoS)
                if len(field_value) > 10000:  # 10KB limit
                    result.add_issue(ValidationIssue(
                        field_name=field_name,
                        rule_type="excessive_length",
                        severity=ValidationSeverity.WARNING,
                        message="Field value exceeds recommended length limit",
                        value=f"Length: {len(field_value)} characters"
                    ))
    
    def _contains_encoded_payload(self, value: str) -> bool:
        """Check if string contains encoded malicious payload."""
        # Check for base64 encoded scripts
        try:
            import base64
            decoded = base64.b64decode(value, validate=True).decode('utf-8', errors='ignore')
            if any(pattern in decoded.lower() for pattern in ['script', 'javascript', 'eval']):
                return True
        except:
            pass
        
        # Check for URL encoded scripts
        try:
            from urllib.parse import unquote
            decoded = unquote(value)
            if any(pattern in decoded.lower() for pattern in ['script', 'javascript', 'eval']):
                return True
        except:
            pass
        
        return False
    
    def _get_expected_format(self, rule: ValidationRule) -> str:
        """Get expected format description for a validation rule."""
        if rule.rule_type == "string_length":
            params = rule.parameters
            min_len = params.get('min_length', 0)
            max_len = params.get('max_length', 'unlimited')
            return f"String length between {min_len} and {max_len} characters"
        elif rule.rule_type == "numeric_range":
            params = rule.parameters
            min_val = params.get('min_value', 'unlimited')
            max_val = params.get('max_value', 'unlimited')
            return f"Numeric value between {min_val} and {max_val}"
        elif rule.rule_type == "indian_phone":
            return "Indian phone number format (+91XXXXXXXXXX or XXXXXXXXXX)"
        elif rule.rule_type == "email":
            return "Valid email address format"
        elif rule.rule_type == "aadhaar_number":
            return "12-digit Aadhaar number"
        elif rule.rule_type == "pan_number":
            return "PAN number format (ABCDE1234F)"
        else:
            return f"Valid {rule.rule_type} format"
    
    def _calculate_data_hash(self, data: Dict[str, Any]) -> str:
        """Calculate hash for data integrity checking."""
        try:
            # Sort keys for consistent hashing
            data_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating data hash: {e}")
            return ""
    
    async def verify_data_integrity(self, data: Dict[str, Any], 
                                  expected_hash: str,
                                  user_id: Optional[str] = None) -> bool:
        """
        Verify data integrity using hash comparison.
        
        Args:
            data: Data to verify
            expected_hash: Expected hash value
            user_id: User identifier for audit logging
            
        Returns:
            True if data integrity is verified
        """
        try:
            calculated_hash = self._calculate_data_hash(data)
            is_valid = calculated_hash == expected_hash
            
            # Log integrity check
            self.security_manager.log_security_event(
                SecurityEventType.DATA_ACCESS if is_valid else SecurityEventType.SECURITY_VIOLATION,
                "data_validation_service",
                "verify_integrity",
                is_valid,
                user_id=user_id,
                details={
                    'expected_hash': expected_hash[:16] + "...",
                    'calculated_hash': calculated_hash[:16] + "...",
                    'data_size': len(json.dumps(data, default=str))
                },
                security_level=SecurityLevel.HIGH if not is_valid else SecurityLevel.MEDIUM,
                data_classification="integrity_check"
            )
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Data integrity verification failed: {e}")
            return False
    
    def get_validation_rules(self, data_type: DataType) -> List[ValidationRule]:
        """Get validation rules for a specific data type."""
        return self._validation_rules.get(data_type, [])
    
    def add_custom_validator(self, name: str, validator_func: Callable) -> None:
        """Add a custom validation function."""
        self._custom_validators[name] = validator_func
        logger.info(f"Custom validator '{name}' added")
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation service statistics."""
        return {
            'supported_data_types': len(self._validation_rules),
            'total_validation_rules': sum(len(rules) for rules in self._validation_rules.values()),
            'custom_validators': len(self._custom_validators),
            'data_types': [dt.value for dt in self._validation_rules.keys()]
        }