"""
Grievance validation system.

This module provides real-time validation for grievance information
during the conversational filing process.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, date

from .models import (
    GrievanceRecord, GrievanceDetails, ContactInformation,
    GrievanceValidationResult, ValidationError, GrievanceType
)
from ..core.exceptions import ValidationError as CoreValidationError

logger = logging.getLogger(__name__)


class GrievanceValidator:
    """
    Real-time validator for grievance information.
    
    Provides validation for all aspects of grievance filing including
    required fields, format validation, and business rules.
    """
    
    def __init__(self):
        """Initialize the grievance validator."""
        self._validation_rules = self._load_validation_rules()
        self._required_fields = self._load_required_fields()
        logger.info("GrievanceValidator initialized")
    
    def validate_grievance(self, grievance: GrievanceRecord) -> GrievanceValidationResult:
        """
        Validate a complete grievance record.
        
        Args:
            grievance: Grievance record to validate
            
        Returns:
            GrievanceValidationResult with validation details
        """
        errors = []
        warnings = []
        missing_fields = []
        
        try:
            # Validate basic information
            errors.extend(self._validate_basic_info(grievance))
            
            # Validate grievance details
            if grievance.details:
                errors.extend(self._validate_grievance_details(grievance.details))
            else:
                missing_fields.append('grievance_details')
            
            # Validate contact information
            if grievance.contact_info:
                contact_errors, contact_warnings = self._validate_contact_info(grievance.contact_info)
                errors.extend(contact_errors)
                warnings.extend(contact_warnings)
            else:
                missing_fields.append('contact_information')
            
            # Validate documents
            doc_errors, doc_warnings = self._validate_documents(grievance.documents, grievance.details)
            errors.extend(doc_errors)
            warnings.extend(doc_warnings)
            
            # Check for missing required fields
            missing_fields.extend(self._check_required_fields(grievance))
            
            # Calculate completion percentage
            completion_percentage = self._calculate_completion_percentage(grievance, missing_fields)
            
            is_valid = len(errors) == 0 and len(missing_fields) == 0
            
            result = GrievanceValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                missing_required_fields=missing_fields,
                completion_percentage=completion_percentage
            )
            
            logger.info("Grievance validation completed: valid=%s, errors=%d, warnings=%d", 
                       is_valid, len(errors), len(warnings))
            
            return result
            
        except Exception as e:
            logger.error("Grievance validation failed: %s", str(e))
            return GrievanceValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    field="general",
                    message=f"Validation failed: {str(e)}",
                    severity="error"
                )],
                completion_percentage=0.0
            )
    
    def validate_field(self, field_name: str, value: Any, context: Optional[Dict[str, Any]] = None) -> List[ValidationError]:
        """
        Validate a specific field value.
        
        Args:
            field_name: Name of the field to validate
            value: Value to validate
            context: Optional context for validation
            
        Returns:
            List of validation errors
        """
        errors = []
        
        try:
            if field_name == 'phone_number':
                errors.extend(self._validate_phone_number(value))
            elif field_name == 'email':
                errors.extend(self._validate_email(value))
            elif field_name == 'problem_description':
                errors.extend(self._validate_problem_description(value))
            elif field_name == 'reference_number':
                errors.extend(self._validate_reference_number(value))
            elif field_name == 'age':
                errors.extend(self._validate_age(value))
            elif field_name == 'address':
                errors.extend(self._validate_address(value))
            # Add more field validations as needed
            
            return errors
            
        except Exception as e:
            logger.error("Field validation failed for %s: %s", field_name, str(e))
            return [ValidationError(
                field=field_name,
                message=f"Validation error: {str(e)}",
                severity="error"
            )]
    
    def _validate_basic_info(self, grievance: GrievanceRecord) -> List[ValidationError]:
        """Validate basic grievance information."""
        errors = []
        
        # Validate session ID
        if not grievance.session_id:
            errors.append(ValidationError(
                field="session_id",
                message="Session ID is required",
                severity="error"
            ))
        
        # Validate language
        if grievance.language not in ['hi', 'en', 'ta', 'te', 'bn', 'mr', 'gu', 'kn', 'ml', 'pa']:
            errors.append(ValidationError(
                field="language",
                message="Unsupported language",
                severity="warning",
                suggestion="Supported languages: Hindi, English, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi"
            ))
        
        return errors
    
    def _validate_grievance_details(self, details: GrievanceDetails) -> List[ValidationError]:
        """Validate grievance details."""
        errors = []
        
        # Validate problem description
        errors.extend(self._validate_problem_description(details.problem_description))
        
        # Validate grievance type
        if not isinstance(details.grievance_type, GrievanceType):
            errors.append(ValidationError(
                field="grievance_type",
                message="Invalid grievance type",
                severity="error"
            ))
        
        # Validate incident date
        if details.incident_date and details.incident_date > date.today():
            errors.append(ValidationError(
                field="incident_date",
                message="Incident date cannot be in the future",
                severity="error"
            ))
        
        # Validate location if provided
        if details.location and len(details.location.strip()) < 3:
            errors.append(ValidationError(
                field="location",
                message="Location must be at least 3 characters long",
                severity="warning",
                suggestion="Please provide a more specific location"
            ))
        
        return errors
    
    def _validate_contact_info(self, contact_info: ContactInformation) -> tuple[List[ValidationError], List[ValidationError]]:
        """Validate contact information."""
        errors = []
        warnings = []
        
        # At least one contact method should be provided
        has_phone = contact_info.phone_number and len(contact_info.phone_number.strip()) > 0
        has_email = contact_info.email and len(contact_info.email.strip()) > 0
        
        if not has_phone and not has_email:
            errors.append(ValidationError(
                field="contact_info",
                message="At least one contact method (phone or email) is required",
                severity="error"
            ))
        
        # Validate phone number if provided
        if has_phone:
            errors.extend(self._validate_phone_number(contact_info.phone_number))
        
        # Validate email if provided
        if has_email:
            errors.extend(self._validate_email(contact_info.email))
        
        # Validate address if provided
        if contact_info.address:
            errors.extend(self._validate_address(contact_info.address))
        
        # Validate preferred contact method
        valid_methods = ['phone', 'email', 'sms']
        if contact_info.preferred_contact_method not in valid_methods:
            warnings.append(ValidationError(
                field="preferred_contact_method",
                message="Invalid preferred contact method",
                severity="warning",
                suggestion=f"Valid methods: {', '.join(valid_methods)}"
            ))
        
        return errors, warnings
    
    def _validate_documents(self, documents: List, details: Optional[GrievanceDetails]) -> tuple[List[ValidationError], List[ValidationError]]:
        """Validate document information."""
        errors = []
        warnings = []
        
        # Check if required documents are available for specific grievance types
        if details and details.grievance_type:
            required_docs = self._get_required_documents(details.grievance_type)
            available_doc_types = [doc.document_type for doc in documents if doc.is_available]
            
            for required_doc in required_docs:
                if required_doc not in available_doc_types:
                    warnings.append(ValidationError(
                        field="documents",
                        message=f"Required document '{required_doc}' is not available",
                        severity="warning",
                        suggestion=f"Please arrange for {required_doc} to strengthen your grievance"
                    ))
        
        # Validate individual documents
        for doc in documents:
            if doc.document_number and len(doc.document_number.strip()) < 3:
                errors.append(ValidationError(
                    field="document_number",
                    message=f"Document number for {doc.document_type} is too short",
                    severity="error"
                ))
        
        return errors, warnings
    
    def _validate_phone_number(self, phone: str) -> List[ValidationError]:
        """Validate phone number format."""
        errors = []
        
        if not phone or not phone.strip():
            return errors  # Empty phone is handled at higher level
        
        # Clean phone number
        clean_phone = re.sub(r'[\s\-\(\)]', '', phone.strip())
        
        # Indian phone number patterns
        patterns = [
            r'^(\+91|91)?[6-9]\d{9}$',  # Mobile numbers
            r'^(\+91|91)?\d{2,4}\d{6,8}$',  # Landline numbers
        ]
        
        is_valid = any(re.match(pattern, clean_phone) for pattern in patterns)
        
        # Additional validation for mobile numbers
        if len(clean_phone) == 11:
            # 11 digit numbers are invalid (too long)
            is_valid = False
        elif len(clean_phone) == 10:
            # Must start with 6, 7, 8, or 9 for mobile
            if not clean_phone[0] in '6789':
                is_valid = False
        elif len(clean_phone) == 9:
            # 9 digit numbers are invalid
            is_valid = False
        
        if not is_valid:
            errors.append(ValidationError(
                field="phone_number",
                message="Invalid phone number format",
                severity="error",
                suggestion="Please provide a valid Indian phone number (10 digits for mobile, with optional +91 prefix)"
            ))
        
        return errors
    
    def _validate_email(self, email: str) -> List[ValidationError]:
        """Validate email address format."""
        errors = []
        
        if not email or not email.strip():
            return errors  # Empty email is handled at higher level
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email.strip()):
            errors.append(ValidationError(
                field="email",
                message="Invalid email address format",
                severity="error",
                suggestion="Please provide a valid email address (e.g., user@example.com)"
            ))
        
        return errors
    
    def _validate_problem_description(self, description: str) -> List[ValidationError]:
        """Validate problem description."""
        errors = []
        
        if not description or not description.strip():
            errors.append(ValidationError(
                field="problem_description",
                message="Problem description is required",
                severity="error"
            ))
            return errors
        
        description = description.strip()
        
        # Minimum length check
        if len(description) < 10:
            errors.append(ValidationError(
                field="problem_description",
                message="Problem description is too short",
                severity="error",
                suggestion="Please provide at least 10 characters describing your problem in detail"
            ))
        
        # Maximum length check
        if len(description) > 2000:
            errors.append(ValidationError(
                field="problem_description",
                message="Problem description is too long",
                severity="warning",
                suggestion="Please keep the description under 2000 characters"
            ))
        
        # Check for meaningful content (not just repeated characters)
        if len(set(description.lower())) < 5:
            errors.append(ValidationError(
                field="problem_description",
                message="Problem description appears to lack meaningful content",
                severity="warning",
                suggestion="Please provide a detailed description of your specific problem"
            ))
        
        return errors
    
    def _validate_reference_number(self, ref_number: str) -> List[ValidationError]:
        """Validate reference number format."""
        errors = []
        
        if not ref_number or not ref_number.strip():
            return errors  # Empty reference is handled at higher level
        
        ref_number = ref_number.strip().upper()
        
        # Reference number should be alphanumeric and at least 6 characters
        if not re.match(r'^[A-Z0-9]{6,}$', ref_number):
            errors.append(ValidationError(
                field="reference_number",
                message="Invalid reference number format",
                severity="error",
                suggestion="Reference number should be at least 6 alphanumeric characters"
            ))
        
        return errors
    
    def _validate_age(self, age: Any) -> List[ValidationError]:
        """Validate age value."""
        errors = []
        
        try:
            age_int = int(age)
            if age_int < 0 or age_int > 120:
                errors.append(ValidationError(
                    field="age",
                    message="Age must be between 0 and 120",
                    severity="error"
                ))
        except (ValueError, TypeError):
            errors.append(ValidationError(
                field="age",
                message="Age must be a valid number",
                severity="error"
            ))
        
        return errors
    
    def _validate_address(self, address: str) -> List[ValidationError]:
        """Validate address format."""
        errors = []
        
        if not address or not address.strip():
            return errors  # Empty address is handled at higher level
        
        address = address.strip()
        
        # Minimum length check
        if len(address) < 10:
            errors.append(ValidationError(
                field="address",
                message="Address is too short",
                severity="warning",
                suggestion="Please provide a complete address with locality, city, and state"
            ))
        
        # Check for basic address components
        has_numbers = bool(re.search(r'\d', address))
        if not has_numbers:
            errors.append(ValidationError(
                field="address",
                message="Address should include house/building number",
                severity="warning",
                suggestion="Please include house number or building details"
            ))
        
        return errors
    
    def _check_required_fields(self, grievance: GrievanceRecord) -> List[str]:
        """Check for missing required fields."""
        missing_fields = []
        
        # Basic required fields
        if not grievance.details:
            missing_fields.append('problem_description')
        elif not grievance.details.problem_description or not grievance.details.problem_description.strip():
            missing_fields.append('problem_description')
        
        # Contact information
        if not grievance.contact_info:
            missing_fields.append('contact_information')
        else:
            has_phone = grievance.contact_info.phone_number and len(grievance.contact_info.phone_number.strip()) > 0
            has_email = grievance.contact_info.email and len(grievance.contact_info.email.strip()) > 0
            
            if not has_phone and not has_email:
                missing_fields.append('contact_method')
        
        return missing_fields
    
    def _calculate_completion_percentage(self, grievance: GrievanceRecord, missing_fields: List[str]) -> float:
        """Calculate completion percentage of the grievance."""
        total_fields = 10  # Total important fields
        completed_fields = 0
        
        # Check each important field
        if grievance.details and grievance.details.problem_description:
            completed_fields += 2  # Problem description is worth 2 points
        
        if grievance.details and grievance.details.grievance_type:
            completed_fields += 1
        
        if grievance.contact_info and (grievance.contact_info.phone_number or grievance.contact_info.email):
            completed_fields += 2  # Contact info is worth 2 points
        
        if grievance.contact_info and grievance.contact_info.phone_number:
            completed_fields += 1
        
        if grievance.contact_info and grievance.contact_info.email:
            completed_fields += 1
        
        if grievance.contact_info and grievance.contact_info.address:
            completed_fields += 1
        
        if grievance.details and grievance.details.location:
            completed_fields += 1
        
        if grievance.details and grievance.details.department:
            completed_fields += 1
        
        if grievance.details and grievance.details.incident_date:
            completed_fields += 1
        
        if grievance.documents:
            completed_fields += 1
        
        return (completed_fields / total_fields) * 100.0
    
    def _get_required_documents(self, grievance_type: GrievanceType) -> List[str]:
        """Get required documents for a specific grievance type."""
        document_requirements = {
            GrievanceType.PENSION_ISSUE: ['pension_card', 'bank_passbook', 'identity_proof'],
            GrievanceType.RATION_CARD_ISSUE: ['ration_card', 'address_proof', 'identity_proof'],
            GrievanceType.CERTIFICATE_DELAY: ['application_receipt', 'identity_proof'],
            GrievanceType.SUBSIDY_DELAY: ['application_receipt', 'bank_details', 'identity_proof'],
            GrievanceType.CORRUPTION_COMPLAINT: ['evidence_documents', 'identity_proof'],
            GrievanceType.SERVICE_DENIAL: ['application_receipt', 'correspondence', 'identity_proof'],
            GrievanceType.DOCUMENT_ISSUE: ['existing_document', 'identity_proof'],
            GrievanceType.SCHEME_RELATED: ['scheme_documents', 'identity_proof'],
            GrievanceType.INFRASTRUCTURE: ['location_proof', 'photographs'],
            GrievanceType.OTHER: ['identity_proof']
        }
        
        return document_requirements.get(grievance_type, ['identity_proof'])
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load validation rules configuration."""
        # This could be loaded from configuration files
        return {
            'phone_number': {
                'required': True,
                'patterns': [r'^(\+91|91)?[6-9]\d{9}$'],
                'min_length': 10,
                'max_length': 13
            },
            'email': {
                'required': False,
                'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            },
            'problem_description': {
                'required': True,
                'min_length': 10,
                'max_length': 2000
            }
        }
    
    def _load_required_fields(self) -> List[str]:
        """Load list of required fields."""
        return [
            'problem_description',
            'contact_information',
            'grievance_type'
        ]