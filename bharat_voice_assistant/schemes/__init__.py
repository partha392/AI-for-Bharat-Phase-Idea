"""
Government scheme discovery and management module.

This module provides comprehensive functionality for managing government schemes,
including automated ingestion from government sources, intelligent categorization,
intelligent matching based on user profiles, and version control for scheme information.
"""

from .scheme_manager import SchemeManager
from .scheme_ingestion import SchemeIngestionService
from .scheme_categorizer import SchemeCategorizer
from .scheme_validator import SchemeValidator
from .database_manager import SchemeDatabaseManager
from .scheme_matcher import IntelligentSchemeMatcher, UserProfile, MatchScore
from .scheme_discovery import SchemeDiscoveryService, DiscoveryQuery, SchemeRecommendation
from .user_profile import UserProfileManager, InteractionRecord, LocationInfo, DemographicInfo, EconomicInfo
from .eligibility_assessor import EligibilityAssessor, EligibilityStatus, DocumentStatus, EligibilityAssessment
from .models import GovernmentScheme, SchemeCategory, SchemeStatus

__all__ = [
    "SchemeManager",
    "SchemeIngestionService", 
    "SchemeCategorizer",
    "SchemeValidator",
    "SchemeDatabaseManager",
    "IntelligentSchemeMatcher",
    "SchemeDiscoveryService",
    "UserProfileManager",
    "EligibilityAssessor",
    "GovernmentScheme",
    "SchemeCategory",
    "SchemeStatus",
    "UserProfile",
    "MatchScore",
    "DiscoveryQuery",
    "SchemeRecommendation",
    "InteractionRecord",
    "LocationInfo",
    "DemographicInfo",
    "EconomicInfo",
    "EligibilityStatus",
    "DocumentStatus",
    "EligibilityAssessment"
]