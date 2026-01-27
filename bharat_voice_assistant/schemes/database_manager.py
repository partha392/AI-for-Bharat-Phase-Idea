"""
Government scheme database management system.

This module provides comprehensive database management for government schemes,
including automated ingestion, categorization, tagging, update validation,
and version control.
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from uuid import UUID, uuid4
from decimal import Decimal

import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine, text, and_, or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .models import (
    GovernmentScheme, SchemeCategory, SchemeStatus, DataSource,
    SchemeUpdateResult, IngestionResult, SchemeMetadata
)
from .scheme_validator import SchemeValidator
from .scheme_categorizer import SchemeCategorizer
from .scheme_ingestion import SchemeIngestionService
from ..core.config import config
from ..core.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)


class SchemeDatabaseManager:
    """
    Comprehensive database manager for government schemes.
    
    Provides functionality for:
    - Automated ingestion from government sources
    - Intelligent categorization and tagging
    - Update validation and version control
    - Search and filtering capabilities
    - Performance monitoring and optimization
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize the database manager.
        
        Args:
            database_url: Database connection URL (optional, uses config if not provided)
        """
        self.database_url = database_url or self._build_database_url()
        self.validator = SchemeValidator()
        self.categorizer = SchemeCategorizer()
        self.ingestion_service = SchemeIngestionService()
        
        # Database connections
        self.engine = create_engine(self.database_url, pool_size=10, max_overflow=20)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Connection pool for async operations
        self.pool = None
        
        # Performance metrics
        self.metrics = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'last_ingestion': None,
            'schemes_processed': 0
        }
    
    async def initialize(self):
        """Initialize async database connections."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {str(e)}")
            raise DatabaseError(f"Database initialization failed: {str(e)}")
    
    async def close(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def ingest_schemes_from_sources(self) -> IngestionResult:
        """
        Perform automated ingestion from all configured government sources.
        
        Returns:
            Comprehensive ingestion result with statistics
        """
        start_time = datetime.now()
        logger.info("Starting automated scheme ingestion from government sources")
        
        try:
            # Initialize ingestion service
            async with self.ingestion_service as ingestion:
                # Get schemes from all sources
                ingestion_result = await ingestion.ingest_from_all_sources()
                
                # Process each ingested scheme
                processed_schemes = []
                for source_name, source_config in ingestion.ingestion_sources.items():
                    try:
                        # Get schemes from this source
                        source_result = await ingestion.ingest_from_source(source_name)
                        
                        # Process and save schemes
                        for scheme_data in source_result.validation_errors:  # This would be scheme data in real implementation
                            try:
                                # Create scheme object
                                scheme = self._create_scheme_from_ingestion_data(scheme_data, source_name)
                                
                                # Auto-categorize and tag
                                await self._auto_categorize_and_tag(scheme)
                                
                                # Validate scheme
                                is_valid, errors = self.validator.validate_scheme(scheme)
                                if not is_valid:
                                    logger.warning(f"Scheme validation failed for {scheme.scheme_id}: {errors}")
                                    ingestion_result.failed_updates += 1
                                    continue
                                
                                # Check for existing scheme and handle updates
                                existing_scheme = await self.get_scheme_by_id(scheme.scheme_id)
                                if existing_scheme:
                                    # Update existing scheme
                                    update_result = await self._handle_scheme_update(existing_scheme, scheme)
                                    if update_result.success:
                                        ingestion_result.updated_schemes += 1
                                        processed_schemes.append(scheme)
                                    else:
                                        ingestion_result.failed_updates += 1
                                else:
                                    # Create new scheme
                                    success = await self._save_new_scheme(scheme)
                                    if success:
                                        ingestion_result.new_schemes += 1
                                        processed_schemes.append(scheme)
                                    else:
                                        ingestion_result.failed_updates += 1
                                
                                ingestion_result.successful_updates += 1
                                
                            except Exception as e:
                                logger.error(f"Error processing scheme from {source_name}: {str(e)}")
                                ingestion_result.failed_updates += 1
                    
                    except Exception as e:
                        logger.error(f"Error ingesting from source {source_name}: {str(e)}")
                        ingestion_result.failed_updates += 1
                
                # Update ingestion statistics
                ingestion_result.processing_time_seconds = (datetime.now() - start_time).total_seconds()
                await self._update_ingestion_metrics(ingestion_result)
                
                logger.info(f"Completed scheme ingestion: {ingestion_result.new_schemes} new, "
                           f"{ingestion_result.updated_schemes} updated, "
                           f"{ingestion_result.failed_updates} failed")
                
                return ingestion_result
        
        except Exception as e:
            logger.error(f"Error during automated scheme ingestion: {str(e)}")
            raise DatabaseError(f"Ingestion failed: {str(e)}")
    
    async def categorize_and_tag_scheme(self, scheme_id: str) -> Tuple[bool, List[str]]:
        """
        Automatically categorize and tag a scheme.
        
        Args:
            scheme_id: ID of the scheme to categorize
            
        Returns:
            Tuple of (success, list_of_tags_applied)
        """
        try:
            # Get the scheme
            scheme = await self.get_scheme_by_id(scheme_id)
            if not scheme:
                return False, []
            
            # Auto-categorize and tag
            await self._auto_categorize_and_tag(scheme)
            
            # Update the scheme in database
            success = await self._update_scheme_in_database(scheme)
            
            if success:
                logger.info(f"Successfully categorized and tagged scheme {scheme_id}")
                return True, scheme.metadata.tags
            else:
                return False, []
        
        except Exception as e:
            logger.error(f"Error categorizing scheme {scheme_id}: {str(e)}")
            return False, []
    
    async def validate_scheme_update(self, scheme_id: str, update_data: Dict[str, Any]) -> SchemeUpdateResult:
        """
        Validate and apply scheme updates with version control.
        
        Args:
            scheme_id: ID of the scheme to update
            update_data: Dictionary containing update data
            
        Returns:
            Update result with validation details and version information
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
            
            # Create updated scheme
            updated_scheme = self._apply_updates_to_scheme(existing_scheme, update_data)
            
            # Validate the update
            is_valid, errors, changes = self.validator.validate_scheme_update(existing_scheme, updated_scheme)
            if not is_valid:
                return SchemeUpdateResult(
                    success=False,
                    scheme_id=scheme_id,
                    validation_errors=errors
                )
            
            # Apply version control
            await self._apply_version_control(updated_scheme, existing_scheme, changes)
            
            # Save updated scheme
            success = await self._update_scheme_in_database(updated_scheme)
            
            if success:
                # Archive previous version
                await self._archive_scheme_version(existing_scheme)
                
                logger.info(f"Successfully updated scheme {scheme_id} to version {updated_scheme.metadata.version}")
                
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
            logger.error(f"Error validating scheme update for {scheme_id}: {str(e)}")
            return SchemeUpdateResult(
                success=False,
                scheme_id=scheme_id,
                validation_errors=[f"Internal error: {str(e)}"]
            )
    
    async def get_scheme_by_id(self, scheme_id: str) -> Optional[GovernmentScheme]:
        """
        Retrieve a scheme by its ID.
        
        Args:
            scheme_id: The scheme ID to look up
            
        Returns:
            The government scheme or None if not found
        """
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT * FROM government_schemes 
                    WHERE scheme_id = $1 AND is_active = true
                """
                row = await conn.fetchrow(query, scheme_id)
                
                if row:
                    return self._row_to_scheme(dict(row))
                return None
        
        except Exception as e:
            logger.error(f"Error retrieving scheme {scheme_id}: {str(e)}")
            return None
    
    async def search_schemes(self, 
                           query: str = None,
                           category: SchemeCategory = None,
                           state: str = None,
                           tags: List[str] = None,
                           limit: int = 50) -> List[GovernmentScheme]:
        """
        Search schemes with various filters.
        
        Args:
            query: Text search query
            category: Scheme category filter
            state: State filter
            tags: Tags filter
            limit: Maximum number of results
            
        Returns:
            List of matching schemes
        """
        try:
            async with self.pool.acquire() as conn:
                # Build dynamic query
                conditions = ["is_active = true"]
                params = []
                param_count = 0
                
                if query:
                    param_count += 1
                    conditions.append(f"(name ILIKE ${param_count} OR description ILIKE ${param_count})")
                    params.append(f"%{query}%")
                
                if category:
                    param_count += 1
                    conditions.append(f"category = ${param_count}")
                    params.append(category.value)
                
                if state:
                    param_count += 1
                    conditions.append(f"target_states ? ${param_count}")
                    params.append(state)
                
                if tags:
                    for tag in tags:
                        param_count += 1
                        conditions.append(f"eligibility_criteria->'tags' ? ${param_count}")
                        params.append(tag)
                
                param_count += 1
                params.append(limit)
                
                sql_query = f"""
                    SELECT * FROM government_schemes 
                    WHERE {' AND '.join(conditions)}
                    ORDER BY created_at DESC
                    LIMIT ${param_count}
                """
                
                rows = await conn.fetch(sql_query, *params)
                
                return [self._row_to_scheme(dict(row)) for row in rows]
        
        except Exception as e:
            logger.error(f"Error searching schemes: {str(e)}")
            return []
    
    async def get_scheme_versions(self, scheme_id: str) -> List[Dict[str, Any]]:
        """
        Get version history for a scheme.
        
        Args:
            scheme_id: The scheme ID
            
        Returns:
            List of version information
        """
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT version, created_at, change_log 
                    FROM scheme_versions 
                    WHERE scheme_id = $1 
                    ORDER BY version DESC
                """
                rows = await conn.fetch(query, scheme_id)
                
                return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"Error retrieving scheme versions for {scheme_id}: {str(e)}")
            return []
    
    async def get_database_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive database statistics.
        
        Returns:
            Dictionary with various statistics
        """
        try:
            async with self.pool.acquire() as conn:
                # Total schemes
                total_schemes = await conn.fetchval("SELECT COUNT(*) FROM government_schemes WHERE is_active = true")
                
                # Schemes by category
                category_stats = await conn.fetch("""
                    SELECT category, COUNT(*) as count 
                    FROM government_schemes 
                    WHERE is_active = true 
                    GROUP BY category
                """)
                
                # Recent ingestion stats
                recent_ingestions = await conn.fetch("""
                    SELECT data_source, COUNT(*) as count, MAX(created_at) as last_update
                    FROM government_schemes 
                    WHERE created_at > NOW() - INTERVAL '30 days'
                    GROUP BY data_source
                """)
                
                return {
                    'total_schemes': total_schemes,
                    'schemes_by_category': {row['category']: row['count'] for row in category_stats},
                    'recent_ingestions': [dict(row) for row in recent_ingestions],
                    'last_update': datetime.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"Error retrieving database statistics: {str(e)}")
            return {}
    
    async def _auto_categorize_and_tag(self, scheme: GovernmentScheme):
        """Automatically categorize and tag a scheme."""
        try:
            # Auto-categorize if needed
            if not scheme.category or scheme.category == SchemeCategory.SOCIAL_SECURITY:
                category, confidence, tags = self.categorizer.categorize_scheme(scheme)
                scheme.category = category
                scheme.metadata.tags = tags
                logger.info(f"Auto-categorized scheme {scheme.scheme_id} as {category.value} with confidence {confidence:.2f}")
            
            # Generate comprehensive tags
            comprehensive_tags = self.categorizer.generate_comprehensive_tags(scheme)
            scheme.metadata.tags = list(set(scheme.metadata.tags + comprehensive_tags))
            
        except Exception as e:
            logger.error(f"Error auto-categorizing scheme {scheme.scheme_id}: {str(e)}")
    
    async def _handle_scheme_update(self, existing_scheme: GovernmentScheme, new_scheme: GovernmentScheme) -> SchemeUpdateResult:
        """Handle updating an existing scheme."""
        try:
            # Validate the update
            is_valid, errors, changes = self.validator.validate_scheme_update(existing_scheme, new_scheme)
            if not is_valid:
                return SchemeUpdateResult(
                    success=False,
                    scheme_id=new_scheme.scheme_id,
                    validation_errors=errors
                )
            
            # Apply version control
            await self._apply_version_control(new_scheme, existing_scheme, changes)
            
            # Update in database
            success = await self._update_scheme_in_database(new_scheme)
            
            if success:
                # Archive previous version
                await self._archive_scheme_version(existing_scheme)
                
                return SchemeUpdateResult(
                    success=True,
                    scheme_id=new_scheme.scheme_id,
                    changes_detected=changes,
                    previous_version=existing_scheme.metadata.version,
                    new_version=new_scheme.metadata.version
                )
            else:
                return SchemeUpdateResult(
                    success=False,
                    scheme_id=new_scheme.scheme_id,
                    validation_errors=["Failed to update scheme in database"]
                )
        
        except Exception as e:
            logger.error(f"Error handling scheme update: {str(e)}")
            return SchemeUpdateResult(
                success=False,
                scheme_id=new_scheme.scheme_id,
                validation_errors=[f"Internal error: {str(e)}"]
            )
    
    async def _save_new_scheme(self, scheme: GovernmentScheme) -> bool:
        """Save a new scheme to the database."""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO government_schemes (
                        id, scheme_id, name, name_hi, name_regional, department, ministry,
                        category, subcategory, description, description_hi, description_regional,
                        eligibility_criteria, benefits, required_documents, application_process,
                        target_states, target_districts, is_active, launch_date, end_date,
                        budget_allocated, beneficiaries_target, beneficiaries_current,
                        success_rate, average_processing_days, data_source, last_verified_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                        $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28
                    )
                """
                
                await conn.execute(
                    query,
                    scheme.id, scheme.scheme_id, scheme.name, scheme.name_hi,
                    json.dumps(scheme.name_regional), scheme.department, scheme.ministry,
                    scheme.category.value, scheme.subcategory, scheme.description,
                    scheme.description_hi, json.dumps(scheme.description_regional),
                    json.dumps(scheme.eligibility_criteria.__dict__),
                    json.dumps(scheme.benefits.__dict__),
                    json.dumps(scheme.application_process.required_documents),
                    json.dumps(scheme.application_process.__dict__),
                    json.dumps(scheme.target_states), json.dumps(scheme.target_districts),
                    scheme.status == SchemeStatus.ACTIVE, scheme.launch_date, scheme.end_date,
                    scheme.budget_allocated, scheme.beneficiaries_target, scheme.beneficiaries_current,
                    scheme.metadata.success_rate, scheme.average_processing_days,
                    scheme.metadata.data_source.value, scheme.metadata.last_verified_at
                )
                
                return True
        
        except Exception as e:
            logger.error(f"Error saving new scheme {scheme.scheme_id}: {str(e)}")
            return False
    
    async def _update_scheme_in_database(self, scheme: GovernmentScheme) -> bool:
        """Update an existing scheme in the database."""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    UPDATE government_schemes SET
                        name = $2, name_hi = $3, name_regional = $4, department = $5,
                        ministry = $6, category = $7, subcategory = $8, description = $9,
                        description_hi = $10, description_regional = $11,
                        eligibility_criteria = $12, benefits = $13, required_documents = $14,
                        application_process = $15, target_states = $16, target_districts = $17,
                        is_active = $18, launch_date = $19, end_date = $20,
                        budget_allocated = $21, beneficiaries_target = $22,
                        beneficiaries_current = $23, success_rate = $24,
                        average_processing_days = $25, last_verified_at = $26,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE scheme_id = $1
                """
                
                await conn.execute(
                    query,
                    scheme.scheme_id, scheme.name, scheme.name_hi,
                    json.dumps(scheme.name_regional), scheme.department, scheme.ministry,
                    scheme.category.value, scheme.subcategory, scheme.description,
                    scheme.description_hi, json.dumps(scheme.description_regional),
                    json.dumps(scheme.eligibility_criteria.__dict__),
                    json.dumps(scheme.benefits.__dict__),
                    json.dumps(scheme.application_process.required_documents),
                    json.dumps(scheme.application_process.__dict__),
                    json.dumps(scheme.target_states), json.dumps(scheme.target_districts),
                    scheme.status == SchemeStatus.ACTIVE, scheme.launch_date, scheme.end_date,
                    scheme.budget_allocated, scheme.beneficiaries_target, scheme.beneficiaries_current,
                    scheme.metadata.success_rate, scheme.average_processing_days,
                    scheme.metadata.last_verified_at
                )
                
                return True
        
        except Exception as e:
            logger.error(f"Error updating scheme {scheme.scheme_id}: {str(e)}")
            return False
    
    async def _apply_version_control(self, new_scheme: GovernmentScheme, old_scheme: GovernmentScheme, changes: List[str]):
        """Apply version control to scheme updates."""
        try:
            # Increment version
            new_scheme.metadata.version = old_scheme.metadata.version + 1
            new_scheme.updated_at = datetime.now()
            
            # Add change log entry
            change_entry = {
                'version': new_scheme.metadata.version,
                'timestamp': datetime.now().isoformat(),
                'changes': changes,
                'updated_by': 'automated_ingestion',
                'change_summary': f"Updated {len(changes)} fields: {', '.join(changes[:5])}"
            }
            
            new_scheme.metadata.change_log.append(change_entry)
            
            # Keep only last 10 change log entries
            if len(new_scheme.metadata.change_log) > 10:
                new_scheme.metadata.change_log = new_scheme.metadata.change_log[-10:]
            
        except Exception as e:
            logger.error(f"Error applying version control: {str(e)}")
    
    async def _archive_scheme_version(self, scheme: GovernmentScheme):
        """Archive a scheme version for history tracking."""
        try:
            async with self.pool.acquire() as conn:
                # Create scheme_versions table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS scheme_versions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        scheme_id VARCHAR(50) NOT NULL,
                        version INTEGER NOT NULL,
                        scheme_data JSONB NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(scheme_id, version)
                    )
                """)
                
                # Insert version record
                await conn.execute("""
                    INSERT INTO scheme_versions (scheme_id, version, scheme_data)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (scheme_id, version) DO NOTHING
                """, scheme.scheme_id, scheme.metadata.version, json.dumps(scheme.to_dict()))
                
        except Exception as e:
            logger.error(f"Error archiving scheme version: {str(e)}")
    
    def _create_scheme_from_ingestion_data(self, data: Dict[str, Any], source_name: str) -> GovernmentScheme:
        """Create a GovernmentScheme from ingestion data."""
        # This would normally parse the ingestion data format
        # For now, assume data is already in the correct format
        return GovernmentScheme.from_dict(data)
    
    def _apply_updates_to_scheme(self, existing_scheme: GovernmentScheme, update_data: Dict[str, Any]) -> GovernmentScheme:
        """Apply updates to an existing scheme."""
        # Convert existing scheme to dict, apply updates, and create new scheme
        scheme_dict = existing_scheme.to_dict()
        scheme_dict.update(update_data)
        return GovernmentScheme.from_dict(scheme_dict)
    
    def _row_to_scheme(self, row: Dict[str, Any]) -> GovernmentScheme:
        """Convert database row to GovernmentScheme object."""
        try:
            # Parse JSON fields
            name_regional = json.loads(row.get('name_regional', '{}')) if row.get('name_regional') else {}
            description_regional = json.loads(row.get('description_regional', '{}')) if row.get('description_regional') else {}
            eligibility_criteria = json.loads(row.get('eligibility_criteria', '{}'))
            benefits = json.loads(row.get('benefits', '{}'))
            application_process = json.loads(row.get('application_process', '{}'))
            target_states = json.loads(row.get('target_states', '[]')) if row.get('target_states') else []
            target_districts = json.loads(row.get('target_districts', '[]')) if row.get('target_districts') else []
            
            # Create scheme data dictionary
            scheme_data = {
                'id': str(row['id']),
                'scheme_id': row['scheme_id'],
                'name': row['name'],
                'name_hi': row.get('name_hi'),
                'name_regional': name_regional,
                'department': row['department'],
                'ministry': row.get('ministry'),
                'category': row['category'],
                'subcategory': row.get('subcategory'),
                'description': row['description'],
                'description_hi': row.get('description_hi'),
                'description_regional': description_regional,
                'eligibility_criteria': eligibility_criteria,
                'benefits': benefits,
                'application_process': application_process,
                'target_states': target_states,
                'target_districts': target_districts,
                'status': 'active' if row.get('is_active', True) else 'inactive',
                'launch_date': row.get('launch_date').isoformat() if row.get('launch_date') else None,
                'end_date': row.get('end_date').isoformat() if row.get('end_date') else None,
                'budget_allocated': float(row['budget_allocated']) if row.get('budget_allocated') else None,
                'beneficiaries_target': row.get('beneficiaries_target'),
                'beneficiaries_current': row.get('beneficiaries_current', 0),
                'average_processing_days': row.get('average_processing_days'),
                'metadata': {
                    'data_source': row.get('data_source', 'manual_entry'),
                    'last_verified_at': row.get('last_verified_at').isoformat() if row.get('last_verified_at') else None,
                    'success_rate': float(row.get('success_rate', 0.0)),
                    'version': 1,  # Default version
                    'change_log': [],
                    'tags': []
                },
                'created_at': row.get('created_at').isoformat() if row.get('created_at') else datetime.now().isoformat(),
                'updated_at': row.get('updated_at').isoformat() if row.get('updated_at') else datetime.now().isoformat()
            }
            
            return GovernmentScheme.from_dict(scheme_data)
        
        except Exception as e:
            logger.error(f"Error converting row to scheme: {str(e)}")
            raise DatabaseError(f"Failed to convert database row to scheme: {str(e)}")
    
    def _build_database_url(self) -> str:
        """Build database URL from configuration."""
        try:
            from ..core.config import config
            db_config = config.database
            return f"postgresql://{db_config.username}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.database}"
        except ImportError:
            # Fallback for testing
            return "postgresql://postgres:password@localhost:5432/bharat_voice_assistant"
    
    async def _update_ingestion_metrics(self, result: IngestionResult):
        """Update ingestion metrics."""
        try:
            self.metrics['last_ingestion'] = datetime.now()
            self.metrics['schemes_processed'] += result.total_processed
            self.metrics['successful_operations'] += result.successful_updates
            self.metrics['failed_operations'] += result.failed_updates
            self.metrics['total_operations'] += result.total_processed
            
            # Store metrics in database
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO system_metrics (metric_name, metric_value, dimensions)
                    VALUES ($1, $2, $3)
                """, 'scheme_ingestion_result', result.successful_updates, json.dumps({
                    'total_processed': result.total_processed,
                    'new_schemes': result.new_schemes,
                    'updated_schemes': result.updated_schemes,
                    'failed_updates': result.failed_updates,
                    'processing_time': result.processing_time_seconds
                }))
        
        except Exception as e:
            logger.error(f"Error updating ingestion metrics: {str(e)}")