"""
User profile management for scheme matching.

This module provides user profile models and management functionality
to support intelligent scheme matching based on demographics, location,
and interaction history.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from uuid import UUID, uuid4
import json

from .models import SchemeCategory
from ..core.exceptions import UserProfileError

logger = logging.getLogger(__name__)


@dataclass
class InteractionRecord:
    """Record of user interaction with a scheme."""
    scheme_id: str
    category: str
    action: str  # 'viewed', 'applied', 'bookmarked', 'shared'
    outcome: Optional[str] = None  # 'approved', 'rejected', 'pending', 'withdrawn'
    engagement_time: int = 0  # seconds spent
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LocationInfo:
    """User location information."""
    state: str
    district: str
    block: Optional[str] = None
    village: Optional[str] = None
    pincode: Optional[str] = None
    location_type: str = 'unknown'  # 'rural', 'urban', 'semi_urban'
    coordinates: Optional[Dict[str, float]] = None  # lat, lng


@dataclass
class DemographicInfo:
    """User demographic information."""
    age: Optional[int] = None
    gender: Optional[str] = None  # 'male', 'female', 'other'
    caste_category: Optional[str] = None  # 'general', 'obc', 'sc', 'st'
    religion: Optional[str] = None
    marital_status: Optional[str] = None  # 'single', 'married', 'divorced', 'widowed'
    family_size: Optional[int] = None
    dependents: Optional[int] = None
    disability_status: Optional[bool] = None
    disability_type: Optional[str] = None


@dataclass
class EconomicInfo:
    """User economic information."""
    income: Optional[int] = None  # annual income in INR
    income_source: Optional[str] = None  # 'agriculture', 'employment', 'business', 'pension'
    employment_status: Optional[str] = None  # 'employed', 'unemployed', 'self_employed', 'retired'
    occupation: Optional[str] = None
    land_ownership: Optional[str] = None  # 'landless', 'marginal', 'small', 'large'
    land_size: Optional[float] = None  # in hectares
    housing_status: Optional[str] = None  # 'owned', 'rented', 'homeless', 'inadequate'
    bank_account: bool = False
    ration_card_type: Optional[str] = None  # 'apl', 'bpl', 'aay'


@dataclass
class PreferenceInfo:
    """User preferences and settings."""
    preferred_language: str = 'hi'
    preferred_categories: List[SchemeCategory] = field(default_factory=list)
    notification_preferences: Dict[str, bool] = field(default_factory=dict)
    communication_mode: str = 'voice'  # 'voice', 'text', 'both'
    privacy_level: str = 'standard'  # 'minimal', 'standard', 'detailed'


class UserProfileManager:
    """
    Manager for user profiles and interaction history.
    
    Provides functionality to create, update, and retrieve user profiles
    for intelligent scheme matching.
    """
    
    def __init__(self):
        """Initialize the user profile manager."""
        self._profiles = {}  # In-memory storage for demo
        logger.info("Initialized UserProfileManager")
    
    async def create_profile(self, 
                           user_id: str,
                           location: LocationInfo,
                           demographics: Optional[DemographicInfo] = None,
                           economic: Optional[EconomicInfo] = None,
                           preferences: Optional[PreferenceInfo] = None) -> bool:
        """
        Create a new user profile.
        
        Args:
            user_id: Unique user identifier
            location: User location information
            demographics: User demographic information
            economic: User economic information
            preferences: User preferences
            
        Returns:
            True if profile created successfully
        """
        try:
            if user_id in self._profiles:
                logger.warning(f"Profile already exists for user {user_id}")
                return False
            
            profile = {
                'user_id': user_id,
                'location': location,
                'demographics': demographics or DemographicInfo(),
                'economic': economic or EconomicInfo(),
                'preferences': preferences or PreferenceInfo(),
                'interaction_history': [],
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'profile_version': 1
            }
            
            self._profiles[user_id] = profile
            logger.info(f"Created profile for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating profile for user {user_id}: {str(e)}")
            raise UserProfileError(f"Failed to create profile: {str(e)}")
    
    async def update_profile(self, 
                           user_id: str,
                           updates: Dict[str, Any]) -> bool:
        """
        Update an existing user profile.
        
        Args:
            user_id: User identifier
            updates: Dictionary of updates to apply
            
        Returns:
            True if profile updated successfully
        """
        try:
            if user_id not in self._profiles:
                logger.error(f"Profile not found for user {user_id}")
                return False
            
            profile = self._profiles[user_id]
            
            # Apply updates
            for key, value in updates.items():
                if key in ['location', 'demographics', 'economic', 'preferences']:
                    if hasattr(profile[key], '__dict__'):
                        # Update dataclass fields
                        for field_name, field_value in value.items():
                            setattr(profile[key], field_name, field_value)
                    else:
                        profile[key] = value
                elif key not in ['user_id', 'created_at', 'profile_version']:
                    profile[key] = value
            
            profile['updated_at'] = datetime.now()
            profile['profile_version'] += 1
            
            logger.info(f"Updated profile for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating profile for user {user_id}: {str(e)}")
            raise UserProfileError(f"Failed to update profile: {str(e)}")
    
    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile by ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            User profile dictionary or None if not found
        """
        try:
            return self._profiles.get(user_id)
            
        except Exception as e:
            logger.error(f"Error retrieving profile for user {user_id}: {str(e)}")
            return None
    
    async def record_interaction(self, 
                               user_id: str,
                               interaction: InteractionRecord) -> bool:
        """
        Record a user interaction with a scheme.
        
        Args:
            user_id: User identifier
            interaction: Interaction record
            
        Returns:
            True if interaction recorded successfully
        """
        try:
            if user_id not in self._profiles:
                logger.warning(f"Profile not found for user {user_id}, creating basic profile")
                # Create basic profile if it doesn't exist
                await self.create_profile(
                    user_id=user_id,
                    location=LocationInfo(state='unknown', district='unknown')
                )
            
            profile = self._profiles[user_id]
            profile['interaction_history'].append(interaction)
            profile['updated_at'] = datetime.now()
            
            # Keep only recent interactions (last 6 months)
            cutoff_date = datetime.now() - timedelta(days=180)
            profile['interaction_history'] = [
                interaction for interaction in profile['interaction_history']
                if interaction.timestamp > cutoff_date
            ]
            
            logger.debug(f"Recorded interaction for user {user_id}: {interaction.action} on {interaction.scheme_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording interaction for user {user_id}: {str(e)}")
            return False
    
    async def get_interaction_history(self, 
                                    user_id: str,
                                    days: int = 30) -> List[InteractionRecord]:
        """
        Get user interaction history.
        
        Args:
            user_id: User identifier
            days: Number of days to look back
            
        Returns:
            List of interaction records
        """
        try:
            profile = self._profiles.get(user_id)
            if not profile:
                return []
            
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_interactions = [
                interaction for interaction in profile['interaction_history']
                if interaction.timestamp > cutoff_date
            ]
            
            return recent_interactions
            
        except Exception as e:
            logger.error(f"Error retrieving interaction history for user {user_id}: {str(e)}")
            return []
    
    async def get_user_preferences(self, user_id: str) -> Optional[PreferenceInfo]:
        """
        Get user preferences.
        
        Args:
            user_id: User identifier
            
        Returns:
            User preferences or None if not found
        """
        try:
            profile = self._profiles.get(user_id)
            if profile:
                return profile['preferences']
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving preferences for user {user_id}: {str(e)}")
            return None
    
    async def update_preferences(self, 
                               user_id: str,
                               preferences: PreferenceInfo) -> bool:
        """
        Update user preferences.
        
        Args:
            user_id: User identifier
            preferences: Updated preferences
            
        Returns:
            True if preferences updated successfully
        """
        try:
            if user_id not in self._profiles:
                return False
            
            self._profiles[user_id]['preferences'] = preferences
            self._profiles[user_id]['updated_at'] = datetime.now()
            
            logger.info(f"Updated preferences for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating preferences for user {user_id}: {str(e)}")
            return False
    
    def get_profile_completeness(self, user_id: str) -> float:
        """
        Calculate profile completeness score.
        
        Args:
            user_id: User identifier
            
        Returns:
            Completeness score between 0.0 and 1.0
        """
        try:
            profile = self._profiles.get(user_id)
            if not profile:
                return 0.0
            
            total_fields = 0
            completed_fields = 0
            
            # Location fields
            location = profile['location']
            total_fields += 4
            if location.state and location.state != 'unknown':
                completed_fields += 1
            if location.district and location.district != 'unknown':
                completed_fields += 1
            if location.block:
                completed_fields += 1
            if location.location_type != 'unknown':
                completed_fields += 1
            
            # Demographics fields
            demographics = profile['demographics']
            total_fields += 6
            if demographics.age is not None:
                completed_fields += 1
            if demographics.gender is not None:
                completed_fields += 1
            if demographics.caste_category is not None:
                completed_fields += 1
            if demographics.marital_status is not None:
                completed_fields += 1
            if demographics.family_size is not None:
                completed_fields += 1
            if demographics.disability_status is not None:
                completed_fields += 1
            
            # Economic fields
            economic = profile['economic']
            total_fields += 6
            if economic.income is not None:
                completed_fields += 1
            if economic.employment_status is not None:
                completed_fields += 1
            if economic.occupation is not None:
                completed_fields += 1
            if economic.land_ownership is not None:
                completed_fields += 1
            if economic.housing_status is not None:
                completed_fields += 1
            if economic.ration_card_type is not None:
                completed_fields += 1
            
            return completed_fields / total_fields if total_fields > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating profile completeness for user {user_id}: {str(e)}")
            return 0.0