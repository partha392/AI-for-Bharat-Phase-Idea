"""
Scheme validation and data quality management.

This module provides comprehensive validation for government scheme data,
ensuring data quality and consistency across all scheme information.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
import re
from decimal import Decimal

from .models import GovernmentScheme, SchemeCategory, SchemeStatus, EligibilityCriteria, SchemeBenefits, ApplicationProcess
from ..core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class SchemeValidator:
    """
    Comprehensive validator for government scheme data.
    
    Validates scheme information for completeness, consistency,
    and compliance with data quality standards.
    """
    
    # Valid Indian state codes
    VALID_STATE_CODES = {
        'AP', 'AR', 'AS', 'BR', 'CG', 'GA', 'GJ', 'HR', 'HP', 'JK', 'JH',
        'KA', 'KL', 'MP', 'MH', 'MN', 'ML', 'MZ', 'NL', 'OR', 'PB', 'RJ',
        'SK', 'TN', 'TS', 'TR', 'UP', 'UK', 'WB', 'AN', 'CH', 'DN', 'DD',
        'DL', 'LD', 'PY'
    }
    
    # Required fields for basic scheme validation
    REQUIRED_FIELDS = [
        'scheme_id', 'name', 'department', 'category', 'description',
        'eligibility_criteria', 'benefits', 'application_process'
    ]
    
    # Valid document types for application process
    VALID_DOCUMENT_TYPES = {
        'aadhaar_card', 'pan_card', 'voter_id', 'driving_license', 'passport',
        'income_certificate', 'caste_certificate', 'domicile_certificate',
        'bank_account_details', 'land_documents', 'educational_certificates',
        'employment_certificate', 'disability_certificate', 'age_proof',
        'address_proof', 'photograph', 'signature', 'thumb_impression'
    }
    
    def __init__(self):
        """Initialize the scheme validator."""
        self.validation_rules = self._load_validation_rules()
    
    def validate_scheme(self, scheme: GovernmentScheme) -> Tuple[bool, List[str]]:
        """
        Validate a complete government scheme.
        
        Args:
            scheme: The government scheme to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Basic field validation
            errors.extend(self._validate_basic_fields(scheme))
            
            # Identifier validation
            errors.extend(self._validate_identifiers(scheme))
            
            # Content validation
            errors.extend(self._validate_content(scheme))
            
            # Eligibility criteria validation
            errors.extend(self._validate_eligibility_criteria(scheme.eligibility_criteria))
            
            # Benefits validation
            errors.extend(self._validate_benefits(scheme.benefits))
            
            # Application process validation
            errors.extend(self._validate_application_process(scheme.application_process))
            
            # Geographic targeting validation
            errors.extend(self._validate_geographic_targeting(scheme))
            
            # Date validation
            errors.extend(self._validate_dates(scheme))
            
            # Numeric validation
            errors.extend(self._validate_numeric_fields(scheme))
            
            # Metadata validation
            errors.extend(self._validate_metadata(scheme))
            
        except Exception as e:
            logger.error(f"Unexpected error during scheme validation: {str(e)}")
            errors.append(f"Validation error: {str(e)}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_scheme_update(self, old_scheme: GovernmentScheme, new_scheme: GovernmentScheme) -> Tuple[bool, List[str], List[str]]:
        """
        Validate a scheme update and detect changes.
        
        Args:
            old_scheme: The existing scheme
            new_scheme: The updated scheme
            
        Returns:
            Tuple of (is_valid, list_of_errors, list_of_changes)
        """
        # First validate the new scheme
        is_valid, errors = self.validate_scheme(new_scheme)
        
        # Detect changes
        changes = self._detect_changes(old_scheme, new_scheme)
        
        # Validate update-specific rules
        update_errors = self._validate_update_rules(old_scheme, new_scheme, changes)
        errors.extend(update_errors)
        
        is_valid = len(errors) == 0
        return is_valid, errors, changes
    
    def _validate_basic_fields(self, scheme: GovernmentScheme) -> List[str]:
        """Validate basic required fields."""
        errors = []
        
        for field in self.REQUIRED_FIELDS:
            if not hasattr(scheme, field) or not getattr(scheme, field):
                errors.append(f"Required field '{field}' is missing or empty")
        
        return errors
    
    def _validate_identifiers(self, scheme: GovernmentScheme) -> List[str]:
        """Validate scheme identifiers."""
        errors = []
        
        # Scheme ID validation
        if not scheme.scheme_id:
            errors.append("Scheme ID is required")
        elif not re.match(r'^[a-zA-Z0-9\-_]+$', scheme.scheme_id):
            errors.append("Scheme ID must contain only alphanumeric characters, hyphens, and underscores")
        elif len(scheme.scheme_id) > 50:
            errors.append("Scheme ID must be 50 characters or less")
        
        # Name validation
        if not scheme.name:
            errors.append("Scheme name is required")
        elif len(scheme.name) > 500:
            errors.append("Scheme name must be 500 characters or less")
        
        return errors
    
    def _validate_content(self, scheme: GovernmentScheme) -> List[str]:
        """Validate content fields."""
        errors = []
        
        # Description validation
        if not scheme.description:
            errors.append("Scheme description is required")
        elif len(scheme.description) < 50:
            errors.append("Scheme description must be at least 50 characters")
        elif len(scheme.description) > 5000:
            errors.append("Scheme description must be 5000 characters or less")
        
        # Department validation
        if not scheme.department:
            errors.append("Department is required")
        elif len(scheme.department) > 200:
            errors.append("Department name must be 200 characters or less")
        
        # Ministry validation
        if scheme.ministry and len(scheme.ministry) > 200:
            errors.append("Ministry name must be 200 characters or less")
        
        # Category validation
        if not isinstance(scheme.category, SchemeCategory):
            errors.append("Invalid scheme category")
        
        return errors
    
    def _validate_eligibility_criteria(self, criteria: EligibilityCriteria) -> List[str]:
        """Validate eligibility criteria."""
        errors = []
        
        # Income limit validation
        if criteria.income_limit is not None:
            if criteria.income_limit < 0:
                errors.append("Income limit cannot be negative")
            elif criteria.income_limit > 10000000:  # 1 crore
                errors.append("Income limit seems unreasonably high")
        
        # Age validation
        if criteria.age_min is not None:
            if criteria.age_min < 0 or criteria.age_min > 120:
                errors.append("Minimum age must be between 0 and 120")
        
        if criteria.age_max is not None:
            if criteria.age_max < 0 or criteria.age_max > 120:
                errors.append("Maximum age must be between 0 and 120")
        
        if criteria.age_min is not None and criteria.age_max is not None:
            if criteria.age_min > criteria.age_max:
                errors.append("Minimum age cannot be greater than maximum age")
        
        # Location type validation
        if criteria.location_type and criteria.location_type not in ['rural', 'urban', 'both']:
            errors.append("Location type must be 'rural', 'urban', or 'both'")
        
        # Gender validation
        if criteria.gender and criteria.gender not in ['male', 'female', 'transgender', 'any']:
            errors.append("Gender must be 'male', 'female', 'transgender', or 'any'")
        
        return errors
    
    def _validate_benefits(self, benefits: SchemeBenefits) -> List[str]:
        """Validate scheme benefits."""
        errors = []
        
        # Financial assistance validation
        if benefits.financial_assistance is not None:
            if benefits.financial_assistance < 0:
                errors.append("Financial assistance cannot be negative")
            elif benefits.financial_assistance > 100000000:  # 10 crore
                errors.append("Financial assistance amount seems unreasonably high")
        
        # Subsidy percentage validation
        if benefits.subsidy_percentage is not None:
            if benefits.subsidy_percentage < 0 or benefits.subsidy_percentage > 100:
                errors.append("Subsidy percentage must be between 0 and 100")
        
        # Loan amount validation
        if benefits.loan_amount is not None:
            if benefits.loan_amount < 0:
                errors.append("Loan amount cannot be negative")
        
        # Interest rate validation
        if benefits.interest_rate is not None:
            if benefits.interest_rate < 0 or benefits.interest_rate > 50:
                errors.append("Interest rate must be between 0 and 50 percent")
        
        # Insurance coverage validation
        if benefits.insurance_coverage is not None:
            if benefits.insurance_coverage < 0:
                errors.append("Insurance coverage cannot be negative")
        
        # Description validation
        if not benefits.description:
            errors.append("Benefits description is required")
        elif len(benefits.description) > 1000:
            errors.append("Benefits description must be 1000 characters or less")
        
        return errors
    
    def _validate_application_process(self, process: ApplicationProcess) -> List[str]:
        """Validate application process."""
        errors = []
        
        # Steps validation
        if not process.steps:
            errors.append("Application process steps are required")
        elif len(process.steps) == 0:
            errors.append("At least one application step is required")
        elif len(process.steps) > 20:
            errors.append("Too many application steps (maximum 20)")
        
        # Required documents validation
        if not process.required_documents:
            errors.append("Required documents list is required")
        else:
            for doc in process.required_documents:
                if doc not in self.VALID_DOCUMENT_TYPES:
                    errors.append(f"Invalid document type: {doc}")
        
        # Application fee validation
        if process.application_fee is not None:
            if process.application_fee < 0:
                errors.append("Application fee cannot be negative")
            elif process.application_fee > 10000:
                errors.append("Application fee seems unreasonably high")
        
        # Processing time validation
        if process.processing_time_days is not None:
            if process.processing_time_days < 0:
                errors.append("Processing time cannot be negative")
            elif process.processing_time_days > 365:
                errors.append("Processing time seems unreasonably long (>1 year)")
        
        # Application mode validation
        if process.application_mode:
            valid_modes = {'online', 'offline', 'both'}
            for mode in process.application_mode:
                if mode not in valid_modes:
                    errors.append(f"Invalid application mode: {mode}")
        
        return errors
    
    def _validate_geographic_targeting(self, scheme: GovernmentScheme) -> List[str]:
        """Validate geographic targeting."""
        errors = []
        
        # State codes validation
        if scheme.target_states:
            for state in scheme.target_states:
                if state not in self.VALID_STATE_CODES:
                    errors.append(f"Invalid state code: {state}")
        
        return errors
    
    def _validate_dates(self, scheme: GovernmentScheme) -> List[str]:
        """Validate date fields."""
        errors = []
        
        # Launch date validation
        if scheme.launch_date:
            if scheme.launch_date > date.today():
                # Allow future launch dates but warn
                pass
        
        # End date validation
        if scheme.end_date:
            if scheme.launch_date and scheme.end_date < scheme.launch_date:
                errors.append("End date cannot be before launch date")
        
        return errors
    
    def _validate_numeric_fields(self, scheme: GovernmentScheme) -> List[str]:
        """Validate numeric fields."""
        errors = []
        
        # Budget validation
        if scheme.budget_allocated is not None:
            if scheme.budget_allocated < 0:
                errors.append("Budget allocated cannot be negative")
        
        # Beneficiaries validation
        if scheme.beneficiaries_target is not None:
            if scheme.beneficiaries_target < 0:
                errors.append("Target beneficiaries cannot be negative")
        
        if scheme.beneficiaries_current < 0:
            errors.append("Current beneficiaries cannot be negative")
        
        if (scheme.beneficiaries_target is not None and 
            scheme.beneficiaries_current > scheme.beneficiaries_target):
            errors.append("Current beneficiaries cannot exceed target")
        
        # Processing days validation
        if scheme.average_processing_days is not None:
            if scheme.average_processing_days < 0:
                errors.append("Average processing days cannot be negative")
        
        return errors
    
    def _validate_metadata(self, scheme: GovernmentScheme) -> List[str]:
        """Validate metadata fields."""
        errors = []
        
        # Version validation
        if scheme.metadata.version < 1:
            errors.append("Version must be at least 1")
        
        # Popularity score validation
        if scheme.metadata.popularity_score < 0 or scheme.metadata.popularity_score > 1:
            errors.append("Popularity score must be between 0 and 1")
        
        # Success rate validation
        if scheme.metadata.success_rate < 0 or scheme.metadata.success_rate > 1:
            errors.append("Success rate must be between 0 and 1")
        
        return errors
    
    def _detect_changes(self, old_scheme: GovernmentScheme, new_scheme: GovernmentScheme) -> List[str]:
        """Detect changes between two scheme versions."""
        changes = []
        
        # Compare basic fields
        if old_scheme.name != new_scheme.name:
            changes.append("name")
        if old_scheme.description != new_scheme.description:
            changes.append("description")
        if old_scheme.department != new_scheme.department:
            changes.append("department")
        if old_scheme.category != new_scheme.category:
            changes.append("category")
        if old_scheme.status != new_scheme.status:
            changes.append("status")
        
        # Compare eligibility criteria
        if old_scheme.eligibility_criteria.__dict__ != new_scheme.eligibility_criteria.__dict__:
            changes.append("eligibility_criteria")
        
        # Compare benefits
        if old_scheme.benefits.__dict__ != new_scheme.benefits.__dict__:
            changes.append("benefits")
        
        # Compare application process
        if old_scheme.application_process.__dict__ != new_scheme.application_process.__dict__:
            changes.append("application_process")
        
        # Compare geographic targeting
        if old_scheme.target_states != new_scheme.target_states:
            changes.append("target_states")
        if old_scheme.target_districts != new_scheme.target_districts:
            changes.append("target_districts")
        
        # Compare dates
        if old_scheme.launch_date != new_scheme.launch_date:
            changes.append("launch_date")
        if old_scheme.end_date != new_scheme.end_date:
            changes.append("end_date")
        
        # Compare numeric fields
        if old_scheme.budget_allocated != new_scheme.budget_allocated:
            changes.append("budget_allocated")
        if old_scheme.beneficiaries_target != new_scheme.beneficiaries_target:
            changes.append("beneficiaries_target")
        
        return changes
    
    def _validate_update_rules(self, old_scheme: GovernmentScheme, new_scheme: GovernmentScheme, changes: List[str]) -> List[str]:
        """Validate update-specific rules."""
        errors = []
        
        # Scheme ID should not change
        if old_scheme.scheme_id != new_scheme.scheme_id:
            errors.append("Scheme ID cannot be changed during update")
        
        # Version should increment
        if new_scheme.metadata.version <= old_scheme.metadata.version:
            errors.append("Version must be incremented during update")
        
        # Status change validation
        if old_scheme.status != new_scheme.status:
            valid_transitions = self._get_valid_status_transitions(old_scheme.status)
            if new_scheme.status not in valid_transitions:
                errors.append(f"Invalid status transition from {old_scheme.status.value} to {new_scheme.status.value}")
        
        return errors
    
    def _get_valid_status_transitions(self, current_status: SchemeStatus) -> List[SchemeStatus]:
        """Get valid status transitions for a given current status."""
        transitions = {
            SchemeStatus.DRAFT: [SchemeStatus.ACTIVE, SchemeStatus.INACTIVE],
            SchemeStatus.ACTIVE: [SchemeStatus.SUSPENDED, SchemeStatus.EXPIRED, SchemeStatus.INACTIVE],
            SchemeStatus.SUSPENDED: [SchemeStatus.ACTIVE, SchemeStatus.EXPIRED, SchemeStatus.INACTIVE],
            SchemeStatus.INACTIVE: [SchemeStatus.ACTIVE],
            SchemeStatus.EXPIRED: []  # No transitions from expired
        }
        return transitions.get(current_status, [])
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load validation rules configuration."""
        # This could be loaded from a configuration file in a real implementation
        return {
            'max_description_length': 5000,
            'min_description_length': 50,
            'max_name_length': 500,
            'max_department_length': 200,
            'max_ministry_length': 200,
            'max_application_steps': 20,
            'max_application_fee': 10000,
            'max_processing_days': 365,
            'max_income_limit': 10000000,
            'max_financial_assistance': 100000000
        }