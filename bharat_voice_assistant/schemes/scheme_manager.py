"""
Central scheme management system.

This module provides the main interface for managing government schemes,
including database operations, version control, and coordination between
ingestion, validation, and categorization services.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4
import json

import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .models import (
    GovernmentScheme, SchemeCategory, SchemeStatus, DataSource,
    SchemeUpdateResult, IngestionResult
)
from .scheme_validator import SchemeValidator
from .scheme_categorizer import SchemeCategorizer
from .scheme_ingestion import SchemeIngestionService
from .database_manager import SchemeDatabaseManager
from .scheme_matcher import IntelligentSchemeMatcher, UserProfile, MatchScore
from ..core.config import config
from ..core.exceptions import SchemeManagerError, ValidationError

logger = logging.getLogger(__name__)


class SchemeManager:
    """
    Central manager for government scheme operations.
    
    Provides comprehensive functionality for:
    - Scheme CRUD operations
    - Automated ingestion and updates
    - Version control and change tracking
    - Search and filtering
    - Performance monitoring
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize the scheme manager.
        
        Args:
            database_url: Database connection URL (optional, uses config if not provided)
        """
        self.database_url = database_url or self._get_database_url()
        self.validator = SchemeValidator()
        self.categorizer = SchemeCategorizer()
        self.ingestion_service = SchemeIngestionService()
        self.database_manager = SchemeDatabaseManager(database_url)
        self.matcher = IntelligentSchemeMatcher()
        
        # Initialize discovery service with lazy import to avoid circular dependency
        self.discovery_service = None
        
        # Database connection
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Performance metrics
        self.metrics = {
            'total_schemes': 0,
            'active_schemes': 0,
            'last_update': None,
            'ingestion_stats': {}
        }
    
    async def create_scheme(self, scheme: GovernmentScheme) -> Tuple[bool, List[str]]:
        """
        Create a new government scheme.
        
        Args:
            scheme: The government scheme to create
            
        Returns:
            Tuple of (success, list_of_errors)
        """
        try:
            # Validate scheme
            is_valid, errors = self.validator.validate_scheme(scheme)
            if not is_valid:
                return False, errors
            
            # Auto-categorize if needed
            if not scheme.category or scheme.category == SchemeCategory.SOCIAL_SECURITY:
                category, confidence, tags = self.categorizer.categorize_scheme(scheme)
                scheme.category = category
                scheme.metadata.tags = tags
                logger.info(f"Auto-categorized scheme {scheme.scheme_id} as {category.value} with confidence {confidence:.2f}")
            
            # Check for duplicates
            existing_scheme = await self.get_scheme_by_id(scheme.scheme_id)
            if existing_scheme:
                return False, [f"Scheme with ID {scheme.scheme_id} already exists"]
            
            # Save to database
            success = await self._save_scheme_to_db(scheme)
            if success:
                logger.info(f"Successfully created scheme: {scheme.scheme_id}")
                await self._update_metrics()
                return True, []
            else:
                return False, ["Failed to save scheme to database"]
        
        except Exception as e:
            logger.error(f"Error creating scheme {scheme.scheme_id}: {str(e)}")
            return False, [f"Internal error: {str(e)}"]
    
    async def update_scheme(self, scheme_id: str, updated_scheme: GovernmentScheme) -> SchemeUpdateResult:
        """
        Update an existing government scheme.
        
        Args:
            scheme_id: ID of the scheme to update
            updated_scheme: Updated scheme data
            
        Returns:
            SchemeUpdateResult with update details
        """
        try:
            # Get existing scheme
            existing_scheme = await self.get_scheme_by_id(scheme_id)
            if not existing_scheme:
                return SchemeUpdateResult(
                    success=False,
                    scheme_id=scheme_id,
                    validation_errors=[f"Scheme {scheme_id} not found"]
                )
            
            # Validate update
            is_valid, errors, changes = self.validator.validate_scheme_update(existing_scheme, updated_scheme)
            if not is_valid:
                return SchemeUpdateResult(
                    success=False,
                    scheme_id=scheme_id,
                    validation_errors=errors
                )
            
            # Update version and metadata
            updated_scheme.metadata.version = existing_scheme.metadata.version + 1
            updated_scheme.updated_at = datetime.now()
            
            # Add change log entry
            change_entry = {
                'version': updated_scheme.metadata.version,
                'timestamp': datetime.now().isoformat(),
                'changes': changes,
                'updated_by': 'system'  # This could be user ID in a real system
            }
            updated_scheme.metadata.change_log.append(change_entry)
            
            # Save updated scheme
            success = await self._update_scheme_in_db(updated_scheme)
            
            if success:
                logger.info(f"Successfully updated scheme {scheme_id} to version {updated_scheme.metadata.version}")
                await self._update_metrics()
                
                return SchemeUpdateResult(
                    success=True,
                    scheme_id=scheme_id,
                    changes_detected=changes,
                    previous_version=existing_scheme.metadata.version,
                    new_version=updated_scheme.metadata.version
                )
            else:
                return SchemeUpdateResult(
                    success=False,
                    scheme_id=scheme_id,
                    validation_errors=["Failed to save updated scheme to database"]
                )
        
        except Exception as e:
            logger.error(f"Error updating scheme {scheme_id}: {str(e)}")
            return SchemeUpdateResult(
                success=False,
                scheme_id=scheme_id,
                validation_errors=[f"Internal error: {str(e)}"]
            )
    
    async def get_scheme_by_id(self, scheme_id: str) -> Optional[GovernmentScheme]:
        """
        Get a scheme by its ID.
        
        Args:
            scheme_id: The scheme ID to look up
            
        Returns:
            The government scheme or None if not found
        """
        try:
            # This would normally query the database
            # For now, return None as a placeholder
            return None
        except Exception as e:
            logger.error(f"Error retrieving scheme {scheme_id}: {str(e)}")
            return None
    
    async def search_schemes(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[GovernmentScheme]:
        """
        Search for schemes based on query and filters.
        
        Args:
            query: Search query text
            filters: Optional filters (category, state, etc.)
            
        Returns:
            List of matching schemes
        """
        try:
            # This would normally perform database search
            # For now, return empty list as placeholder
            return []
        except Exception as e:
            logger.error(f"Error searching schemes: {str(e)}")
            return []
    
    async def get_schemes_by_category(self, category: SchemeCategory) -> List[GovernmentScheme]:
        """
        Get all schemes in a specific category.
        
        Args:
            category: The scheme category
            
        Returns:
            List of schemes in the category
        """
        try:
            # This would normally query the database
            return []
        except Exception as e:
            logger.error(f"Error retrieving schemes by category {category}: {str(e)}")
            return []
    
    async def ingest_schemes_from_sources(self) -> IngestionResult:
        """
        Trigger ingestion from all configured sources.
        
        Returns:
            Comprehensive ingestion result
        """
        try:
            # Initialize database manager if needed
            if not self.database_manager.pool:
                await self.database_manager.initialize()
            
            # Delegate to database manager
            result = await self.database_manager.ingest_schemes_from_sources()
            
            # Update local metrics
            await self._update_metrics()
            
            logger.info(f"Completed scheme ingestion: {result.successful_updates} successful, "
                       f"{result.failed_updates} failed")
            
            return result
        except Exception as e:
            logger.error(f"Error during scheme ingestion: {str(e)}")
            raise SchemeManagerError(f"Ingestion failed: {str(e)}")
    
    async def validate_and_update_scheme(self, scheme_id: str, new_data: Dict[str, Any]) -> SchemeUpdateResult:
        """
        Validate and update a scheme with new data.
        
        Args:
            scheme_id: ID of the scheme to update
            new_data: New scheme data
            
        Returns:
            Update result with validation details
        """
        try:
            # Get existing scheme
            existing_scheme = await self.get_scheme_by_id(scheme_id)
            if not existing_scheme:
                return SchemeUpdateResult(
                    success=False,
                    scheme_id=scheme_id,
                    validation_errors=[f"Scheme {scheme_id} not found"]
                )
            
            # Create updated scheme from new data
            updated_scheme = GovernmentScheme.from_dict({
                **existing_scheme.to_dict(),
                **new_data
            })
            
            # Perform update
            return await self.update_scheme(scheme_id, updated_scheme)
            
        except Exception as e:
            logger.error(f"Error validating and updating scheme {scheme_id}: {str(e)}")
            return SchemeUpdateResult(
                success=False,
                scheme_id=scheme_id,
                validation_errors=[f"Internal error: {str(e)}"]
            )
    
    async def get_scheme_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive scheme statistics.
        
        Returns:
            Dictionary with various statistics
        """
        try:
            # This would normally query the database for statistics
            return {
                'total_schemes': self.metrics.get('total_schemes', 0),
                'active_schemes': self.metrics.get('active_schemes', 0),
                'schemes_by_category': {},
                'last_update': self.metrics.get('last_update'),
                'ingestion_stats': self.metrics.get('ingestion_stats', {})
            }
        except Exception as e:
            logger.error(f"Error retrieving scheme statistics: {str(e)}")
            return {}
    
    async def discover_schemes_for_user(self, 
                                      user_id: str,
                                      query_text: str,
                                      language: str = 'hi',
                                      max_results: int = 10) -> Dict[str, Any]:
        """
        Discover relevant schemes for a user using intelligent matching.
        
        Args:
            user_id: User identifier
            query_text: Natural language query
            language: Query language
            max_results: Maximum number of results
            
        Returns:
            Discovery result with ranked recommendations
        """
        try:
            # Lazy initialization of discovery service to avoid circular import
            if self.discovery_service is None:
                from .scheme_discovery import SchemeDiscoveryService, DiscoveryQuery
                self.discovery_service = SchemeDiscoveryService(self)
            
            query = DiscoveryQuery(
                user_id=user_id,
                query_text=query_text,
                language=language,
                max_results=max_results
            )
            
            result = await self.discovery_service.discover_schemes(query)
            
            # Convert to dictionary format for API response
            return {
                'recommendations': [
                    {
                        'scheme': rec.scheme.to_dict(),
                        'match_score': rec.match_score.overall_score,
                        'rank': rec.rank,
                        'reason': rec.recommendation_reason,
                        'next_steps': rec.next_steps,
                        'estimated_benefit': rec.estimated_benefit,
                        'application_complexity': rec.application_complexity,
                        'eligibility_match': rec.match_score.eligibility_match,
                        'approval_likelihood': rec.match_score.approval_likelihood,
                        'explanation': rec.match_score.explanation
                    }
                    for rec in result.recommendations
                ],
                'total_considered': result.total_schemes_considered,
                'processing_time_ms': result.processing_time_ms,
                'personalization_applied': result.personalization_applied,
                'suggestions': result.suggestions
            }
            
        except Exception as e:
            logger.error(f"Error discovering schemes for user {user_id}: {str(e)}")
            raise SchemeManagerError(f"Scheme discovery failed: {str(e)}")
    
    async def get_personalized_recommendations(self, 
                                             user_id: str,
                                             max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Get personalized scheme recommendations for a user.
        
        Args:
            user_id: User identifier
            max_results: Maximum number of recommendations
            
        Returns:
            List of personalized recommendations
        """
        try:
            # Lazy initialization of discovery service to avoid circular import
            if self.discovery_service is None:
                from .scheme_discovery import SchemeDiscoveryService
                self.discovery_service = SchemeDiscoveryService(self)
            
            recommendations = await self.discovery_service.get_personalized_recommendations(
                user_id, max_results
            )
            
            return [
                {
                    'scheme': rec.scheme.to_dict(),
                    'match_score': rec.match_score.overall_score,
                    'rank': rec.rank,
                    'reason': rec.recommendation_reason,
                    'next_steps': rec.next_steps,
                    'estimated_benefit': rec.estimated_benefit,
                    'application_complexity': rec.application_complexity,
                    'eligibility_match': rec.match_score.eligibility_match,
                    'approval_likelihood': rec.match_score.approval_likelihood
                }
                for rec in recommendations
            ]
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations for user {user_id}: {str(e)}")
            return []
    
    async def match_schemes_to_profile(self, 
                                     user_profile: UserProfile,
                                     scheme_filters: Optional[Dict[str, Any]] = None,
                                     max_results: int = 10) -> List[Tuple[GovernmentScheme, MatchScore]]:
        """
        Match schemes to a user profile using intelligent algorithm.
        
        Args:
            user_profile: User profile for matching
            scheme_filters: Optional filters for schemes
            max_results: Maximum number of results
            
        Returns:
            List of tuples (scheme, match_score) sorted by relevance
        """
        try:
            # Get available schemes
            available_schemes = await self.search_schemes("", scheme_filters or {"status": "active"})
            
            # Apply intelligent matching
            match_results = await self.matcher.match_schemes(
                user_profile=user_profile,
                available_schemes=available_schemes,
                max_results=max_results
            )
            
            logger.info(f"Matched {len(match_results)} schemes to user profile")
            return match_results
            
        except Exception as e:
            logger.error(f"Error matching schemes to profile: {str(e)}")
            raise SchemeManagerError(f"Scheme matching failed: {str(e)}")
    
    async def _save_scheme_to_db(self, scheme: GovernmentScheme) -> bool:
        """Save a scheme to the database."""
        try:
            # This would normally save to the database
            # For now, return True as placeholder
            return True
        except Exception as e:
            logger.error(f"Error saving scheme to database: {str(e)}")
            return False
    
    async def _update_scheme_in_db(self, scheme: GovernmentScheme) -> bool:
        """Update a scheme in the database."""
        try:
            # This would normally update the database
            # For now, return True as placeholder
            return True
        except Exception as e:
            logger.error(f"Error updating scheme in database: {str(e)}")
            return False
    
    async def _update_metrics(self):
        """Update internal metrics."""
        try:
            # This would normally update metrics from database
            self.metrics['last_update'] = datetime.now()
        except Exception as e:
            logger.error(f"Error updating metrics: {str(e)}")
    
    def _get_database_url(self) -> str:
        """Get database URL from config or environment."""
        try:
            return config.get('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/bharat_voice_assistant')
        except:
            return 'postgresql://postgres:password@localhost:5432/bharat_voice_assistant'