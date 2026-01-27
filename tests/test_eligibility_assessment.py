"""
Unit tests for eligibility assessment system.

Tests rule-based eligibility checking, document requirement analysis,
and success probability estimation functionality.
"""

import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from bharat_voice_assistant.schemes.eligibility_assessor import (
    EligibilityAssessor, EligibilityStatus, DocumentStatus,
    EligibilityRule, DocumentRequirement, EligibilityAssessment
)
from bharat_voice_assistant.schemes.models import (
    GovernmentScheme, SchemeCategory, EligibilityCriteria, 
    SchemeBenefits, ApplicationProcess, SchemeMetadata, DataSource
)
from bharat_voice_assistant.schemes.user_profile import (
    UserProfileManager, DemographicInfo, EconomicInfo, LocationInfo
)


class TestEligibilityAssessor:
    """Test cases for EligibilityAssessor class."""
    
    @pytest.fixture
    def user_profile_manager(self):
        """Create mock user profile manager."""
        return AsyncMock(spec=UserProfileManager)
    
    @pytest.fixture
    def assessor(self, user_profile_manager):
        """Create eligibility assessor instance."""
        return EligibilityAssessor(user_profile_manager)
    
    @pytest.fixture
    def sample_user_profile(self):
        """Create sample user profile."""
        return {
            'user_id': 'test_user_123',
            'demographics': DemographicInfo(
                age=35,
                gender='male',
                caste_category='obc',
                marital_status='married',
                family_size=4,
                disability_status=False
            ),
            'economic': EconomicInfo(
                income=150000,
                employment_status='employed',
                land_ownership='small',
                housing_status='owned',
                bank_account=True
            ),
            'location': LocationInfo(
                state='Karnataka',
                district='Bangalore',
                location_type='urban'
            ),
            'interaction_history': [],
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
    
    @pytest.fixture
    def sample_scheme(self):
        """Create sample government scheme."""
        return GovernmentScheme(
            scheme_id="test-scheme-001",
            name="Test Housing Scheme",
            department="Ministry of Housing",
            category=SchemeCategory.HOUSING,
            description="Test scheme for housing assistance",
            eligibility_criteria=EligibilityCriteria(
                age_min=18,
                age_max=60,
                income_limit=200000,
                location_type="both",
                caste_category=["obc", "sc", "st"]
            ),
            benefits=SchemeBenefits(
                financial_assistance=100000,
                description="Financial assistance for house construction"
            ),
            application_process=ApplicationProcess(
                required_documents=[
                    "Identity Proof",
                    "Address Proof", 
                    "Income Certificate",
                    "Caste Certificate",
                    "Bank Account Details"
                ],
                processing_time_days=45
            ),
            target_states=["Karnataka", "Tamil Nadu"],
            metadata=SchemeMetadata(
                data_source=DataSource.GOVERNMENT_API,
                success_rate=0.75
            )
        )
    
    @pytest.mark.asyncio
    async def test_assess_eligibility_eligible_user(self, assessor, sample_user_profile, sample_scheme):
        """Test eligibility assessment for eligible user."""
        # Setup
        assessor.user_profile_manager.get_profile.return_value = sample_user_profile
        assessor.user_profile_manager.get_profile_completeness.return_value = 0.9
        
        # Execute
        assessment = await assessor.assess_eligibility('test_user_123', sample_scheme)
        
        # Verify
        assert isinstance(assessment, EligibilityAssessment)
        assert assessment.scheme_id == "test-scheme-001"
        assert assessment.user_id == "test_user_123"
        assert assessment.overall_status == EligibilityStatus.ELIGIBLE
        assert assessment.eligibility_score > 0.8
        assert assessment.success_probability > 0.5
        assert len(assessment.passed_rules) > 0
        assert len(assessment.required_documents) > 0
        assert len(assessment.recommendations) > 0
        assert assessment.confidence_level > 0.0
    
    @pytest.mark.asyncio
    async def test_assess_eligibility_not_eligible_user(self, assessor, sample_user_profile, sample_scheme):
        """Test eligibility assessment for non-eligible user."""
        # Setup - modify profile to be ineligible
        sample_user_profile['economic'].income = 300000  # Exceeds limit
        sample_user_profile['demographics'].age = 70  # Exceeds age limit
        assessor.user_profile_manager.get_profile.return_value = sample_user_profile
        assessor.user_profile_manager.get_profile_completeness.return_value = 0.9
        
        # Execute
        assessment = await assessor.assess_eligibility('test_user_123', sample_scheme)
        
        # Verify
        assert assessment.overall_status == EligibilityStatus.NOT_ELIGIBLE
        assert assessment.eligibility_score < 0.5
        assert len(assessment.failed_rules) > 0
        assert "income_limit" in assessment.failed_rules or "age_max" in assessment.failed_rules
    
    @pytest.mark.asyncio
    async def test_assess_eligibility_insufficient_data(self, assessor, sample_user_profile, sample_scheme):
        """Test eligibility assessment with insufficient data."""
        # Setup - remove key data
        sample_user_profile['demographics'].age = None
        sample_user_profile['economic'].income = None
        sample_user_profile['demographics'].caste_category = None
        assessor.user_profile_manager.get_profile.return_value = sample_user_profile
        assessor.user_profile_manager.get_profile_completeness.return_value = 0.3
        
        # Execute
        assessment = await assessor.assess_eligibility('test_user_123', sample_scheme)
        
        # Verify
        assert assessment.overall_status == EligibilityStatus.INSUFFICIENT_DATA
        assert len(assessment.missing_data_rules) > 0
        assert "age_min" in assessment.missing_data_rules or "age_max" in assessment.missing_data_rules
        assert "income_limit" in assessment.missing_data_rules
    
    @pytest.mark.asyncio
    async def test_assess_eligibility_user_not_found(self, assessor, sample_scheme):
        """Test eligibility assessment when user profile not found."""
        # Setup
        assessor.user_profile_manager.get_profile.return_value = None
        
        # Execute & Verify
        with pytest.raises(Exception):
            await assessor.assess_eligibility('nonexistent_user', sample_scheme)
    
    def test_generate_eligibility_rules(self, assessor):
        """Test eligibility rule generation from criteria."""
        criteria = EligibilityCriteria(
            age_min=18,
            age_max=60,
            income_limit=200000,
            gender="female",
            caste_category=["sc", "st"],
            location_type="rural"
        )
        
        rules = assessor._generate_eligibility_rules(criteria)
        
        # Verify rules are generated
        assert len(rules) > 0
        rule_ids = [rule.rule_id for rule in rules]
        assert "age_min" in rule_ids
        assert "age_max" in rule_ids
        assert "income_limit" in rule_ids
        assert "gender" in rule_ids
        assert "caste_category" in rule_ids
        assert "location_type" in rule_ids
        
        # Verify rule properties
        age_min_rule = next(rule for rule in rules if rule.rule_id == "age_min")
        assert age_min_rule.operator == "ge"
        assert age_min_rule.value == 18
        assert age_min_rule.mandatory is True
    
    def test_evaluate_rule_passed(self, assessor):
        """Test rule evaluation - passed case."""
        rule = EligibilityRule(
            rule_id="age_min",
            name="Minimum Age",
            description="Must be at least 18",
            field_name="age",
            operator="ge",
            value=18,
            mandatory=True
        )
        
        demographics = DemographicInfo(age=25)
        economic = EconomicInfo()
        location = LocationInfo(state='', district='')
        
        result = assessor._evaluate_rule(rule, demographics, economic, location)
        assert result == 'passed'
    
    def test_evaluate_rule_failed(self, assessor):
        """Test rule evaluation - failed case."""
        rule = EligibilityRule(
            rule_id="income_limit",
            name="Income Limit",
            description="Income must not exceed limit",
            field_name="income",
            operator="le",
            value=200000,
            mandatory=True
        )
        
        demographics = DemographicInfo()
        economic = EconomicInfo(income=300000)  # Exceeds limit
        location = LocationInfo(state='', district='')
        
        result = assessor._evaluate_rule(rule, demographics, economic, location)
        assert result == 'failed'
    
    def test_evaluate_rule_missing_data(self, assessor):
        """Test rule evaluation - missing data case."""
        rule = EligibilityRule(
            rule_id="age_min",
            name="Minimum Age",
            description="Must be at least 18",
            field_name="age",
            operator="ge",
            value=18,
            mandatory=True
        )
        
        demographics = DemographicInfo(age=None)  # Missing age
        economic = EconomicInfo()
        location = LocationInfo(state='', district='')
        
        result = assessor._evaluate_rule(rule, demographics, economic, location)
        assert result == 'missing_data'
    
    def test_analyze_document_requirement_identity(self, assessor, sample_user_profile, sample_scheme):
        """Test document requirement analysis for identity documents."""
        doc_req = assessor._analyze_document_requirement(
            "Aadhaar Card", sample_user_profile, sample_scheme
        )
        
        assert doc_req.document_type == 'identity'
        assert doc_req.status == DocumentStatus.REQUIRED
        assert doc_req.mandatory is True
        assert len(doc_req.alternatives) > 0
        assert 'Aadhaar Card' in doc_req.alternatives
    
    def test_analyze_document_requirement_income(self, assessor, sample_user_profile, sample_scheme):
        """Test document requirement analysis for income documents."""
        doc_req = assessor._analyze_document_requirement(
            "Income Certificate", sample_user_profile, sample_scheme
        )
        
        assert doc_req.document_type == 'income'
        assert doc_req.status == DocumentStatus.REQUIRED
        assert doc_req.mandatory is True
        assert doc_req.validity_period == 365
        assert doc_req.issuing_authority == "Tehsildar/Revenue Officer"
    
    def test_analyze_document_requirement_education(self, assessor, sample_user_profile, sample_scheme):
        """Test document requirement analysis for education documents."""
        doc_req = assessor._analyze_document_requirement(
            "Education Certificate", sample_user_profile, sample_scheme
        )
        
        assert doc_req.document_type == 'education'
        assert doc_req.status == DocumentStatus.OPTIONAL
        assert doc_req.mandatory is False
    
    def test_calculate_document_readiness(self, assessor, sample_user_profile):
        """Test document readiness calculation."""
        assessment = EligibilityAssessment(
            scheme_id="test",
            user_id="test",
            overall_status=EligibilityStatus.ELIGIBLE,
            eligibility_score=0.8,
            success_probability=0.7,
            required_documents=[
                DocumentRequirement("Identity", "identity", DocumentStatus.REQUIRED, "ID proof"),
                DocumentRequirement("Income", "income", DocumentStatus.REQUIRED, "Income proof")
            ]
        )
        
        readiness = assessor._calculate_document_readiness(assessment, sample_user_profile)
        
        assert 0.0 <= readiness <= 1.0
        assert readiness > 0.0  # Should have some documents available
    
    def test_calculate_profile_quality(self, assessor, sample_user_profile):
        """Test profile quality calculation."""
        quality = assessor._calculate_profile_quality(sample_user_profile)
        
        assert 0.0 <= quality <= 1.0
        assert quality > 0.5  # Complete profile should have good quality
    
    def test_calculate_confidence_level(self, assessor, sample_user_profile):
        """Test confidence level calculation."""
        assessment = EligibilityAssessment(
            scheme_id="test",
            user_id="test",
            overall_status=EligibilityStatus.ELIGIBLE,
            eligibility_score=0.8,
            success_probability=0.7,
            passed_rules=["age_min", "income_limit"],
            failed_rules=[],
            missing_data_rules=[],
            data_completeness=0.9
        )
        
        confidence = assessor._calculate_confidence_level(assessment, sample_user_profile)
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Good assessment should have high confidence
    
    @pytest.mark.asyncio
    async def test_get_document_checklist(self, assessor, sample_user_profile, sample_scheme):
        """Test document checklist generation."""
        # Setup
        assessor.user_profile_manager.get_profile.return_value = sample_user_profile
        assessor.user_profile_manager.get_profile_completeness.return_value = 0.9
        
        # Execute
        checklist = await assessor.get_document_checklist('test_user_123', sample_scheme)
        
        # Verify
        assert isinstance(checklist, list)
        assert len(checklist) > 0
        
        # Check checklist structure
        for item in checklist:
            assert 'document' in item
            assert 'type' in item
            assert 'status' in item
            assert 'mandatory' in item
            assert 'description' in item
    
    @pytest.mark.asyncio
    async def test_estimate_approval_timeline(self, assessor, sample_scheme):
        """Test approval timeline estimation."""
        assessment = EligibilityAssessment(
            scheme_id="test",
            user_id="test",
            overall_status=EligibilityStatus.ELIGIBLE,
            eligibility_score=0.8,
            success_probability=0.9,
            confidence_level=0.8,
            data_completeness=0.9
        )
        
        timeline = await assessor.estimate_approval_timeline(assessment, sample_scheme)
        
        assert 'estimated_processing_days' in timeline
        assert 'base_processing_days' in timeline
        assert 'confidence' in timeline
        assert 'factors' in timeline
        
        assert timeline['estimated_processing_days'] > 0
        assert timeline['base_processing_days'] == 45  # From sample scheme
        assert isinstance(timeline['factors'], list)
    
    def test_eligibility_rule_creation(self):
        """Test EligibilityRule dataclass creation."""
        rule = EligibilityRule(
            rule_id="test_rule",
            name="Test Rule",
            description="A test rule",
            field_name="age",
            operator="ge",
            value=18,
            mandatory=True,
            weight=1.0,
            error_message="Age must be at least 18"
        )
        
        assert rule.rule_id == "test_rule"
        assert rule.name == "Test Rule"
        assert rule.mandatory is True
        assert rule.weight == 1.0
    
    def test_document_requirement_creation(self):
        """Test DocumentRequirement dataclass creation."""
        doc_req = DocumentRequirement(
            document_name="Test Document",
            document_type="identity",
            status=DocumentStatus.REQUIRED,
            description="Test document requirement",
            alternatives=["Alt1", "Alt2"],
            validity_period=365,
            issuing_authority="Test Authority",
            format_requirements=["Original", "Clear"],
            mandatory=True
        )
        
        assert doc_req.document_name == "Test Document"
        assert doc_req.document_type == "identity"
        assert doc_req.status == DocumentStatus.REQUIRED
        assert len(doc_req.alternatives) == 2
        assert doc_req.validity_period == 365
        assert doc_req.mandatory is True
    
    def test_eligibility_assessment_creation(self):
        """Test EligibilityAssessment dataclass creation."""
        assessment = EligibilityAssessment(
            scheme_id="test-scheme",
            user_id="test-user",
            overall_status=EligibilityStatus.ELIGIBLE,
            eligibility_score=0.8,
            success_probability=0.7
        )
        
        assert assessment.scheme_id == "test-scheme"
        assert assessment.user_id == "test-user"
        assert assessment.overall_status == EligibilityStatus.ELIGIBLE
        assert assessment.eligibility_score == 0.8
        assert assessment.success_probability == 0.7
        assert isinstance(assessment.passed_rules, list)
        assert isinstance(assessment.failed_rules, list)
        assert isinstance(assessment.missing_data_rules, list)
        assert isinstance(assessment.required_documents, list)
        assert isinstance(assessment.optional_documents, list)
        assert isinstance(assessment.document_checklist, list)
        assert isinstance(assessment.recommendations, list)
        assert isinstance(assessment.next_steps, list)
        assert isinstance(assessment.assessment_date, datetime)


class TestEligibilityAssessmentEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def assessor(self):
        """Create assessor with mock user profile manager."""
        return EligibilityAssessor(AsyncMock(spec=UserProfileManager))
    
    def test_evaluate_rule_with_invalid_operator(self, assessor):
        """Test rule evaluation with invalid operator."""
        rule = EligibilityRule(
            rule_id="test",
            name="Test",
            description="Test",
            field_name="age",
            operator="invalid_op",  # Invalid operator
            value=18,
            mandatory=True
        )
        
        demographics = DemographicInfo(age=25)
        economic = EconomicInfo()
        location = LocationInfo(state='', district='')
        
        result = assessor._evaluate_rule(rule, demographics, economic, location)
        assert result == 'failed'  # Should default to failed for invalid operator
    
    def test_evaluate_rule_with_range_operator(self, assessor):
        """Test rule evaluation with range operator."""
        rule = EligibilityRule(
            rule_id="age_range",
            name="Age Range",
            description="Age must be in range",
            field_name="age",
            operator="range",
            value=[18, 60],  # Range value
            mandatory=True
        )
        
        # Test within range
        demographics = DemographicInfo(age=35)
        economic = EconomicInfo()
        location = LocationInfo(state='', district='')
        
        result = assessor._evaluate_rule(rule, demographics, economic, location)
        assert result == 'passed'
        
        # Test outside range
        demographics.age = 70
        result = assessor._evaluate_rule(rule, demographics, economic, location)
        assert result == 'failed'
    
    def test_evaluate_rule_with_in_operator(self, assessor):
        """Test rule evaluation with 'in' operator."""
        rule = EligibilityRule(
            rule_id="caste_check",
            name="Caste Check",
            description="Must be in allowed castes",
            field_name="caste_category",
            operator="in",
            value=["sc", "st", "obc"],
            mandatory=True
        )
        
        # Test matching value
        demographics = DemographicInfo(caste_category="obc")
        economic = EconomicInfo()
        location = LocationInfo(state='', district='')
        
        result = assessor._evaluate_rule(rule, demographics, economic, location)
        assert result == 'passed'
        
        # Test non-matching value
        demographics.caste_category = "general"
        result = assessor._evaluate_rule(rule, demographics, economic, location)
        assert result == 'failed'
    
    def test_analyze_document_requirement_unknown_type(self, assessor):
        """Test document analysis for unknown document type."""
        doc_req = assessor._analyze_document_requirement(
            "Unknown Document Type", {}, GovernmentScheme()
        )
        
        assert doc_req.document_type == 'other'
        assert doc_req.status == DocumentStatus.REQUIRED
        assert doc_req.mandatory is True
    
    def test_calculate_document_readiness_no_documents(self, assessor):
        """Test document readiness with no required documents."""
        assessment = EligibilityAssessment(
            scheme_id="test",
            user_id="test",
            overall_status=EligibilityStatus.ELIGIBLE,
            eligibility_score=0.8,
            success_probability=0.7,
            required_documents=[]  # No documents required
        )
        
        readiness = assessor._calculate_document_readiness(assessment, {})
        assert readiness == 1.0  # Should be 100% ready if no documents required
    
    def test_calculate_profile_quality_empty_profile(self, assessor):
        """Test profile quality calculation with empty profile."""
        empty_profile = {
            'demographics': DemographicInfo(),
            'economic': EconomicInfo(),
            'location': LocationInfo(state='', district=''),
            'interaction_history': [],
            'updated_at': datetime.now()
        }
        
        quality = assessor._calculate_profile_quality(empty_profile)
        assert 0.0 <= quality <= 1.0
        assert quality < 0.5  # Empty profile should have low quality
    
    @pytest.mark.asyncio
    async def test_estimate_approval_timeline_no_processing_time(self, assessor):
        """Test timeline estimation when scheme has no processing time."""
        assessment = EligibilityAssessment(
            scheme_id="test",
            user_id="test",
            overall_status=EligibilityStatus.ELIGIBLE,
            eligibility_score=0.8,
            success_probability=0.7,
            confidence_level=0.8
        )
        
        scheme = GovernmentScheme(
            application_process=ApplicationProcess(
                processing_time_days=None  # No processing time specified
            )
        )
        
        timeline = await assessor.estimate_approval_timeline(assessment, scheme)
        
        assert timeline['estimated_processing_days'] == 36  # 30 * 1.2 for success probability 0.7
        assert timeline['base_processing_days'] == 30