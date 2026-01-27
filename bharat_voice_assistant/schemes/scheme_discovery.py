"""
Scheme discovery service with intelligent matching.

This module provides the main interface for discovering relevant government schemes
using the intelligent matching algorithm, with support for natural language queries
and personalized recommendations.

Requirements: 2.1, 2.4, 2.5
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from .scheme_matcher import IntelligentSchemeMatcher, UserProfile, MatchScore
from .user_profile import UserProfileManager, InteractionRecord
from .models import GovernmentScheme, SchemeCategory
from .user_profile import UserProfileManager, InteractionRecord
from ..core.exceptions import SchemeDiscoveryError
from ..language.intent_classifier import IntentClassifier
from ..language.entity_extractor import EntityExtractor

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryQuery:
    """User query for scheme discovery."""
    user_id: str
    query_text: str
    language: str = 'hi'
    location_context: Optional[Dict[str, str]] = None
    demographic_context: Optional[Dict[str, Any]] = None
    max_results: int = 10
    include_explanations: bool = True


@dataclass
class SchemeRecommendation:
    """Scheme recommendation with matching details."""
    scheme: GovernmentScheme
    match_score: MatchScore
    rank: int
    recommendation_reason: str
    next_steps: List[str] = field(default_factory=list)
    estimated_benefit: Optional[str] = None
    application_complexity: str = "medium"  # low, medium, high


@dataclass
class DiscoveryResult:
    """Result of scheme discovery operation."""
    query: DiscoveryQuery
    recommendations: List[SchemeRecommendation]
    total_schemes_considered: int
    processing_time_ms: int
    personalization_applied: bool = False
    suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class SchemeDiscoveryService:
    """
    Intelligent scheme discovery service.
    
    Provides natural language query processing, intelligent matching,
    and personalized recommendations for government schemes.
    """
    
    def __init__(self, 
                 scheme_manager=None,
                 profile_manager: Optional[UserProfileManager] = None):
        """
        Initialize the scheme discovery service.
        
        Args:
            scheme_manager: Scheme management service
            profile_manager: User profile management service
        """
        self.scheme_manager = scheme_manager  # Will be injected to avoid circular import
        self.profile_manager = profile_manager or UserProfileManager()
        self.matcher = IntelligentSchemeMatcher()
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        
        logger.info("Initialized SchemeDiscoveryService")
    
    async def discover_schemes(self, query: DiscoveryQuery) -> DiscoveryResult:
        """
        Discover relevant schemes based on user query.
        
        Args:
            query: Discovery query with user requirements
            
        Returns:
            Discovery result with ranked recommendations
        """
        start_time = datetime.now()
        
        try:
            # 1. Process natural language query
            intent, entities = await self._process_query(query)
            
            # 2. Get or create user profile
            user_profile = await self._get_user_profile(query, entities)
            
            # 3. Get available schemes
            available_schemes = await self._get_available_schemes(query, intent, entities)
            
            # 4. Apply intelligent matching
            match_results = await self.matcher.match_schemes(
                user_profile=user_profile,
                available_schemes=available_schemes,
                max_results=query.max_results * 2  # Get more for filtering
            )
            
            # 5. Create recommendations
            recommendations = await self._create_recommendations(
                match_results, query, user_profile
            )
            
            # 6. Record interaction
            await self._record_discovery_interaction(query, recommendations)
            
            # 7. Generate suggestions
            suggestions = await self._generate_suggestions(query, recommendations)
            
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            result = DiscoveryResult(
                query=query,
                recommendations=recommendations[:query.max_results],
                total_schemes_considered=len(available_schemes),
                processing_time_ms=processing_time,
                personalization_applied=len(user_profile.interaction_history) > 0,
                suggestions=suggestions
            )
            
            logger.info(f"Discovered {len(result.recommendations)} schemes for user {query.user_id} "
                       f"in {processing_time}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Error discovering schemes: {str(e)}")
            raise SchemeDiscoveryError(f"Failed to discover schemes: {str(e)}")
    
    async def get_personalized_recommendations(self, 
                                             user_id: str,
                                             max_results: int = 5) -> List[SchemeRecommendation]:
        """
        Get personalized scheme recommendations for a user.
        
        Args:
            user_id: User identifier
            max_results: Maximum number of recommendations
            
        Returns:
            List of personalized recommendations
        """
        try:
            # Get user profile
            profile_data = await self.profile_manager.get_profile(user_id)
            if not profile_data:
                logger.warning(f"No profile found for user {user_id}")
                return []
            
            user_profile = self._convert_to_user_profile(profile_data)
            
            # Get all active schemes
            all_schemes = await self.scheme_manager.search_schemes("", {"status": "active"})
            
            # Apply intelligent matching
            match_results = await self.matcher.match_schemes(
                user_profile=user_profile,
                available_schemes=all_schemes,
                max_results=max_results
            )
            
            # Create recommendations
            recommendations = []
            for rank, (scheme, match_score) in enumerate(match_results, 1):
                recommendation = SchemeRecommendation(
                    scheme=scheme,
                    match_score=match_score,
                    rank=rank,
                    recommendation_reason=self._generate_recommendation_reason(match_score),
                    next_steps=self._generate_next_steps(scheme),
                    estimated_benefit=self._estimate_benefit(scheme, user_profile),
                    application_complexity=self._assess_application_complexity(scheme)
                )
                recommendations.append(recommendation)
            
            logger.info(f"Generated {len(recommendations)} personalized recommendations for user {user_id}")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {str(e)}")
            return []
    
    async def _process_query(self, query: DiscoveryQuery) -> Tuple[str, Dict[str, Any]]:
        """Process natural language query to extract intent and entities."""
        try:
            # Classify intent
            intent_result = self.intent_classifier.classify_intent(query.query_text, query.language)
            intent = intent_result.intent
            
            # Extract entities
            entities = self.entity_extractor.extract_entities(query.query_text, query.language)
            
            logger.debug(f"Processed query: intent={intent}, entities={list(entities.keys())}")
            return intent, entities
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return "scheme_search", {}
    
    async def _get_user_profile(self, 
                              query: DiscoveryQuery, 
                              entities: Dict[str, Any]) -> UserProfile:
        """Get or create user profile for matching."""
        try:
            # Try to get existing profile
            profile_data = await self.profile_manager.get_profile(query.user_id)
            
            if profile_data:
                user_profile = self._convert_to_user_profile(profile_data)
            else:
                # Create basic profile from query context
                user_profile = UserProfile(
                    user_id=query.user_id,
                    location=query.location_context or {},
                    **query.demographic_context or {}
                )
            
            # Update profile with extracted entities
            self._update_profile_from_entities(user_profile, entities)
            
            return user_profile
            
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return UserProfile(user_id=query.user_id)
    
    async def _get_available_schemes(self, 
                                   query: DiscoveryQuery,
                                   intent: str,
                                   entities: Dict[str, Any]) -> List[GovernmentScheme]:
        """Get available schemes based on query context."""
        try:
            # Build search filters
            filters = {"status": "active"}
            
            # Add location filters
            if query.location_context:
                state = query.location_context.get('state')
                if state:
                    filters['state'] = state
            
            # Add category filters based on intent and entities
            if intent == "agriculture_query" or "farming" in entities:
                filters['category'] = SchemeCategory.AGRICULTURE.value
            elif intent == "housing_query" or "house" in entities:
                filters['category'] = SchemeCategory.HOUSING.value
            elif intent == "education_query" or "education" in entities:
                filters['category'] = SchemeCategory.EDUCATION.value
            elif intent == "health_query" or "health" in entities:
                filters['category'] = SchemeCategory.HEALTH.value
            
            # Search schemes
            schemes = await self.scheme_manager.search_schemes(query.query_text, filters)
            
            # If no specific results, get all active schemes
            if not schemes:
                schemes = await self.scheme_manager.search_schemes("", {"status": "active"})
            
            logger.debug(f"Found {len(schemes)} available schemes")
            return schemes
            
        except Exception as e:
            logger.error(f"Error getting available schemes: {str(e)}")
            return []
    
    async def _create_recommendations(self, 
                                    match_results: List[Tuple[GovernmentScheme, MatchScore]],
                                    query: DiscoveryQuery,
                                    user_profile: UserProfile) -> List[SchemeRecommendation]:
        """Create detailed recommendations from match results."""
        try:
            recommendations = []
            
            for rank, (scheme, match_score) in enumerate(match_results, 1):
                recommendation = SchemeRecommendation(
                    scheme=scheme,
                    match_score=match_score,
                    rank=rank,
                    recommendation_reason=self._generate_recommendation_reason(match_score),
                    next_steps=self._generate_next_steps(scheme),
                    estimated_benefit=self._estimate_benefit(scheme, user_profile),
                    application_complexity=self._assess_application_complexity(scheme)
                )
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error creating recommendations: {str(e)}")
            return []
    
    async def _record_discovery_interaction(self, 
                                          query: DiscoveryQuery,
                                          recommendations: List[SchemeRecommendation]):
        """Record the discovery interaction for personalization."""
        try:
            if not recommendations:
                return
            
            # Record interaction for top recommendation
            top_recommendation = recommendations[0]
            interaction = InteractionRecord(
                scheme_id=top_recommendation.scheme.scheme_id,
                category=top_recommendation.scheme.category.value,
                action='discovered',
                engagement_time=0,
                metadata={
                    'query': query.query_text,
                    'rank': 1,
                    'match_score': top_recommendation.match_score.overall_score
                }
            )
            
            await self.profile_manager.record_interaction(query.user_id, interaction)
            
        except Exception as e:
            logger.error(f"Error recording discovery interaction: {str(e)}")
    
    async def _generate_suggestions(self, 
                                  query: DiscoveryQuery,
                                  recommendations: List[SchemeRecommendation]) -> List[str]:
        """Generate helpful suggestions for the user."""
        try:
            suggestions = []
            
            if not recommendations:
                suggestions.append("Try providing more details about your situation")
                suggestions.append("Check if you meet the basic eligibility criteria")
                return suggestions
            
            # Suggest profile completion if needed
            profile_data = await self.profile_manager.get_profile(query.user_id)
            if profile_data:
                completeness = self.profile_manager.get_profile_completeness(query.user_id)
                if completeness < 0.7:
                    suggestions.append("Complete your profile for better recommendations")
            
            # Suggest related categories
            top_category = recommendations[0].scheme.category
            related_categories = self.matcher._get_related_categories(top_category)
            if related_categories:
                category_names = [cat.value.replace('_', ' ').title() for cat in related_categories]
                suggestions.append(f"Also explore: {', '.join(category_names[:2])}")
            
            # Suggest application preparation
            if any(rec.application_complexity == "high" for rec in recommendations[:3]):
                suggestions.append("Consider getting help with application process")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {str(e)}")
            return []
    
    def _convert_to_user_profile(self, profile_data: Dict[str, Any]) -> UserProfile:
        """Convert profile data to UserProfile object."""
        try:
            location = profile_data.get('location', {})
            demographics = profile_data.get('demographics', {})
            economic = profile_data.get('economic', {})
            preferences = profile_data.get('preferences', {})
            
            # Convert interaction history
            interaction_history = []
            for interaction_data in profile_data.get('interaction_history', []):
                if hasattr(interaction_data, '__dict__'):
                    # Already an InteractionRecord object
                    interaction_history.append(interaction_data.__dict__)
                else:
                    # Convert from dict
                    interaction_history.append(interaction_data)
            
            user_profile = UserProfile(
                user_id=profile_data['user_id'],
                age=getattr(demographics, 'age', None) if hasattr(demographics, 'age') else demographics.get('age'),
                gender=getattr(demographics, 'gender', None) if hasattr(demographics, 'gender') else demographics.get('gender'),
                income=getattr(economic, 'income', None) if hasattr(economic, 'income') else economic.get('income'),
                location={
                    'state': getattr(location, 'state', '') if hasattr(location, 'state') else location.get('state', ''),
                    'district': getattr(location, 'district', '') if hasattr(location, 'district') else location.get('district', ''),
                    'type': getattr(location, 'location_type', 'unknown') if hasattr(location, 'location_type') else location.get('location_type', 'unknown')
                },
                education_level=getattr(demographics, 'education_level', None) if hasattr(demographics, 'education_level') else demographics.get('education_level'),
                employment_status=getattr(economic, 'employment_status', None) if hasattr(economic, 'employment_status') else economic.get('employment_status'),
                caste_category=getattr(demographics, 'caste_category', None) if hasattr(demographics, 'caste_category') else demographics.get('caste_category'),
                disability_status=getattr(demographics, 'disability_status', None) if hasattr(demographics, 'disability_status') else demographics.get('disability_status'),
                marital_status=getattr(demographics, 'marital_status', None) if hasattr(demographics, 'marital_status') else demographics.get('marital_status'),
                family_size=getattr(demographics, 'family_size', None) if hasattr(demographics, 'family_size') else demographics.get('family_size'),
                land_ownership=getattr(economic, 'land_ownership', None) if hasattr(economic, 'land_ownership') else economic.get('land_ownership'),
                housing_status=getattr(economic, 'housing_status', None) if hasattr(economic, 'housing_status') else economic.get('housing_status'),
                preferred_categories=getattr(preferences, 'preferred_categories', []) if hasattr(preferences, 'preferred_categories') else preferences.get('preferred_categories', []),
                interaction_history=interaction_history
            )
            
            return user_profile
            
        except Exception as e:
            logger.error(f"Error converting profile data: {str(e)}")
            return UserProfile(user_id=profile_data.get('user_id', 'unknown'))
    
    def _update_profile_from_entities(self, user_profile: UserProfile, entities: Dict[str, Any]):
        """Update user profile with extracted entities."""
        try:
            # Update location if mentioned
            if 'location' in entities:
                location_info = entities['location']
                if isinstance(location_info, dict):
                    user_profile.location.update(location_info)
            
            # Update demographics if mentioned
            if 'age' in entities:
                user_profile.age = entities['age']
            
            if 'gender' in entities:
                user_profile.gender = entities['gender']
            
            # Update economic info if mentioned
            if 'income' in entities:
                user_profile.income = entities['income']
            
            if 'occupation' in entities:
                user_profile.employment_status = entities['occupation']
            
        except Exception as e:
            logger.error(f"Error updating profile from entities: {str(e)}")
    
    def _generate_recommendation_reason(self, match_score: MatchScore) -> str:
        """Generate human-readable recommendation reason."""
        try:
            if match_score.overall_score > 0.8:
                return "Excellent match for your profile and needs"
            elif match_score.overall_score > 0.6:
                return "Good match based on your eligibility and location"
            elif match_score.overall_score > 0.4:
                return "Potential match worth exploring"
            else:
                return "Limited match but may still be relevant"
                
        except Exception as e:
            logger.error(f"Error generating recommendation reason: {str(e)}")
            return "Recommended based on your profile"
    
    def _generate_next_steps(self, scheme: GovernmentScheme) -> List[str]:
        """Generate next steps for applying to a scheme."""
        try:
            steps = []
            
            # Add document preparation step
            if scheme.application_process.required_documents:
                steps.append(f"Gather required documents: {', '.join(scheme.application_process.required_documents[:3])}")
            
            # Add application step
            if 'online' in scheme.application_process.application_mode:
                steps.append("Apply online through the official portal")
            elif 'offline' in scheme.application_process.application_mode:
                steps.append("Visit the nearest government office to apply")
            else:
                steps.append("Contact the implementing department for application process")
            
            # Add follow-up step
            if scheme.application_process.processing_time_days:
                steps.append(f"Track application status after {scheme.application_process.processing_time_days} days")
            else:
                steps.append("Follow up on application status regularly")
            
            return steps
            
        except Exception as e:
            logger.error(f"Error generating next steps: {str(e)}")
            return ["Contact the implementing department for more information"]
    
    def _estimate_benefit(self, scheme: GovernmentScheme, user_profile: UserProfile) -> Optional[str]:
        """Estimate potential benefit for the user."""
        try:
            if scheme.benefits.financial_assistance:
                amount = scheme.benefits.financial_assistance
                if amount >= 100000:
                    return f"₹{amount:,} financial assistance"
                else:
                    return f"₹{amount:,} support"
            
            if scheme.benefits.subsidy_percentage:
                return f"{scheme.benefits.subsidy_percentage}% subsidy"
            
            if scheme.benefits.loan_amount:
                return f"Loan up to ₹{scheme.benefits.loan_amount:,}"
            
            if scheme.benefits.description:
                return scheme.benefits.description[:50] + "..."
            
            return None
            
        except Exception as e:
            logger.error(f"Error estimating benefit: {str(e)}")
            return None
    
    def _assess_application_complexity(self, scheme: GovernmentScheme) -> str:
        """Assess the complexity of applying to a scheme."""
        try:
            complexity_score = 0
            
            # Document requirements
            doc_count = len(scheme.application_process.required_documents)
            if doc_count > 5:
                complexity_score += 2
            elif doc_count > 2:
                complexity_score += 1
            
            # Application steps
            step_count = len(scheme.application_process.steps)
            if step_count > 5:
                complexity_score += 2
            elif step_count > 3:
                complexity_score += 1
            
            # Processing time
            if scheme.application_process.processing_time_days:
                if scheme.application_process.processing_time_days > 60:
                    complexity_score += 1
            
            # Application fee
            if scheme.application_process.application_fee and scheme.application_process.application_fee > 500:
                complexity_score += 1
            
            if complexity_score >= 4:
                return "high"
            elif complexity_score >= 2:
                return "medium"
            else:
                return "low"
                
        except Exception as e:
            logger.error(f"Error assessing application complexity: {str(e)}")
            return "medium"