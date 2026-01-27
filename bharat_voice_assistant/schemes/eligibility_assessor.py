"""
Eligibility assessment system for government schemes.

This module implements rule-based eligibility checking against scheme criteria,
document requirement analysis and checklist generation, and success probability
estimation for the Bharat Voice Assistant.

Requirements: 2.3, 2.5
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import math

from .models import GovernmentScheme, EligibilityCriteria, ApplicationProcess
from .user_profile import UserProfileManager, DemographicInfo, EconomicInfo, LocationInfo
from ..core.exceptions import EligibilityAssessmentError

logger = logging.getLogger(__name__)


class EligibilityStatus(Enum):
    """Eligibility status values."""
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    PARTIALLY_ELIGIBLE = "partially_eligible"
    INSUFFICIENT_DATA = "insufficient_data"


class DocumentStatus(Enum):
    """Document requirement status."""
    REQUIRED = "required"
    OPTIONAL = "optional"
    NOT_APPLICABLE = "not_applicable"
    ALTERNATIVE_AVAILABLE = "alternative_available"


@dataclass
class EligibilityRule:
    """Individual eligibility rule with validation logic."""
    rule_id: str
    name: str
    description: str
    field_name: str
    operator: str  # 'eq', 'ne', 'lt', 'le', 'gt', 'ge', 'in', 'not_in', 'range'
    value: Any
    mandatory: bool = True
    weight: float = 1.0
    error_message: str = ""


@dataclass
class DocumentRequirement:
    """Document requirement with analysis."""
    document_name: str
    document_type: str
    status: DocumentStatus
    description: str
    alternatives: List[str] = field(default_factory=list)
    validity_period: Optional[int] = None  # days
    issuing_authority: Optional[str] = None
    format_requirements: List[str] = field(default_factory=list)
    mandatory: bool = True


@dataclass
class EligibilityAssessment:
    """Complete eligibility assessment result."""
    scheme_id: str
    user_id: str
    overall_status: EligibilityStatus
    eligibility_score: float  # 0.0 to 1.0
    success_probability: float  # 0.0 to 1.0
    
    # Rule-based assessment
    passed_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    missing_data_rules: List[str] = field(default_factory=list)
    
    # Document analysis
    required_documents: List[DocumentRequirement] = field(default_factory=list)
    optional_documents: List[DocumentRequirement] = field(default_factory=list)
    document_checklist: List[Dict[str, Any]] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    
    # Metadata
    assessment_date: datetime = field(default_factory=datetime.now)
    confidence_level: float = 0.0
    data_completeness: float = 0.0


class EligibilityAssessor:
    """
    Rule-based eligibility assessment system.
    
    Provides comprehensive eligibility checking, document requirement analysis,
    and success probability estimation for government schemes.
    """
    
    def __init__(self, user_profile_manager: UserProfileManager):
        """Initialize the eligibility assessor."""
        self.user_profile_manager = user_profile_manager
        
        # Document type mappings
        self.document_types = {
            'identity': ['aadhaar', 'voter_id', 'passport', 'driving_license'],
            'address': ['aadhaar', 'voter_id', 'utility_bill', 'bank_statement'],
            'income': ['income_certificate', 'salary_slip', 'itr', 'bank_statement'],
            'caste': ['caste_certificate', 'community_certificate'],
            'age': ['birth_certificate', 'school_certificate', 'aadhaar'],
            'education': ['education_certificate', 'marksheet', 'degree'],
            'employment': ['employment_certificate', 'salary_slip', 'business_license'],
            'land': ['land_records', 'patta', 'khata'],
            'bank': ['bank_account_details', 'passbook', 'bank_statement'],
            'disability': ['disability_certificate', 'medical_certificate']
        }
        
        logger.info("Initialized EligibilityAssessor")
    
    async def assess_eligibility(self, 
                               user_id: str, 
                               scheme: GovernmentScheme) -> EligibilityAssessment:
        """
        Perform comprehensive eligibility assessment for a user and scheme.
        
        Args:
            user_id: User identifier
            scheme: Government scheme to assess
            
        Returns:
            Complete eligibility assessment
        """
        try:
            # Get user profile
            profile = await self.user_profile_manager.get_profile(user_id)
            if not profile:
                raise EligibilityAssessmentError(f"User profile not found: {user_id}")
            
            assessment = EligibilityAssessment(
                scheme_id=scheme.scheme_id,
                user_id=user_id,
                overall_status=EligibilityStatus.INSUFFICIENT_DATA,
                eligibility_score=0.0,
                success_probability=0.0
            )
            
            # 1. Rule-based eligibility checking
            await self._perform_rule_based_assessment(assessment, profile, scheme)
            
            # 2. Document requirement analysis
            await self._analyze_document_requirements(assessment, profile, scheme)
            
            # 3. Success probability estimation
            await self._estimate_success_probability(assessment, profile, scheme)
            
            # 4. Generate recommendations and next steps
            await self._generate_recommendations(assessment, profile, scheme)
            
            # 5. Calculate confidence and data completeness
            assessment.confidence_level = self._calculate_confidence_level(assessment, profile)
            assessment.data_completeness = self.user_profile_manager.get_profile_completeness(user_id)
            
            logger.info(f"Completed eligibility assessment for user {user_id}, scheme {scheme.scheme_id}")
            return assessment
            
        except Exception as e:
            logger.error(f"Error assessing eligibility: {str(e)}")
            raise EligibilityAssessmentError(f"Failed to assess eligibility: {str(e)}")
    
    async def _perform_rule_based_assessment(self, 
                                           assessment: EligibilityAssessment,
                                           profile: Dict[str, Any],
                                           scheme: GovernmentScheme):
        """Perform rule-based eligibility checking."""
        try:
            rules = self._generate_eligibility_rules(scheme.eligibility_criteria)
            total_weight = sum(rule.weight for rule in rules)
            passed_weight = 0.0
            
            demographics = profile.get('demographics', DemographicInfo())
            economic = profile.get('economic', EconomicInfo())
            location = profile.get('location', LocationInfo(state='', district=''))
            
            for rule in rules:
                result = self._evaluate_rule(rule, demographics, economic, location)
                
                if result == 'passed':
                    assessment.passed_rules.append(rule.rule_id)
                    passed_weight += rule.weight
                elif result == 'failed':
                    assessment.failed_rules.append(rule.rule_id)
                    if rule.mandatory:
                        # Mandatory rule failed - not eligible
                        assessment.overall_status = EligibilityStatus.NOT_ELIGIBLE
                else:  # missing_data
                    assessment.missing_data_rules.append(rule.rule_id)
            
            # Calculate eligibility score
            if total_weight > 0:
                assessment.eligibility_score = passed_weight / total_weight
            
            # Determine overall status
            if assessment.overall_status != EligibilityStatus.NOT_ELIGIBLE:
                if assessment.eligibility_score >= 0.8:
                    assessment.overall_status = EligibilityStatus.ELIGIBLE
                elif assessment.eligibility_score >= 0.5:
                    assessment.overall_status = EligibilityStatus.PARTIALLY_ELIGIBLE
                elif len(assessment.missing_data_rules) > len(assessment.failed_rules):
                    assessment.overall_status = EligibilityStatus.INSUFFICIENT_DATA
                else:
                    assessment.overall_status = EligibilityStatus.NOT_ELIGIBLE
            
        except Exception as e:
            logger.error(f"Error in rule-based assessment: {str(e)}")
            assessment.overall_status = EligibilityStatus.INSUFFICIENT_DATA
    
    def _generate_eligibility_rules(self, criteria: EligibilityCriteria) -> List[EligibilityRule]:
        """Generate eligibility rules from criteria."""
        rules = []
        
        # Age rules
        if criteria.age_min is not None:
            rules.append(EligibilityRule(
                rule_id="age_min",
                name="Minimum Age",
                description=f"User must be at least {criteria.age_min} years old",
                field_name="age",
                operator="ge",
                value=criteria.age_min,
                mandatory=True,
                weight=1.0,
                error_message=f"Minimum age requirement is {criteria.age_min} years"
            ))
        
        if criteria.age_max is not None:
            rules.append(EligibilityRule(
                rule_id="age_max",
                name="Maximum Age",
                description=f"User must be at most {criteria.age_max} years old",
                field_name="age",
                operator="le",
                value=criteria.age_max,
                mandatory=True,
                weight=1.0,
                error_message=f"Maximum age limit is {criteria.age_max} years"
            ))
        
        # Income rule
        if criteria.income_limit is not None:
            rules.append(EligibilityRule(
                rule_id="income_limit",
                name="Income Limit",
                description=f"Annual income must not exceed ₹{criteria.income_limit:,}",
                field_name="income",
                operator="le",
                value=criteria.income_limit,
                mandatory=True,
                weight=2.0,
                error_message=f"Income exceeds limit of ₹{criteria.income_limit:,}"
            ))
        
        # Gender rule
        if criteria.gender is not None and criteria.gender != 'any':
            rules.append(EligibilityRule(
                rule_id="gender",
                name="Gender Requirement",
                description=f"Scheme is for {criteria.gender} applicants",
                field_name="gender",
                operator="eq",
                value=criteria.gender,
                mandatory=True,
                weight=1.0,
                error_message=f"This scheme is only for {criteria.gender} applicants"
            ))
        
        # Caste category rule
        if criteria.caste_category is not None and len(criteria.caste_category) > 0:
            rules.append(EligibilityRule(
                rule_id="caste_category",
                name="Caste Category",
                description=f"Must belong to one of: {', '.join(criteria.caste_category)}",
                field_name="caste_category",
                operator="in",
                value=criteria.caste_category,
                mandatory=True,
                weight=1.5,
                error_message=f"Must belong to category: {', '.join(criteria.caste_category)}"
            ))
        
        # Location type rule
        if criteria.location_type is not None and criteria.location_type != 'both':
            rules.append(EligibilityRule(
                rule_id="location_type",
                name="Location Type",
                description=f"Must be from {criteria.location_type} area",
                field_name="location_type",
                operator="eq",
                value=criteria.location_type,
                mandatory=True,
                weight=1.0,
                error_message=f"This scheme is only for {criteria.location_type} areas"
            ))
        
        # Employment status rule
        if criteria.employment_status is not None:
            rules.append(EligibilityRule(
                rule_id="employment_status",
                name="Employment Status",
                description=f"Employment status must be {criteria.employment_status}",
                field_name="employment_status",
                operator="eq",
                value=criteria.employment_status,
                mandatory=False,
                weight=0.5,
                error_message=f"Preferred employment status: {criteria.employment_status}"
            ))
        
        # Education level rule
        if criteria.education_level is not None:
            rules.append(EligibilityRule(
                rule_id="education_level",
                name="Education Level",
                description=f"Education level requirement: {criteria.education_level}",
                field_name="education_level",
                operator="eq",
                value=criteria.education_level,
                mandatory=False,
                weight=0.5,
                error_message=f"Education requirement: {criteria.education_level}"
            ))
        
        # Disability status rule
        if criteria.disability_status is not None:
            rules.append(EligibilityRule(
                rule_id="disability_status",
                name="Disability Status",
                description=f"Disability status must be {criteria.disability_status}",
                field_name="disability_status",
                operator="eq",
                value=criteria.disability_status,
                mandatory=True,
                weight=1.0,
                error_message=f"Disability status requirement: {criteria.disability_status}"
            ))
        
        # Family size rule
        if criteria.family_size is not None:
            rules.append(EligibilityRule(
                rule_id="family_size",
                name="Family Size",
                description=f"Family size must be at least {criteria.family_size}",
                field_name="family_size",
                operator="ge",
                value=criteria.family_size,
                mandatory=False,
                weight=0.5,
                error_message=f"Minimum family size: {criteria.family_size}"
            ))
        
        # Land ownership rule
        if criteria.land_ownership is not None:
            rules.append(EligibilityRule(
                rule_id="land_ownership",
                name="Land Ownership",
                description=f"Land ownership status: {criteria.land_ownership}",
                field_name="land_ownership",
                operator="eq",
                value=criteria.land_ownership,
                mandatory=False,
                weight=0.5,
                error_message=f"Land ownership requirement: {criteria.land_ownership}"
            ))
        
        # Housing status rule
        if criteria.housing_status is not None:
            rules.append(EligibilityRule(
                rule_id="housing_status",
                name="Housing Status",
                description=f"Housing status: {criteria.housing_status}",
                field_name="housing_status",
                operator="eq",
                value=criteria.housing_status,
                mandatory=False,
                weight=0.5,
                error_message=f"Housing status requirement: {criteria.housing_status}"
            ))
        
        return rules
    
    def _evaluate_rule(self, 
                      rule: EligibilityRule,
                      demographics: DemographicInfo,
                      economic: EconomicInfo,
                      location: LocationInfo) -> str:
        """Evaluate a single eligibility rule."""
        try:
            # Get field value based on rule field name
            field_value = None
            
            if rule.field_name == 'age':
                field_value = demographics.age
            elif rule.field_name == 'gender':
                field_value = demographics.gender
            elif rule.field_name == 'caste_category':
                field_value = demographics.caste_category
            elif rule.field_name == 'marital_status':
                field_value = demographics.marital_status
            elif rule.field_name == 'family_size':
                field_value = demographics.family_size
            elif rule.field_name == 'disability_status':
                field_value = demographics.disability_status
            elif rule.field_name == 'income':
                field_value = economic.income
            elif rule.field_name == 'employment_status':
                field_value = economic.employment_status
            elif rule.field_name == 'land_ownership':
                field_value = economic.land_ownership
            elif rule.field_name == 'housing_status':
                field_value = economic.housing_status
            elif rule.field_name == 'location_type':
                field_value = location.location_type
            
            # Check if data is missing
            if field_value is None:
                return 'missing_data'
            
            # Evaluate based on operator
            if rule.operator == 'eq':
                return 'passed' if field_value == rule.value else 'failed'
            elif rule.operator == 'ne':
                return 'passed' if field_value != rule.value else 'failed'
            elif rule.operator == 'lt':
                return 'passed' if field_value < rule.value else 'failed'
            elif rule.operator == 'le':
                return 'passed' if field_value <= rule.value else 'failed'
            elif rule.operator == 'gt':
                return 'passed' if field_value > rule.value else 'failed'
            elif rule.operator == 'ge':
                return 'passed' if field_value >= rule.value else 'failed'
            elif rule.operator == 'in':
                return 'passed' if field_value in rule.value else 'failed'
            elif rule.operator == 'not_in':
                return 'passed' if field_value not in rule.value else 'failed'
            elif rule.operator == 'range':
                min_val, max_val = rule.value
                return 'passed' if min_val <= field_value <= max_val else 'failed'
            
            return 'failed'
            
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.rule_id}: {str(e)}")
            return 'failed'
    
    async def _analyze_document_requirements(self, 
                                           assessment: EligibilityAssessment,
                                           profile: Dict[str, Any],
                                           scheme: GovernmentScheme):
        """Analyze document requirements and generate checklist."""
        try:
            required_docs = scheme.application_process.required_documents
            
            for doc_name in required_docs:
                doc_req = self._analyze_document_requirement(doc_name, profile, scheme)
                
                if doc_req.mandatory:
                    assessment.required_documents.append(doc_req)
                else:
                    assessment.optional_documents.append(doc_req)
                
                # Add to checklist
                assessment.document_checklist.append({
                    'document': doc_req.document_name,
                    'type': doc_req.document_type,
                    'status': doc_req.status.value,
                    'mandatory': doc_req.mandatory,
                    'description': doc_req.description,
                    'alternatives': doc_req.alternatives,
                    'issuing_authority': doc_req.issuing_authority,
                    'format_requirements': doc_req.format_requirements
                })
            
            # Add scheme-specific document requirements
            self._add_scheme_specific_documents(assessment, profile, scheme)
            
        except Exception as e:
            logger.error(f"Error analyzing document requirements: {str(e)}")
    
    def _analyze_document_requirement(self, 
                                    doc_name: str,
                                    profile: Dict[str, Any],
                                    scheme: GovernmentScheme) -> DocumentRequirement:
        """Analyze a specific document requirement."""
        doc_name_lower = doc_name.lower()
        
        # Identity documents
        if any(keyword in doc_name_lower for keyword in ['aadhaar', 'identity', 'id']):
            return DocumentRequirement(
                document_name=doc_name,
                document_type='identity',
                status=DocumentStatus.REQUIRED,
                description="Government-issued identity proof",
                alternatives=['Aadhaar Card', 'Voter ID', 'Passport', 'Driving License'],
                issuing_authority="Government of India",
                format_requirements=['Original or certified copy', 'Clear and legible'],
                mandatory=True
            )
        
        # Address documents
        elif any(keyword in doc_name_lower for keyword in ['address', 'residence']):
            return DocumentRequirement(
                document_name=doc_name,
                document_type='address',
                status=DocumentStatus.REQUIRED,
                description="Proof of current address",
                alternatives=['Aadhaar Card', 'Utility Bill', 'Bank Statement', 'Rent Agreement'],
                validity_period=90,  # 3 months
                format_requirements=['Recent document (within 3 months)', 'Clear address visible'],
                mandatory=True
            )
        
        # Income documents
        elif any(keyword in doc_name_lower for keyword in ['income', 'salary', 'earning']):
            return DocumentRequirement(
                document_name=doc_name,
                document_type='income',
                status=DocumentStatus.REQUIRED,
                description="Proof of annual income",
                alternatives=['Income Certificate', 'Salary Slips', 'ITR', 'Bank Statement'],
                issuing_authority="Tehsildar/Revenue Officer",
                validity_period=365,  # 1 year
                format_requirements=['Certified by competent authority', 'Current financial year'],
                mandatory=True
            )
        
        # Caste certificate
        elif any(keyword in doc_name_lower for keyword in ['caste', 'category', 'community']):
            return DocumentRequirement(
                document_name=doc_name,
                document_type='caste',
                status=DocumentStatus.REQUIRED,
                description="Caste/Category certificate",
                alternatives=['Caste Certificate', 'Community Certificate'],
                issuing_authority="District Collector/Tehsildar",
                format_requirements=['Original certificate', 'Valid and not expired'],
                mandatory=True
            )
        
        # Age proof
        elif any(keyword in doc_name_lower for keyword in ['age', 'birth', 'dob']):
            return DocumentRequirement(
                document_name=doc_name,
                document_type='age',
                status=DocumentStatus.REQUIRED,
                description="Proof of age/date of birth",
                alternatives=['Birth Certificate', 'School Certificate', 'Aadhaar Card'],
                format_requirements=['Government issued', 'Clear date of birth'],
                mandatory=True
            )
        
        # Education documents
        elif any(keyword in doc_name_lower for keyword in ['education', 'qualification', 'certificate']):
            return DocumentRequirement(
                document_name=doc_name,
                document_type='education',
                status=DocumentStatus.OPTIONAL,
                description="Educational qualification proof",
                alternatives=['Degree Certificate', 'Marksheet', 'School Certificate'],
                format_requirements=['Certified copy', 'From recognized institution'],
                mandatory=False
            )
        
        # Bank documents
        elif any(keyword in doc_name_lower for keyword in ['bank', 'account', 'passbook']):
            return DocumentRequirement(
                document_name=doc_name,
                document_type='bank',
                status=DocumentStatus.REQUIRED,
                description="Bank account details",
                alternatives=['Bank Passbook', 'Bank Statement', 'Cancelled Cheque'],
                format_requirements=['Active account', 'Clear account details'],
                mandatory=True
            )
        
        # Default document
        else:
            return DocumentRequirement(
                document_name=doc_name,
                document_type='other',
                status=DocumentStatus.REQUIRED,
                description=f"Required document: {doc_name}",
                format_requirements=['As specified by implementing agency'],
                mandatory=True
            )
    
    def _add_scheme_specific_documents(self, 
                                     assessment: EligibilityAssessment,
                                     profile: Dict[str, Any],
                                     scheme: GovernmentScheme):
        """Add scheme-specific document requirements."""
        try:
            # Add documents based on scheme category
            if scheme.category.value == 'agriculture':
                assessment.required_documents.append(DocumentRequirement(
                    document_name="Land Records",
                    document_type='land',
                    status=DocumentStatus.REQUIRED,
                    description="Proof of land ownership/cultivation",
                    alternatives=['Patta', 'Khata', 'Revenue Records'],
                    issuing_authority="Village Revenue Officer",
                    mandatory=True
                ))
            
            elif scheme.category.value == 'disability':
                assessment.required_documents.append(DocumentRequirement(
                    document_name="Disability Certificate",
                    document_type='disability',
                    status=DocumentStatus.REQUIRED,
                    description="Medical certificate of disability",
                    issuing_authority="Medical Board/Civil Surgeon",
                    validity_period=1825,  # 5 years
                    mandatory=True
                ))
            
            elif scheme.category.value == 'employment':
                assessment.optional_documents.append(DocumentRequirement(
                    document_name="Employment Registration",
                    document_type='employment',
                    status=DocumentStatus.OPTIONAL,
                    description="Registration with employment exchange",
                    issuing_authority="Employment Exchange",
                    mandatory=False
                ))
            
        except Exception as e:
            logger.error(f"Error adding scheme-specific documents: {str(e)}")
    
    async def _estimate_success_probability(self, 
                                          assessment: EligibilityAssessment,
                                          profile: Dict[str, Any],
                                          scheme: GovernmentScheme):
        """Estimate probability of successful application."""
        try:
            base_probability = 0.5  # Base 50% chance
            
            # Factor 1: Eligibility score (40% weight)
            eligibility_factor = assessment.eligibility_score * 0.4
            
            # Factor 2: Data completeness (20% weight)
            completeness_factor = assessment.data_completeness * 0.2
            
            # Factor 3: Scheme success rate (20% weight)
            scheme_success_factor = 0.0
            if scheme.metadata.success_rate > 0:
                scheme_success_factor = scheme.metadata.success_rate * 0.2
            else:
                scheme_success_factor = 0.6 * 0.2  # Assume 60% if unknown
            
            # Factor 4: Document readiness (10% weight)
            doc_readiness = self._calculate_document_readiness(assessment, profile)
            doc_factor = doc_readiness * 0.1
            
            # Factor 5: Profile quality (10% weight)
            profile_quality = self._calculate_profile_quality(profile)
            quality_factor = profile_quality * 0.1
            
            # Calculate final probability
            success_probability = (
                eligibility_factor + 
                completeness_factor + 
                scheme_success_factor + 
                doc_factor + 
                quality_factor
            )
            
            # Apply penalties for failed mandatory rules
            if assessment.failed_rules:
                mandatory_failures = len([rule for rule in assessment.failed_rules])
                penalty = min(mandatory_failures * 0.2, 0.8)
                success_probability *= (1.0 - penalty)
            
            # Apply bonus for high eligibility
            if assessment.eligibility_score > 0.9:
                success_probability += 0.1
            
            assessment.success_probability = min(max(success_probability, 0.0), 1.0)
            
        except Exception as e:
            logger.error(f"Error estimating success probability: {str(e)}")
            assessment.success_probability = 0.5
    
    def _calculate_document_readiness(self, 
                                    assessment: EligibilityAssessment,
                                    profile: Dict[str, Any]) -> float:
        """Calculate document readiness score."""
        try:
            if not assessment.required_documents:
                return 1.0
            
            # For demo purposes, assume some documents are available
            # In real implementation, this would check user's document status
            available_docs = 0
            total_docs = len(assessment.required_documents)
            
            # Simulate document availability based on profile completeness
            demographics = profile.get('demographics', DemographicInfo())
            economic = profile.get('economic', EconomicInfo())
            
            # Basic documents likely available if profile is complete
            if demographics.age is not None:
                available_docs += 1  # Age proof
            if economic.income is not None:
                available_docs += 1  # Income proof
            if demographics.caste_category is not None:
                available_docs += 1  # Caste certificate
            if economic.bank_account:
                available_docs += 1  # Bank documents
            
            # Assume identity and address documents are commonly available
            available_docs += 2
            
            return min(available_docs / max(total_docs, 1), 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating document readiness: {str(e)}")
            return 0.5
    
    def _calculate_profile_quality(self, profile: Dict[str, Any]) -> float:
        """Calculate profile quality score."""
        try:
            quality_score = 0.0
            
            # Check data consistency
            demographics = profile.get('demographics', DemographicInfo())
            economic = profile.get('economic', EconomicInfo())
            location = profile.get('location', LocationInfo(state='', district=''))
            
            # Age consistency
            if demographics.age is not None and 0 < demographics.age < 120:
                quality_score += 0.2
            
            # Income reasonableness
            if economic.income is not None and economic.income > 0:
                quality_score += 0.2
            
            # Location completeness
            if location.state and location.district:
                quality_score += 0.2
            
            # Profile recency (assume recent if updated recently)
            updated_at = profile.get('updated_at', datetime.now())
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            
            days_since_update = (datetime.now() - updated_at).days
            if days_since_update < 30:
                quality_score += 0.2
            elif days_since_update < 90:
                quality_score += 0.1
            
            # Interaction history
            interaction_history = profile.get('interaction_history', [])
            if len(interaction_history) > 0:
                quality_score += 0.2
            
            return min(quality_score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating profile quality: {str(e)}")
            return 0.5
    
    async def _generate_recommendations(self, 
                                      assessment: EligibilityAssessment,
                                      profile: Dict[str, Any],
                                      scheme: GovernmentScheme):
        """Generate recommendations and next steps."""
        try:
            # Recommendations based on assessment status
            if assessment.overall_status == EligibilityStatus.ELIGIBLE:
                assessment.recommendations.append(
                    "You are eligible for this scheme. Proceed with application."
                )
                assessment.next_steps.extend([
                    "Gather all required documents",
                    "Visit the nearest application center or apply online",
                    "Submit application before the deadline"
                ])
            
            elif assessment.overall_status == EligibilityStatus.PARTIALLY_ELIGIBLE:
                assessment.recommendations.append(
                    "You meet most requirements but some criteria need attention."
                )
                
                # Specific recommendations for failed rules
                for rule_id in assessment.failed_rules:
                    if rule_id == 'income_limit':
                        assessment.recommendations.append(
                            "Your income exceeds the limit. Check if you qualify for other income categories."
                        )
                    elif rule_id == 'age_min' or rule_id == 'age_max':
                        assessment.recommendations.append(
                            "Age requirement not met. Look for similar schemes with different age criteria."
                        )
            
            elif assessment.overall_status == EligibilityStatus.INSUFFICIENT_DATA:
                assessment.recommendations.append(
                    "Complete your profile to get accurate eligibility assessment."
                )
                
                # Specific data needed
                for rule_id in assessment.missing_data_rules:
                    if rule_id == 'income_limit':
                        assessment.next_steps.append("Provide annual income information")
                    elif rule_id == 'age_min' or rule_id == 'age_max':
                        assessment.next_steps.append("Provide date of birth/age information")
                    elif rule_id == 'caste_category':
                        assessment.next_steps.append("Provide caste/category information")
            
            else:  # NOT_ELIGIBLE
                assessment.recommendations.append(
                    "You do not meet the eligibility criteria for this scheme."
                )
                assessment.next_steps.append(
                    "Explore other schemes that match your profile"
                )
            
            # Document-specific recommendations
            if assessment.required_documents:
                assessment.next_steps.append(
                    f"Prepare {len(assessment.required_documents)} required documents"
                )
            
            # Success probability based recommendations
            if assessment.success_probability > 0.8:
                assessment.recommendations.append(
                    "High chance of approval. Apply as soon as possible."
                )
            elif assessment.success_probability > 0.6:
                assessment.recommendations.append(
                    "Good chance of approval. Ensure all documents are complete."
                )
            elif assessment.success_probability > 0.4:
                assessment.recommendations.append(
                    "Moderate chance of approval. Consider improving profile completeness."
                )
            else:
                assessment.recommendations.append(
                    "Low chance of approval. Review eligibility criteria carefully."
                )
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
    
    def _calculate_confidence_level(self, 
                                  assessment: EligibilityAssessment,
                                  profile: Dict[str, Any]) -> float:
        """Calculate confidence level in the assessment."""
        try:
            confidence = 0.0
            
            # Data completeness factor (40%)
            confidence += assessment.data_completeness * 0.4
            
            # Rule evaluation completeness (30%)
            total_rules = len(assessment.passed_rules) + len(assessment.failed_rules) + len(assessment.missing_data_rules)
            evaluated_rules = len(assessment.passed_rules) + len(assessment.failed_rules)
            
            if total_rules > 0:
                rule_completeness = evaluated_rules / total_rules
                confidence += rule_completeness * 0.3
            
            # Profile quality factor (20%)
            profile_quality = self._calculate_profile_quality(profile)
            confidence += profile_quality * 0.2
            
            # Assessment consistency (10%)
            if assessment.overall_status != EligibilityStatus.INSUFFICIENT_DATA:
                confidence += 0.1
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating confidence level: {str(e)}")
            return 0.5
    
    async def get_document_checklist(self, 
                                   user_id: str, 
                                   scheme: GovernmentScheme) -> List[Dict[str, Any]]:
        """Get document checklist for a scheme."""
        try:
            assessment = await self.assess_eligibility(user_id, scheme)
            return assessment.document_checklist
            
        except Exception as e:
            logger.error(f"Error getting document checklist: {str(e)}")
            return []
    
    async def estimate_approval_timeline(self, 
                                       assessment: EligibilityAssessment,
                                       scheme: GovernmentScheme) -> Dict[str, Any]:
        """Estimate approval timeline based on assessment."""
        try:
            base_days = scheme.application_process.processing_time_days or 30
            
            # Adjust based on success probability
            if assessment.success_probability > 0.8:
                estimated_days = base_days
            elif assessment.success_probability > 0.6:
                estimated_days = int(base_days * 1.2)
            else:
                estimated_days = int(base_days * 1.5)
            
            return {
                'estimated_processing_days': estimated_days,
                'base_processing_days': base_days,
                'confidence': assessment.confidence_level,
                'factors': [
                    f"Success probability: {assessment.success_probability:.1%}",
                    f"Data completeness: {assessment.data_completeness:.1%}",
                    f"Document readiness: {len(assessment.required_documents)} documents required"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error estimating approval timeline: {str(e)}")
            return {
                'estimated_processing_days': 30,
                'base_processing_days': 30,
                'confidence': 0.5,
                'factors': ['Default estimate due to error']
            }