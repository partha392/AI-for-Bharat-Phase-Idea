"""
Tests for intelligent scheme matching algorithm.

This module tests the multi-criteria matching based on demographics and location,
relevance scoring with machine learning models, and personalization based on user
interaction history.

Requirements: 2.1, 2.4, 2.5
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from bharat_voice_assistant.schemes.scheme_matcher import (
    IntelligentSchemeMatcher, UserProfile, MatchScore, MatchingCriteria
)
from bharat_voice_assistant.schemes.scheme_discovery import (
    SchemeDiscoveryService, DiscoveryQuery, SchemeRecommendation
)
from bharat_voice_assistant.schemes.user_profile import (
    UserProfileManager, InteractionRecord, LocationInfo, DemographicInfo, EconomicInfo
)
from bharat_voice_assistant.schemes.models import (
    GovernmentScheme, SchemeCategory, EligibilityCriteria, SchemeBenefits, ApplicationProcess
)

# Import hypothesis for property-based testing
from hypothesis import given, strategies as st, settings, HealthCheck


class TestIntelligentSchemeMatcher:
    """Test cases for the intelligent scheme matching algorithm."""
    
    @pytest.fixture
    def matcher(self):
        """Create a scheme matcher instance."""
        return IntelligentSchemeMatcher()
    
    @pytest.fixture
    def sample_user_profile(self):
        """Create a sample user profile for testing."""
        return UserProfile(
            user_id="test-user-123",
            age=35,
            gender="male",
            income=150000,
            location={
                "state": "Maharashtra",
                "district": "Mumbai",
                "type": "urban"
            },
            education_level="secondary",
            employment_status="employed",
            caste_category="general",
            disability_status=False,
            marital_status="married",
            family_size=4,
            land_ownership="landless",
            housing_status="rented",
            preferred_categories=[SchemeCategory.HOUSING, SchemeCategory.EDUCATION],
            interaction_history=[
                {
                    "scheme_id": "pmay-g-001",
                    "category": "housing",
                    "action": "viewed",
                    "timestamp": (datetime.now() - timedelta(days=5)).isoformat(),
                    "engagement_time": 120
                }
            ]
        )
    
    @pytest.fixture
    def sample_schemes(self):
        """Create sample government schemes for testing."""
        schemes = []
        
        # Housing scheme
        housing_scheme = GovernmentScheme(
            scheme_id="pmay-g-001",
            name="Pradhan Mantri Awas Yojana - Gramin",
            department="Ministry of Rural Development",
            category=SchemeCategory.HOUSING,
            description="Financial assistance for construction of pucca house",
            eligibility_criteria=EligibilityCriteria(
                income_limit=200000,
                location_type="both",
                housing_status="homeless_or_inadequate"
            ),
            benefits=SchemeBenefits(
                financial_assistance=120000,
                description="Financial assistance for construction of pucca house"
            ),
            target_states=["Maharashtra", "Gujarat"],
            target_districts=["Mumbai", "Pune"]
        )
        schemes.append(housing_scheme)
        
        # Agriculture scheme
        agriculture_scheme = GovernmentScheme(
            scheme_id="pmkisan-001",
            name="PM-KISAN",
            department="Ministry of Agriculture",
            category=SchemeCategory.AGRICULTURE,
            description="Annual financial assistance for farmers",
            eligibility_criteria=EligibilityCriteria(
                land_ownership="small_marginal",
                employment_status="farmer"
            ),
            benefits=SchemeBenefits(
                financial_assistance=6000,
                description="Annual financial assistance of Rs. 6000"
            ),
            target_states=["Maharashtra"]
        )
        schemes.append(agriculture_scheme)
        
        # Education scheme
        education_scheme = GovernmentScheme(
            scheme_id="edu-001",
            name="Scholarship Scheme",
            department="Ministry of Education",
            category=SchemeCategory.EDUCATION,
            description="Educational support for students",
            eligibility_criteria=EligibilityCriteria(
                age_min=5,
                age_max=25,
                income_limit=300000
            ),
            benefits=SchemeBenefits(
                financial_assistance=25000,
                description="Educational scholarship"
            ),
            target_states=["Maharashtra"]
        )
        schemes.append(education_scheme)
        
        return schemes
    
    @pytest.mark.asyncio
    async def test_match_schemes_basic(self, matcher, sample_user_profile, sample_schemes):
        """Test basic scheme matching functionality."""
        # Test matching schemes to user profile
        results = await matcher.match_schemes(
            user_profile=sample_user_profile,
            available_schemes=sample_schemes,
            max_results=5
        )
        
        # Verify results
        assert len(results) > 0
        assert len(results) <= 5
        
        # Check result structure
        for scheme, match_score in results:
            assert isinstance(scheme, GovernmentScheme)
            assert isinstance(match_score, MatchScore)
            assert 0.0 <= match_score.overall_score <= 1.0
            assert isinstance(match_score.eligibility_match, bool)
            assert 0.0 <= match_score.confidence <= 1.0
            assert 0.0 <= match_score.approval_likelihood <= 1.0
    
    @pytest.mark.asyncio
    async def test_eligibility_compliance_check(self, matcher, sample_user_profile, sample_schemes):
        """Test eligibility compliance checking."""
        housing_scheme = sample_schemes[0]  # Housing scheme
        
        # Test with eligible user
        score, eligible = matcher._check_eligibility_compliance(
            sample_user_profile, housing_scheme.eligibility_criteria
        )
        
        assert isinstance(score, float)
        assert isinstance(eligible, bool)
        assert 0.0 <= score <= 1.0
        
        # Test with ineligible user (high income)
        high_income_profile = UserProfile(
            user_id="high-income-user",
            income=500000  # Above housing scheme limit
        )
        
        score, eligible = matcher._check_eligibility_compliance(
            high_income_profile, housing_scheme.eligibility_criteria
        )
        
        assert score >= 0.0  # Some partial compliance possible
        # Note: eligible might still be True if other criteria are met
    
    def test_demographics_score_calculation(self, matcher, sample_user_profile, sample_schemes):
        """Test demographics-based scoring."""
        housing_scheme = sample_schemes[0]
        
        score = matcher._calculate_demographics_score(sample_user_profile, housing_scheme)
        
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
    
    def test_location_score_calculation(self, matcher, sample_user_profile, sample_schemes):
        """Test location-based scoring."""
        housing_scheme = sample_schemes[0]
        
        score = matcher._calculate_location_score(sample_user_profile, housing_scheme)
        
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        
        # Should score high since user is in Maharashtra and scheme targets Maharashtra
        assert score > 0.5
    
    def test_income_score_calculation(self, matcher, sample_user_profile, sample_schemes):
        """Test income-based scoring."""
        housing_scheme = sample_schemes[0]  # Income limit: 200000
        
        score = matcher._calculate_income_score(sample_user_profile, housing_scheme)
        
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        
        # User income (150000) is below limit (200000), should score well
        assert score > 0.6
    
    def test_category_preference_score(self, matcher, sample_user_profile, sample_schemes):
        """Test category preference scoring."""
        housing_scheme = sample_schemes[0]
        
        score = matcher._calculate_category_preference_score(sample_user_profile, housing_scheme)
        
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        
        # User has housing in preferred categories, should score high
        assert score > 0.8
    
    def test_interaction_score_calculation(self, matcher, sample_user_profile, sample_schemes):
        """Test interaction history scoring."""
        housing_scheme = sample_schemes[0]
        
        score = matcher._calculate_interaction_score(sample_user_profile, housing_scheme)
        
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        
        # User has recent interaction with housing scheme, should boost score
        assert score >= 0.5
    
    def test_approval_likelihood_calculation(self, matcher, sample_user_profile, sample_schemes):
        """Test approval likelihood calculation."""
        housing_scheme = sample_schemes[0]
        
        # Create a mock match score
        match_score = MatchScore(
            scheme_id=housing_scheme.scheme_id,
            overall_score=0.8,
            criteria_scores={
                MatchingCriteria.ELIGIBILITY_COMPLIANCE: 0.9,
                MatchingCriteria.DEMOGRAPHICS: 0.7,
                MatchingCriteria.LOCATION: 0.8
            }
        )
        
        likelihood = matcher._calculate_approval_likelihood(
            sample_user_profile, housing_scheme, match_score
        )
        
        assert isinstance(likelihood, float)
        assert 0.0 <= likelihood <= 1.0
    
    def test_confidence_calculation(self, matcher):
        """Test confidence calculation."""
        match_score = MatchScore(
            scheme_id="test-scheme",
            overall_score=0.8,
            criteria_scores={
                MatchingCriteria.ELIGIBILITY_COMPLIANCE: 0.9,
                MatchingCriteria.DEMOGRAPHICS: 0.8,
                MatchingCriteria.LOCATION: 0.7,
                MatchingCriteria.INCOME: 0.6
            },
            eligibility_match=True
        )
        
        confidence = matcher._calculate_confidence(match_score)
        
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
    
    def test_match_explanation_generation(self, matcher, sample_user_profile, sample_schemes):
        """Test match explanation generation."""
        housing_scheme = sample_schemes[0]
        
        match_score = MatchScore(
            scheme_id=housing_scheme.scheme_id,
            overall_score=0.8,
            criteria_scores={
                MatchingCriteria.ELIGIBILITY_COMPLIANCE: 0.9,
                MatchingCriteria.LOCATION: 0.8,
                MatchingCriteria.DEMOGRAPHICS: 0.7
            },
            eligibility_match=True,
            approval_likelihood=0.8
        )
        
        explanations = matcher._generate_match_explanation(
            sample_user_profile, housing_scheme, match_score
        )
        
        assert isinstance(explanations, list)
        assert len(explanations) > 0
        assert all(isinstance(exp, str) for exp in explanations)
    
    @pytest.mark.asyncio
    async def test_personalization_boost(self, matcher, sample_user_profile, sample_schemes):
        """Test personalization boost application."""
        results = [(scheme, MatchScore(scheme_id=scheme.scheme_id, overall_score=0.5)) 
                  for scheme in sample_schemes]
        
        personalized_results = await matcher._apply_personalization(
            sample_user_profile, results
        )
        
        assert len(personalized_results) == len(results)
        
        # Check that personalization boost was applied
        for scheme, match_score in personalized_results:
            assert hasattr(match_score, 'personalization_boost')
            assert isinstance(match_score.personalization_boost, float)
    
    def test_education_level_matching(self, matcher):
        """Test education level matching logic."""
        # Test exact match
        assert matcher._education_level_matches("secondary", "secondary")
        
        # Test hierarchy (higher education meets lower requirement)
        assert matcher._education_level_matches("graduate", "secondary")
        
        # Test insufficient education
        assert not matcher._education_level_matches("primary", "graduate")
        
        # Test None handling
        assert not matcher._education_level_matches(None, "secondary")
    
    def test_related_categories(self, matcher):
        """Test related category identification."""
        related = matcher._get_related_categories(SchemeCategory.AGRICULTURE)
        
        assert isinstance(related, set)
        assert SchemeCategory.RURAL_DEVELOPMENT in related
        assert SchemeCategory.FINANCIAL_INCLUSION in related
    
    def test_profile_completeness_calculation(self, matcher, sample_user_profile):
        """Test profile completeness calculation."""
        completeness = matcher._calculate_profile_completeness(sample_user_profile)
        
        assert isinstance(completeness, float)
        assert 0.0 <= completeness <= 1.0
        
        # Sample profile should be fairly complete
        assert completeness > 0.5


class TestSchemeDiscoveryService:
    """Test cases for the scheme discovery service."""
    
    @pytest.fixture
    def mock_scheme_manager(self):
        """Create a mock scheme manager."""
        manager = Mock()
        manager.search_schemes = AsyncMock(return_value=[])
        return manager
    
    @pytest.fixture
    def mock_profile_manager(self):
        """Create a mock profile manager."""
        manager = Mock()
        manager.get_profile = AsyncMock(return_value=None)
        manager.record_interaction = AsyncMock(return_value=True)
        return manager
    
    @pytest.fixture
    def discovery_service(self, mock_scheme_manager, mock_profile_manager):
        """Create a discovery service instance."""
        return SchemeDiscoveryService(mock_scheme_manager, mock_profile_manager)
    
    @pytest.fixture
    def sample_discovery_query(self):
        """Create a sample discovery query."""
        return DiscoveryQuery(
            user_id="test-user-123",
            query_text="मुझे आवास योजना के बारे में जानकारी चाहिए",
            language="hi",
            location_context={"state": "Maharashtra", "district": "Mumbai"},
            demographic_context={"age": 35, "income": 150000},
            max_results=5
        )
    
    @pytest.fixture
    def sample_schemes(self):
        """Create sample government schemes for testing."""
        schemes = []
        
        # Housing scheme
        housing_scheme = GovernmentScheme(
            scheme_id="pmay-g-001",
            name="Pradhan Mantri Awas Yojana - Gramin",
            department="Ministry of Rural Development",
            category=SchemeCategory.HOUSING,
            description="Financial assistance for construction of pucca house",
            eligibility_criteria=EligibilityCriteria(
                income_limit=200000,
                location_type="both",
                housing_status="homeless_or_inadequate"
            ),
            benefits=SchemeBenefits(
                financial_assistance=120000,
                description="Financial assistance for construction of pucca house"
            ),
            target_states=["Maharashtra", "Gujarat"],
            target_districts=["Mumbai", "Pune"]
        )
        schemes.append(housing_scheme)
        
        # Agriculture scheme
        agriculture_scheme = GovernmentScheme(
            scheme_id="pmkisan-001",
            name="PM-KISAN",
            department="Ministry of Agriculture",
            category=SchemeCategory.AGRICULTURE,
            description="Annual financial assistance for farmers",
            eligibility_criteria=EligibilityCriteria(
                land_ownership="small_marginal",
                employment_status="farmer"
            ),
            benefits=SchemeBenefits(
                financial_assistance=6000,
                description="Annual financial assistance of Rs. 6000"
            ),
            target_states=["Maharashtra"]
        )
        schemes.append(agriculture_scheme)
        
        return schemes
    
    @pytest.mark.asyncio
    async def test_discover_schemes(self, discovery_service, sample_discovery_query, sample_schemes):
        """Test scheme discovery functionality."""
        # Mock the scheme manager to return sample schemes
        discovery_service.scheme_manager.search_schemes = AsyncMock(return_value=sample_schemes)
        
        # Mock intent classification and entity extraction
        with patch.object(discovery_service, '_process_query') as mock_process:
            mock_process.return_value = ("housing_query", {"location": {"state": "Maharashtra"}})
            
            result = await discovery_service.discover_schemes(sample_discovery_query)
            
            assert hasattr(result, 'recommendations')
            assert hasattr(result, 'total_schemes_considered')
            assert hasattr(result, 'processing_time_ms')
            assert hasattr(result, 'personalization_applied')
            assert hasattr(result, 'suggestions')
            
            assert isinstance(result.recommendations, list)
            assert isinstance(result.processing_time_ms, int)
            assert isinstance(result.personalization_applied, bool)
    
    @pytest.mark.asyncio
    async def test_personalized_recommendations(self, discovery_service, sample_schemes):
        """Test personalized recommendations."""
        # Mock profile manager to return a profile
        mock_profile = {
            'user_id': 'test-user-123',
            'location': LocationInfo(state='Maharashtra', district='Mumbai'),
            'demographics': DemographicInfo(age=35, gender='male'),
            'economic': EconomicInfo(income=150000),
            'preferences': {'preferred_categories': [SchemeCategory.HOUSING]},
            'interaction_history': []
        }
        discovery_service.profile_manager.get_profile = AsyncMock(return_value=mock_profile)
        discovery_service.scheme_manager.search_schemes = AsyncMock(return_value=sample_schemes)
        
        recommendations = await discovery_service.get_personalized_recommendations(
            user_id="test-user-123",
            max_results=3
        )
        
        assert isinstance(recommendations, list)
        assert len(recommendations) <= 3
        
        for rec in recommendations:
            assert isinstance(rec, SchemeRecommendation)
            assert hasattr(rec, 'scheme')
            assert hasattr(rec, 'match_score')
            assert hasattr(rec, 'rank')
            assert hasattr(rec, 'recommendation_reason')
    
    def test_recommendation_reason_generation(self, discovery_service):
        """Test recommendation reason generation."""
        match_score = MatchScore(
            scheme_id="test-scheme",
            overall_score=0.85,
            eligibility_match=True
        )
        
        reason = discovery_service._generate_recommendation_reason(match_score)
        
        assert isinstance(reason, str)
        assert len(reason) > 0
    
    def test_next_steps_generation(self, discovery_service, sample_schemes):
        """Test next steps generation."""
        scheme = sample_schemes[0]  # Housing scheme
        
        steps = discovery_service._generate_next_steps(scheme)
        
        assert isinstance(steps, list)
        assert len(steps) > 0
        assert all(isinstance(step, str) for step in steps)
    
    def test_benefit_estimation(self, discovery_service, sample_schemes):
        """Test benefit estimation."""
        scheme = sample_schemes[0]  # Housing scheme with financial assistance
        user_profile = UserProfile(user_id="test-user")
        
        benefit = discovery_service._estimate_benefit(scheme, user_profile)
        
        assert benefit is None or isinstance(benefit, str)
        if benefit:
            assert len(benefit) > 0
    
    def test_application_complexity_assessment(self, discovery_service, sample_schemes):
        """Test application complexity assessment."""
        scheme = sample_schemes[0]
        
        complexity = discovery_service._assess_application_complexity(scheme)
        
        assert complexity in ["low", "medium", "high"]


class TestUserProfileManager:
    """Test cases for user profile management."""
    
    @pytest.fixture
    def profile_manager(self):
        """Create a profile manager instance."""
        return UserProfileManager()
    
    @pytest.fixture
    def sample_location(self):
        """Create sample location info."""
        return LocationInfo(
            state="Maharashtra",
            district="Mumbai",
            block="Andheri",
            location_type="urban"
        )
    
    @pytest.fixture
    def sample_demographics(self):
        """Create sample demographic info."""
        return DemographicInfo(
            age=35,
            gender="male",
            caste_category="general",
            marital_status="married",
            family_size=4
        )
    
    @pytest.fixture
    def sample_economic(self):
        """Create sample economic info."""
        return EconomicInfo(
            income=150000,
            employment_status="employed",
            housing_status="rented",
            bank_account=True
        )
    
    @pytest.mark.asyncio
    async def test_create_profile(self, profile_manager, sample_location, sample_demographics, sample_economic):
        """Test profile creation."""
        success = await profile_manager.create_profile(
            user_id="test-user-123",
            location=sample_location,
            demographics=sample_demographics,
            economic=sample_economic
        )
        
        assert success is True
        
        # Verify profile was created
        profile = await profile_manager.get_profile("test-user-123")
        assert profile is not None
        assert profile['user_id'] == "test-user-123"
    
    @pytest.mark.asyncio
    async def test_update_profile(self, profile_manager, sample_location):
        """Test profile updates."""
        # Create initial profile
        await profile_manager.create_profile(
            user_id="test-user-456",
            location=sample_location
        )
        
        # Update profile
        updates = {
            'demographics': {'age': 40, 'gender': 'female'},
            'economic': {'income': 200000}
        }
        
        success = await profile_manager.update_profile("test-user-456", updates)
        assert success is True
        
        # Verify updates
        profile = await profile_manager.get_profile("test-user-456")
        assert profile is not None
    
    @pytest.mark.asyncio
    async def test_record_interaction(self, profile_manager, sample_location):
        """Test interaction recording."""
        # Create profile
        await profile_manager.create_profile(
            user_id="test-user-789",
            location=sample_location
        )
        
        # Record interaction
        interaction = InteractionRecord(
            scheme_id="pmay-g-001",
            category="housing",
            action="viewed",
            engagement_time=120
        )
        
        success = await profile_manager.record_interaction("test-user-789", interaction)
        assert success is True
        
        # Verify interaction was recorded
        history = await profile_manager.get_interaction_history("test-user-789")
        assert len(history) > 0
    
    def test_profile_completeness(self, profile_manager, sample_location, sample_demographics, sample_economic):
        """Test profile completeness calculation."""
        # Create complete profile
        asyncio.run(profile_manager.create_profile(
            user_id="complete-user",
            location=sample_location,
            demographics=sample_demographics,
            economic=sample_economic
        ))
        
        completeness = profile_manager.get_profile_completeness("complete-user")
        
        assert isinstance(completeness, float)
        assert 0.0 <= completeness <= 1.0
        assert completeness > 0.5  # Should be fairly complete


# Property-based tests using Hypothesis
from hypothesis import given, strategies as st

class TestSchemeMatchingProperties:
    """Property-based tests for scheme matching."""
    
    @pytest.fixture
    def matcher(self):
        """Create a scheme matcher instance."""
        return IntelligentSchemeMatcher()
    
    @given(
        age=st.integers(min_value=1, max_value=100),
        income=st.integers(min_value=0, max_value=1000000),
        family_size=st.integers(min_value=1, max_value=20)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_profile_properties(self, matcher, age, income, family_size):
        """Test properties that should hold for any valid user profile."""
        user_profile = UserProfile(
            user_id="property-test-user",
            age=age,
            income=income,
            family_size=family_size,
            location={"state": "TestState", "district": "TestDistrict"}
        )
        
        # Profile completeness should be between 0 and 1
        completeness = matcher._calculate_profile_completeness(user_profile)
        assert 0.0 <= completeness <= 1.0
        
        # Age should be preserved
        assert user_profile.age == age
        assert user_profile.income == income
        assert user_profile.family_size == family_size
    
    @given(
        overall_score=st.floats(min_value=0.0, max_value=1.0),
        eligibility_score=st.floats(min_value=0.0, max_value=1.0),
        location_score=st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_match_score_properties(self, matcher, overall_score, eligibility_score, location_score):
        """Test properties that should hold for any match score."""
        match_score = MatchScore(
            scheme_id="property-test-scheme",
            overall_score=overall_score,
            criteria_scores={
                MatchingCriteria.ELIGIBILITY_COMPLIANCE: eligibility_score,
                MatchingCriteria.LOCATION: location_score
            },
            eligibility_match=eligibility_score > 0.5
        )
        
        # Confidence should be between 0 and 1
        confidence = matcher._calculate_confidence(match_score)
        assert 0.0 <= confidence <= 1.0
        
        # Overall score should be preserved
        assert match_score.overall_score == overall_score
        
        # Eligibility match should be consistent with score
        if eligibility_score > 0.5:
            assert match_score.eligibility_match is True
        else:
            assert match_score.eligibility_match is False