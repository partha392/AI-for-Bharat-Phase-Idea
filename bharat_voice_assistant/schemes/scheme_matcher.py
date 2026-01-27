"""
Intelligent scheme matching algorithm for the Bharat Voice Assistant.

This module implements multi-criteria matching based on demographics and location,
relevance scoring with machine learning models, and personalization based on user
interaction history.

Requirements: 2.1, 2.4, 2.5
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from .models import GovernmentScheme, SchemeCategory, EligibilityCriteria
from ..core.exceptions import SchemeMatchingError

logger = logging.getLogger(__name__)


class MatchingCriteria(Enum):
    """Criteria used for scheme matching."""
    DEMOGRAPHICS = "demographics"
    LOCATION = "location"
    INCOME = "income"
    CATEGORY_PREFERENCE = "category_preference"
    HISTORICAL_INTERACTION = "historical_interaction"
    ELIGIBILITY_COMPLIANCE = "eligibility_compliance"


@dataclass
class UserProfile:
    """User profile for scheme matching."""
    user_id: str
    age: Optional[int] = None
    gender: Optional[str] = None
    income: Optional[int] = None
    location: Dict[str, str] = field(default_factory=dict)  # state, district, block
    education_level: Optional[str] = None
    employment_status: Optional[str] = None
    caste_category: Optional[str] = None
    disability_status: Optional[bool] = None
    marital_status: Optional[str] = None
    family_size: Optional[int] = None
    land_ownership: Optional[str] = None
    housing_status: Optional[str] = None
    preferred_categories: List[SchemeCategory] = field(default_factory=list)
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class MatchScore:
    """Detailed matching score for a scheme."""
    scheme_id: str
    overall_score: float
    criteria_scores: Dict[MatchingCriteria, float] = field(default_factory=dict)
    eligibility_match: bool = True
    confidence: float = 0.0
    explanation: List[str] = field(default_factory=list)
    personalization_boost: float = 0.0
    approval_likelihood: float = 0.0


class IntelligentSchemeMatcher:
    """
    Intelligent scheme matching algorithm with ML-based relevance scoring.
    
    This class implements multi-criteria matching based on demographics, location,
    and user preferences, with machine learning models for relevance scoring and
    personalization based on user interaction history.
    """
    
    def __init__(self):
        """Initialize the scheme matcher."""
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.scaler = StandardScaler()
        
        # Weights for different matching criteria
        self.criteria_weights = {
            MatchingCriteria.ELIGIBILITY_COMPLIANCE: 0.35,
            MatchingCriteria.DEMOGRAPHICS: 0.20,
            MatchingCriteria.LOCATION: 0.15,
            MatchingCriteria.INCOME: 0.15,
            MatchingCriteria.CATEGORY_PREFERENCE: 0.10,
            MatchingCriteria.HISTORICAL_INTERACTION: 0.05
        }
        
        # Cache for TF-IDF vectors
        self._scheme_vectors = {}
        self._vectorizer_fitted = False
        
        logger.info("Initialized IntelligentSchemeMatcher")
    
    async def match_schemes(self, 
                          user_profile: UserProfile, 
                          available_schemes: List[GovernmentScheme],
                          max_results: int = 10) -> List[Tuple[GovernmentScheme, MatchScore]]:
        """
        Match schemes to user profile using intelligent multi-criteria algorithm.
        
        Args:
            user_profile: User profile with demographics and preferences
            available_schemes: List of available government schemes
            max_results: Maximum number of results to return
            
        Returns:
            List of tuples (scheme, match_score) sorted by relevance
        """
        try:
            if not available_schemes:
                logger.warning("No schemes available for matching")
                return []
            
            # Prepare scheme vectors for ML-based matching
            await self._prepare_scheme_vectors(available_schemes)
            
            # Calculate match scores for all schemes
            match_results = []
            for scheme in available_schemes:
                match_score = await self._calculate_match_score(user_profile, scheme)
                if match_score.overall_score > 0.1:  # Filter out very low scores
                    match_results.append((scheme, match_score))
            
            # Sort by overall score (descending) and approval likelihood
            match_results.sort(
                key=lambda x: (x[1].overall_score, x[1].approval_likelihood), 
                reverse=True
            )
            
            # Apply personalization boost
            match_results = await self._apply_personalization(user_profile, match_results)
            
            # Return top results
            top_results = match_results[:max_results]
            
            logger.info(f"Matched {len(top_results)} schemes for user {user_profile.user_id}")
            return top_results
            
        except Exception as e:
            logger.error(f"Error matching schemes: {str(e)}")
            raise SchemeMatchingError(f"Failed to match schemes: {str(e)}")
    
    async def _calculate_match_score(self, 
                                   user_profile: UserProfile, 
                                   scheme: GovernmentScheme) -> MatchScore:
        """Calculate comprehensive match score for a scheme."""
        try:
            match_score = MatchScore(
                scheme_id=scheme.scheme_id,
                overall_score=0.0
            )
            
            # 1. Eligibility compliance check
            eligibility_score, eligibility_match = self._check_eligibility_compliance(
                user_profile, scheme.eligibility_criteria
            )
            match_score.criteria_scores[MatchingCriteria.ELIGIBILITY_COMPLIANCE] = eligibility_score
            match_score.eligibility_match = eligibility_match
            
            if not eligibility_match:
                match_score.overall_score = 0.0
                match_score.explanation.append("User does not meet basic eligibility criteria")
                return match_score
            
            # 2. Demographics matching
            demographics_score = self._calculate_demographics_score(user_profile, scheme)
            match_score.criteria_scores[MatchingCriteria.DEMOGRAPHICS] = demographics_score
            
            # 3. Location matching
            location_score = self._calculate_location_score(user_profile, scheme)
            match_score.criteria_scores[MatchingCriteria.LOCATION] = location_score
            
            # 4. Income matching
            income_score = self._calculate_income_score(user_profile, scheme)
            match_score.criteria_scores[MatchingCriteria.INCOME] = income_score
            
            # 5. Category preference matching
            category_score = self._calculate_category_preference_score(user_profile, scheme)
            match_score.criteria_scores[MatchingCriteria.CATEGORY_PREFERENCE] = category_score
            
            # 6. Historical interaction score
            interaction_score = self._calculate_interaction_score(user_profile, scheme)
            match_score.criteria_scores[MatchingCriteria.HISTORICAL_INTERACTION] = interaction_score
            
            # Calculate weighted overall score
            overall_score = sum(
                score * self.criteria_weights[criteria]
                for criteria, score in match_score.criteria_scores.items()
            )
            match_score.overall_score = min(overall_score, 1.0)
            
            # Calculate approval likelihood
            match_score.approval_likelihood = self._calculate_approval_likelihood(
                user_profile, scheme, match_score
            )
            
            # Calculate confidence
            match_score.confidence = self._calculate_confidence(match_score)
            
            # Generate explanation
            match_score.explanation = self._generate_match_explanation(
                user_profile, scheme, match_score
            )
            
            return match_score
            
        except Exception as e:
            logger.error(f"Error calculating match score for scheme {scheme.scheme_id}: {str(e)}")
            return MatchScore(scheme_id=scheme.scheme_id, overall_score=0.0)
    
    def _check_eligibility_compliance(self, 
                                    user_profile: UserProfile, 
                                    criteria: EligibilityCriteria) -> Tuple[float, bool]:
        """Check if user meets eligibility criteria."""
        try:
            compliance_score = 0.0
            total_criteria = 0
            meets_all_mandatory = True
            
            # Age criteria
            if criteria.age_min is not None or criteria.age_max is not None:
                total_criteria += 1
                if user_profile.age is not None:
                    age_match = True
                    if criteria.age_min and user_profile.age < criteria.age_min:
                        age_match = False
                        meets_all_mandatory = False
                    if criteria.age_max and user_profile.age > criteria.age_max:
                        age_match = False
                        meets_all_mandatory = False
                    
                    if age_match:
                        compliance_score += 1.0
                else:
                    # Missing age data - partial compliance
                    compliance_score += 0.5
            
            # Income criteria
            if criteria.income_limit is not None:
                total_criteria += 1
                if user_profile.income is not None:
                    if user_profile.income <= criteria.income_limit:
                        compliance_score += 1.0
                    else:
                        meets_all_mandatory = False
                else:
                    compliance_score += 0.5
            
            # Location type criteria
            if criteria.location_type is not None:
                total_criteria += 1
                user_location_type = user_profile.location.get('type', 'unknown')
                if criteria.location_type == 'both' or user_location_type == criteria.location_type:
                    compliance_score += 1.0
                elif user_location_type == 'unknown':
                    compliance_score += 0.5
                else:
                    meets_all_mandatory = False
            
            # Gender criteria
            if criteria.gender is not None:
                total_criteria += 1
                if user_profile.gender == criteria.gender or criteria.gender == 'any':
                    compliance_score += 1.0
                elif user_profile.gender is None:
                    compliance_score += 0.5
                else:
                    meets_all_mandatory = False
            
            # Caste category criteria
            if criteria.caste_category is not None and len(criteria.caste_category) > 0:
                total_criteria += 1
                if user_profile.caste_category in criteria.caste_category:
                    compliance_score += 1.0
                elif user_profile.caste_category is None:
                    compliance_score += 0.5
                else:
                    meets_all_mandatory = False
            
            # Education level criteria
            if criteria.education_level is not None:
                total_criteria += 1
                if self._education_level_matches(user_profile.education_level, criteria.education_level):
                    compliance_score += 1.0
                elif user_profile.education_level is None:
                    compliance_score += 0.5
                else:
                    compliance_score += 0.3  # Partial match for education
            
            # Employment status criteria
            if criteria.employment_status is not None:
                total_criteria += 1
                if user_profile.employment_status == criteria.employment_status:
                    compliance_score += 1.0
                elif user_profile.employment_status is None:
                    compliance_score += 0.5
                else:
                    compliance_score += 0.3
            
            # Disability status criteria
            if criteria.disability_status is not None:
                total_criteria += 1
                if user_profile.disability_status == criteria.disability_status:
                    compliance_score += 1.0
                elif user_profile.disability_status is None:
                    compliance_score += 0.5
                else:
                    meets_all_mandatory = False
            
            # Calculate final compliance score
            if total_criteria == 0:
                final_score = 1.0  # No specific criteria
            else:
                final_score = compliance_score / total_criteria
            
            return final_score, meets_all_mandatory
            
        except Exception as e:
            logger.error(f"Error checking eligibility compliance: {str(e)}")
            return 0.0, False
    
    def _calculate_demographics_score(self, 
                                    user_profile: UserProfile, 
                                    scheme: GovernmentScheme) -> float:
        """Calculate demographics matching score."""
        try:
            score = 0.0
            factors = 0
            
            # Age group alignment
            if user_profile.age is not None:
                factors += 1
                if scheme.category in [SchemeCategory.SENIOR_CITIZEN] and user_profile.age >= 60:
                    score += 1.0
                elif scheme.category in [SchemeCategory.EDUCATION] and 5 <= user_profile.age <= 25:
                    score += 1.0
                elif scheme.category in [SchemeCategory.EMPLOYMENT] and 18 <= user_profile.age <= 60:
                    score += 1.0
                else:
                    score += 0.7  # General age appropriateness
            
            # Gender alignment
            if user_profile.gender is not None:
                factors += 1
                if scheme.category == SchemeCategory.WOMEN_EMPOWERMENT:
                    if user_profile.gender == 'female':
                        score += 1.0
                    else:
                        score += 0.2
                else:
                    score += 0.8  # Gender neutral schemes
            
            # Family size considerations
            if user_profile.family_size is not None:
                factors += 1
                if scheme.category in [SchemeCategory.HOUSING, SchemeCategory.SOCIAL_SECURITY]:
                    if user_profile.family_size > 4:
                        score += 1.0  # Large families benefit more
                    else:
                        score += 0.8
                else:
                    score += 0.7
            
            return score / factors if factors > 0 else 0.5
            
        except Exception as e:
            logger.error(f"Error calculating demographics score: {str(e)}")
            return 0.0
    
    def _calculate_location_score(self, 
                                user_profile: UserProfile, 
                                scheme: GovernmentScheme) -> float:
        """Calculate location-based matching score."""
        try:
            score = 0.0
            
            user_state = user_profile.location.get('state', '').lower()
            user_district = user_profile.location.get('district', '').lower()
            
            # State-level matching
            if scheme.target_states:
                if any(state.lower() == user_state for state in scheme.target_states):
                    score += 0.6
                elif 'all' in [s.lower() for s in scheme.target_states]:
                    score += 0.8
                else:
                    score += 0.1  # Scheme not available in user's state
            else:
                score += 0.8  # No state restriction
            
            # District-level matching
            if scheme.target_districts:
                if any(district.lower() == user_district for district in scheme.target_districts):
                    score += 0.4
                else:
                    score += 0.2  # Scheme not available in user's district
            else:
                score += 0.4  # No district restriction
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating location score: {str(e)}")
            return 0.0
    
    def _calculate_income_score(self, 
                              user_profile: UserProfile, 
                              scheme: GovernmentScheme) -> float:
        """Calculate income-based matching score."""
        try:
            if user_profile.income is None:
                return 0.5  # Unknown income
            
            income_limit = scheme.eligibility_criteria.income_limit
            if income_limit is None:
                return 0.8  # No income restriction
            
            # Calculate score based on how well income fits the scheme
            income_ratio = user_profile.income / income_limit
            
            if income_ratio <= 0.5:
                return 1.0  # Well below limit
            elif income_ratio <= 0.8:
                return 0.9  # Comfortably below limit
            elif income_ratio <= 1.0:
                return 0.7  # Just within limit
            else:
                return 0.0  # Above limit
                
        except Exception as e:
            logger.error(f"Error calculating income score: {str(e)}")
            return 0.0
    
    def _calculate_category_preference_score(self, 
                                           user_profile: UserProfile, 
                                           scheme: GovernmentScheme) -> float:
        """Calculate category preference matching score."""
        try:
            if not user_profile.preferred_categories:
                return 0.5  # No preferences specified
            
            if scheme.category in user_profile.preferred_categories:
                return 1.0
            
            # Check for related categories
            related_categories = self._get_related_categories(scheme.category)
            for pref_category in user_profile.preferred_categories:
                if pref_category in related_categories:
                    return 0.7
            
            return 0.3  # Not in preferred categories
            
        except Exception as e:
            logger.error(f"Error calculating category preference score: {str(e)}")
            return 0.0
    
    def _calculate_interaction_score(self, 
                                   user_profile: UserProfile, 
                                   scheme: GovernmentScheme) -> float:
        """Calculate score based on user interaction history."""
        try:
            if not user_profile.interaction_history:
                return 0.5  # No history
            
            score = 0.5
            recent_interactions = [
                interaction for interaction in user_profile.interaction_history
                if self._is_recent_interaction(interaction)
            ]
            
            # Check for similar scheme interactions
            for interaction in recent_interactions:
                interaction_category = interaction.get('category')
                if interaction_category == scheme.category.value:
                    if interaction.get('outcome') == 'applied':
                        score += 0.3
                    elif interaction.get('outcome') == 'viewed':
                        score += 0.1
                elif interaction_category in [cat.value for cat in self._get_related_categories(scheme.category)]:
                    score += 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating interaction score: {str(e)}")
            return 0.0
    
    def _calculate_approval_likelihood(self, 
                                     user_profile: UserProfile, 
                                     scheme: GovernmentScheme, 
                                     match_score: MatchScore) -> float:
        """Calculate likelihood of scheme approval based on various factors."""
        try:
            likelihood = 0.5  # Base likelihood
            
            # Factor in eligibility compliance
            eligibility_score = match_score.criteria_scores.get(MatchingCriteria.ELIGIBILITY_COMPLIANCE, 0.0)
            likelihood += eligibility_score * 0.3
            
            # Factor in scheme success rate
            if scheme.metadata.success_rate > 0:
                likelihood += scheme.metadata.success_rate * 0.2
            
            # Factor in completeness of user profile
            profile_completeness = self._calculate_profile_completeness(user_profile)
            likelihood += profile_completeness * 0.1
            
            # Factor in scheme popularity (inverse relationship - less popular might be easier)
            if scheme.metadata.popularity_score > 0:
                popularity_factor = 1.0 - min(scheme.metadata.popularity_score / 100.0, 0.3)
                likelihood += popularity_factor * 0.1
            
            return min(likelihood, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating approval likelihood: {str(e)}")
            return 0.5
    
    def _calculate_confidence(self, match_score: MatchScore) -> float:
        """Calculate confidence in the matching result."""
        try:
            # Base confidence on the number of criteria with high scores
            high_score_criteria = sum(
                1 for score in match_score.criteria_scores.values() 
                if score > 0.7
            )
            total_criteria = len(match_score.criteria_scores)
            
            if total_criteria == 0:
                return 0.0
            
            confidence = high_score_criteria / total_criteria
            
            # Boost confidence if eligibility is clearly met
            if match_score.eligibility_match and match_score.criteria_scores.get(MatchingCriteria.ELIGIBILITY_COMPLIANCE, 0) > 0.8:
                confidence += 0.2
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {str(e)}")
            return 0.0
    
    def _generate_match_explanation(self, 
                                  user_profile: UserProfile, 
                                  scheme: GovernmentScheme, 
                                  match_score: MatchScore) -> List[str]:
        """Generate human-readable explanation for the match."""
        try:
            explanations = []
            
            # Eligibility explanation
            eligibility_score = match_score.criteria_scores.get(MatchingCriteria.ELIGIBILITY_COMPLIANCE, 0.0)
            if eligibility_score > 0.8:
                explanations.append("You meet all eligibility criteria for this scheme")
            elif eligibility_score > 0.5:
                explanations.append("You meet most eligibility criteria for this scheme")
            else:
                explanations.append("Limited eligibility match for this scheme")
            
            # Location explanation
            location_score = match_score.criteria_scores.get(MatchingCriteria.LOCATION, 0.0)
            if location_score > 0.8:
                explanations.append("This scheme is available in your area")
            elif location_score > 0.5:
                explanations.append("This scheme has limited availability in your area")
            
            # Demographics explanation
            demographics_score = match_score.criteria_scores.get(MatchingCriteria.DEMOGRAPHICS, 0.0)
            if demographics_score > 0.8:
                explanations.append("Your demographic profile is well-suited for this scheme")
            
            # Income explanation
            income_score = match_score.criteria_scores.get(MatchingCriteria.INCOME, 0.0)
            if income_score > 0.8:
                explanations.append("Your income level makes you a strong candidate")
            
            # Approval likelihood explanation
            if match_score.approval_likelihood > 0.8:
                explanations.append("High likelihood of approval based on your profile")
            elif match_score.approval_likelihood > 0.6:
                explanations.append("Good chances of approval")
            
            return explanations
            
        except Exception as e:
            logger.error(f"Error generating match explanation: {str(e)}")
            return ["Match explanation unavailable"]
    
    async def _apply_personalization(self, 
                                   user_profile: UserProfile, 
                                   match_results: List[Tuple[GovernmentScheme, MatchScore]]) -> List[Tuple[GovernmentScheme, MatchScore]]:
        """Apply personalization boost based on user interaction history."""
        try:
            # Calculate personalization boosts
            for scheme, match_score in match_results:
                boost = self._calculate_personalization_boost(user_profile, scheme)
                match_score.personalization_boost = boost
                
                # Apply boost to overall score
                original_score = match_score.overall_score
                boosted_score = original_score + (boost * 0.1)  # 10% max boost
                match_score.overall_score = min(boosted_score, 1.0)
            
            # Re-sort with personalization applied
            match_results.sort(
                key=lambda x: (x[1].overall_score, x[1].approval_likelihood), 
                reverse=True
            )
            
            return match_results
            
        except Exception as e:
            logger.error(f"Error applying personalization: {str(e)}")
            return match_results
    
    def _calculate_personalization_boost(self, 
                                       user_profile: UserProfile, 
                                       scheme: GovernmentScheme) -> float:
        """Calculate personalization boost for a scheme."""
        try:
            boost = 0.0
            
            # Boost based on recent category interactions
            recent_categories = self._get_recent_interaction_categories(user_profile)
            if scheme.category.value in recent_categories:
                boost += 0.3
            
            # Boost based on successful applications in similar categories
            successful_categories = self._get_successful_application_categories(user_profile)
            if scheme.category.value in successful_categories:
                boost += 0.5
            
            # Boost based on time spent on similar schemes
            time_spent_categories = self._get_high_engagement_categories(user_profile)
            if scheme.category.value in time_spent_categories:
                boost += 0.2
            
            return min(boost, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating personalization boost: {str(e)}")
            return 0.0
    
    async def _prepare_scheme_vectors(self, schemes: List[GovernmentScheme]):
        """Prepare TF-IDF vectors for ML-based matching."""
        try:
            if self._vectorizer_fitted and len(self._scheme_vectors) == len(schemes):
                return  # Already prepared
            
            # Prepare text corpus from schemes
            scheme_texts = []
            for scheme in schemes:
                text = f"{scheme.name} {scheme.description} {scheme.category.value}"
                if scheme.subcategory:
                    text += f" {scheme.subcategory}"
                scheme_texts.append(text)
            
            # Fit TF-IDF vectorizer
            if not self._vectorizer_fitted:
                self.tfidf_vectorizer.fit(scheme_texts)
                self._vectorizer_fitted = True
            
            # Transform schemes to vectors
            scheme_vectors = self.tfidf_vectorizer.transform(scheme_texts)
            
            # Store vectors
            self._scheme_vectors = {
                scheme.scheme_id: scheme_vectors[i].toarray()[0]
                for i, scheme in enumerate(schemes)
            }
            
            logger.debug(f"Prepared TF-IDF vectors for {len(schemes)} schemes")
            
        except Exception as e:
            logger.error(f"Error preparing scheme vectors: {str(e)}")
    
    # Helper methods
    
    def _education_level_matches(self, user_education: Optional[str], required_education: str) -> bool:
        """Check if user education level matches requirement."""
        if user_education is None:
            return False
        
        education_hierarchy = {
            'illiterate': 0,
            'primary': 1,
            'secondary': 2,
            'higher_secondary': 3,
            'graduate': 4,
            'postgraduate': 5
        }
        
        user_level = education_hierarchy.get(user_education, 0)
        required_level = education_hierarchy.get(required_education, 0)
        
        return user_level >= required_level
    
    def _get_related_categories(self, category: SchemeCategory) -> Set[SchemeCategory]:
        """Get categories related to the given category."""
        related_map = {
            SchemeCategory.AGRICULTURE: {SchemeCategory.RURAL_DEVELOPMENT, SchemeCategory.FINANCIAL_INCLUSION},
            SchemeCategory.EDUCATION: {SchemeCategory.WOMEN_EMPOWERMENT, SchemeCategory.SOCIAL_SECURITY},
            SchemeCategory.HEALTH: {SchemeCategory.SENIOR_CITIZEN, SchemeCategory.DISABILITY, SchemeCategory.WOMEN_EMPOWERMENT},
            SchemeCategory.HOUSING: {SchemeCategory.RURAL_DEVELOPMENT, SchemeCategory.SOCIAL_SECURITY},
            SchemeCategory.EMPLOYMENT: {SchemeCategory.WOMEN_EMPOWERMENT, SchemeCategory.RURAL_DEVELOPMENT},
            SchemeCategory.SOCIAL_SECURITY: {SchemeCategory.SENIOR_CITIZEN, SchemeCategory.DISABILITY},
            SchemeCategory.RURAL_DEVELOPMENT: {SchemeCategory.AGRICULTURE, SchemeCategory.HOUSING},
            SchemeCategory.WOMEN_EMPOWERMENT: {SchemeCategory.EDUCATION, SchemeCategory.EMPLOYMENT, SchemeCategory.HEALTH},
            SchemeCategory.DISABILITY: {SchemeCategory.HEALTH, SchemeCategory.SOCIAL_SECURITY},
            SchemeCategory.SENIOR_CITIZEN: {SchemeCategory.HEALTH, SchemeCategory.SOCIAL_SECURITY},
            SchemeCategory.FINANCIAL_INCLUSION: {SchemeCategory.AGRICULTURE, SchemeCategory.EMPLOYMENT}
        }
        
        return related_map.get(category, set())
    
    def _is_recent_interaction(self, interaction: Dict[str, Any]) -> bool:
        """Check if interaction is recent (within last 30 days)."""
        try:
            interaction_date = datetime.fromisoformat(interaction.get('timestamp', ''))
            return datetime.now() - interaction_date <= timedelta(days=30)
        except:
            return False
    
    def _calculate_profile_completeness(self, user_profile: UserProfile) -> float:
        """Calculate completeness of user profile."""
        total_fields = 12
        completed_fields = 0
        
        if user_profile.age is not None:
            completed_fields += 1
        if user_profile.gender is not None:
            completed_fields += 1
        if user_profile.income is not None:
            completed_fields += 1
        if user_profile.location:
            completed_fields += 1
        if user_profile.education_level is not None:
            completed_fields += 1
        if user_profile.employment_status is not None:
            completed_fields += 1
        if user_profile.caste_category is not None:
            completed_fields += 1
        if user_profile.disability_status is not None:
            completed_fields += 1
        if user_profile.marital_status is not None:
            completed_fields += 1
        if user_profile.family_size is not None:
            completed_fields += 1
        if user_profile.land_ownership is not None:
            completed_fields += 1
        if user_profile.housing_status is not None:
            completed_fields += 1
        
        return completed_fields / total_fields
    
    def _get_recent_interaction_categories(self, user_profile: UserProfile) -> Set[str]:
        """Get categories from recent interactions."""
        categories = set()
        for interaction in user_profile.interaction_history:
            if self._is_recent_interaction(interaction):
                category = interaction.get('category')
                if category:
                    categories.add(category)
        return categories
    
    def _get_successful_application_categories(self, user_profile: UserProfile) -> Set[str]:
        """Get categories where user had successful applications."""
        categories = set()
        for interaction in user_profile.interaction_history:
            if interaction.get('outcome') == 'approved':
                category = interaction.get('category')
                if category:
                    categories.add(category)
        return categories
    
    def _get_high_engagement_categories(self, user_profile: UserProfile) -> Set[str]:
        """Get categories where user spent significant time."""
        categories = set()
        for interaction in user_profile.interaction_history:
            if interaction.get('engagement_time', 0) > 300:  # 5 minutes
                category = interaction.get('category')
                if category:
                    categories.add(category)
        return categories