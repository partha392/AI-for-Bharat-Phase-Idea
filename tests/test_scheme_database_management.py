"""
Unit tests for government scheme database management.

Tests the automated ingestion, categorization, tagging, update validation,
and version control functionality for government schemes.
"""

import pytest
import asyncio
import json
from datetime import datetime, date
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4

from bharat_voice_assistant.schemes.database_manager import SchemeDatabaseManager
from bharat_voice_assistant.schemes.models import (
    GovernmentScheme, SchemeCategory, SchemeStatus, DataSource,
    EligibilityCriteria, SchemeBenefits, ApplicationProcess,
    SchemeMetadata, IngestionResult, SchemeUpdateResult
)
from bharat_voice_assistant.core.exceptions import DatabaseError, ValidationError


class TestSchemeDatabaseManager:
    """Test suite for SchemeDatabaseManager."""
    
    @pytest.fixture
    def database_manager(self):
        """Create a database manager instance for testing."""
        with patch('bharat_voice_assistant.schemes.database_manager.asyncpg.create_pool'):
            manager = SchemeDatabaseManager("postgresql://test:test@localhost/test")
            
            # Create proper async context manager mock
            mock_conn = AsyncMock()
            
            # Create an async context manager that returns the connection
            class MockAcquire:
                def __init__(self, conn):
                    self.conn = conn
                
                async def __aenter__(self):
                    return self.conn
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return None
            
            mock_pool = AsyncMock()
            mock_pool.acquire = Mock(return_value=MockAcquire(mock_conn))
            
            manager.pool = mock_pool
            # Store reference to mock connection for easy access in tests
            manager._test_mock_conn = mock_conn
            return manager
    
    @pytest.fixture
    def sample_scheme(self):
        """Create a sample government scheme for testing."""
        return GovernmentScheme(
            scheme_id="test-scheme-001",
            name="Test Scheme",
            name_hi="परीक्षण योजना",
            department="Test Department",
            category=SchemeCategory.AGRICULTURE,
            description="A test scheme for unit testing",
            eligibility_criteria=EligibilityCriteria(
                income_limit=200000,
                age_min=18,
                age_max=60,
                location_type="rural"
            ),
            benefits=SchemeBenefits(
                financial_assistance=50000,
                description="Financial assistance for testing"
            ),
            application_process=ApplicationProcess(
                steps=["Step 1", "Step 2", "Step 3"],
                required_documents=["aadhaar_card", "income_certificate"],
                processing_time_days=30
            ),
            target_states=["MH", "UP"],
            metadata=SchemeMetadata(
                data_source=DataSource.GOVERNMENT_API,
                source_url="https://test.gov.in/scheme",
                version=1
            )
        )
    
    @pytest.fixture
    def sample_ingestion_result(self):
        """Create a sample ingestion result for testing."""
        return IngestionResult(
            total_processed=10,
            successful_updates=8,
            failed_updates=2,
            new_schemes=5,
            updated_schemes=3,
            processing_time_seconds=45.5,
            source="test_source"
        )
    
    @pytest.mark.asyncio
    async def test_initialize_database_manager(self, database_manager):
        """Test database manager initialization."""
        with patch('bharat_voice_assistant.schemes.database_manager.asyncpg.create_pool') as mock_pool:
            # Create an async mock that can be awaited
            async def mock_create_pool(*args, **kwargs):
                return AsyncMock()
            
            mock_pool.side_effect = mock_create_pool
            
            await database_manager.initialize()
            
            assert database_manager.pool is not None
            mock_pool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_database_manager(self, database_manager):
        """Test database manager cleanup."""
        database_manager.pool = AsyncMock()
        
        await database_manager.close()
        
        database_manager.pool.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ingest_schemes_from_sources_success(self, database_manager, sample_ingestion_result):
        """Test successful scheme ingestion from sources."""
        # Mock the ingestion service
        mock_ingestion_service = AsyncMock()
        mock_ingestion_service.ingest_from_all_sources.return_value = sample_ingestion_result
        mock_ingestion_service.ingestion_sources = {"test_source": {"type": "api"}}
        
        # Mock the async context manager for ingestion service
        mock_ingestion_service.__aenter__ = AsyncMock(return_value=mock_ingestion_service)
        mock_ingestion_service.__aexit__ = AsyncMock(return_value=None)
        
        with patch.object(database_manager, 'ingestion_service', mock_ingestion_service):
            with patch.object(database_manager, '_update_ingestion_metrics', new_callable=AsyncMock):
                result = await database_manager.ingest_schemes_from_sources()
                
                assert isinstance(result, IngestionResult)
                assert result.total_processed == 10
                assert result.successful_updates == 8
                assert result.failed_updates == 2
    
    @pytest.mark.asyncio
    async def test_ingest_schemes_from_sources_failure(self, database_manager):
        """Test scheme ingestion failure handling."""
        mock_ingestion_service = AsyncMock()
        mock_ingestion_service.ingest_from_all_sources.side_effect = Exception("Ingestion failed")
        
        with patch.object(database_manager, 'ingestion_service', mock_ingestion_service):
            with pytest.raises(DatabaseError, match="Ingestion failed"):
                await database_manager.ingest_schemes_from_sources()
    
    @pytest.mark.asyncio
    async def test_categorize_and_tag_scheme_success(self, database_manager, sample_scheme):
        """Test successful scheme categorization and tagging."""
        # Mock database operations
        mock_conn = database_manager._test_mock_conn
        mock_conn.fetchrow.return_value = {
            'id': str(sample_scheme.id),
            'scheme_id': sample_scheme.scheme_id,
            'name': sample_scheme.name,
            'department': sample_scheme.department,
            'category': sample_scheme.category.value,
            'description': sample_scheme.description,
            'eligibility_criteria': json.dumps(sample_scheme.eligibility_criteria.__dict__),
            'benefits': json.dumps(sample_scheme.benefits.__dict__),
            'application_process': json.dumps(sample_scheme.application_process.__dict__),
            'target_states': json.dumps(sample_scheme.target_states),
            'target_districts': json.dumps([]),
            'is_active': True,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        with patch.object(database_manager, '_update_scheme_in_database', return_value=True):
            with patch.object(database_manager, '_auto_categorize_and_tag', new_callable=AsyncMock):
                success, tags = await database_manager.categorize_and_tag_scheme(sample_scheme.scheme_id)
                
                assert success is True
                assert isinstance(tags, list)
    
    @pytest.mark.asyncio
    async def test_categorize_and_tag_scheme_not_found(self, database_manager):
        """Test categorization when scheme is not found."""
        mock_conn = database_manager._test_mock_conn
        mock_conn.fetchrow.return_value = None
        
        success, tags = await database_manager.categorize_and_tag_scheme("nonexistent-scheme")
        
        assert success is False
        assert tags == []
    
    @pytest.mark.asyncio
    async def test_validate_scheme_update_success(self, database_manager, sample_scheme):
        """Test successful scheme update validation."""
        # Mock existing scheme retrieval
        with patch.object(database_manager, 'get_scheme_by_id', return_value=sample_scheme):
            with patch.object(database_manager.validator, 'validate_scheme_update') as mock_validate:
                mock_validate.return_value = (True, [], ['name', 'description'])
                
                with patch.object(database_manager, '_apply_version_control', new_callable=AsyncMock):
                    with patch.object(database_manager, '_update_scheme_in_database', return_value=True):
                        with patch.object(database_manager, '_archive_scheme_version', new_callable=AsyncMock):
                            
                            update_data = {'name': 'Updated Test Scheme'}
                            result = await database_manager.validate_scheme_update(sample_scheme.scheme_id, update_data)
                            
                            assert result.success is True
                            assert result.scheme_id == sample_scheme.scheme_id
                            assert 'name' in result.changes_detected
    
    @pytest.mark.asyncio
    async def test_validate_scheme_update_not_found(self, database_manager):
        """Test scheme update validation when scheme is not found."""
        with patch.object(database_manager, 'get_scheme_by_id', return_value=None):
            result = await database_manager.validate_scheme_update("nonexistent", {})
            
            assert result.success is False
            assert "not found" in result.validation_errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_scheme_update_validation_failure(self, database_manager, sample_scheme):
        """Test scheme update validation failure."""
        with patch.object(database_manager, 'get_scheme_by_id', return_value=sample_scheme):
            with patch.object(database_manager.validator, 'validate_scheme_update') as mock_validate:
                mock_validate.return_value = (False, ['Invalid data'], [])
                
                result = await database_manager.validate_scheme_update(sample_scheme.scheme_id, {})
                
                assert result.success is False
                assert 'Invalid data' in result.validation_errors
    
    @pytest.mark.asyncio
    async def test_get_scheme_by_id_success(self, database_manager, sample_scheme):
        """Test successful scheme retrieval by ID."""
        # Mock database response
        mock_row = {
            'id': str(sample_scheme.id),
            'scheme_id': sample_scheme.scheme_id,
            'name': sample_scheme.name,
            'name_hi': sample_scheme.name_hi,
            'name_regional': json.dumps(sample_scheme.name_regional),
            'department': sample_scheme.department,
            'ministry': sample_scheme.ministry,
            'category': sample_scheme.category.value,
            'subcategory': sample_scheme.subcategory,
            'description': sample_scheme.description,
            'description_hi': sample_scheme.description_hi,
            'description_regional': json.dumps(sample_scheme.description_regional),
            'eligibility_criteria': json.dumps(sample_scheme.eligibility_criteria.__dict__),
            'benefits': json.dumps(sample_scheme.benefits.__dict__),
            'application_process': json.dumps(sample_scheme.application_process.__dict__),
            'target_states': json.dumps(sample_scheme.target_states),
            'target_districts': json.dumps(sample_scheme.target_districts),
            'is_active': True,
            'launch_date': sample_scheme.launch_date,
            'end_date': sample_scheme.end_date,
            'budget_allocated': sample_scheme.budget_allocated,
            'beneficiaries_target': sample_scheme.beneficiaries_target,
            'beneficiaries_current': sample_scheme.beneficiaries_current,
            'success_rate': sample_scheme.metadata.success_rate,
            'average_processing_days': sample_scheme.average_processing_days,
            'data_source': sample_scheme.metadata.data_source.value,
            'last_verified_at': sample_scheme.metadata.last_verified_at,
            'created_at': sample_scheme.created_at,
            'updated_at': sample_scheme.updated_at
        }
        
        mock_conn = database_manager._test_mock_conn
        mock_conn.fetchrow.return_value = mock_row
        
        result = await database_manager.get_scheme_by_id(sample_scheme.scheme_id)
        
        assert result is not None
        assert result.scheme_id == sample_scheme.scheme_id
        assert result.name == sample_scheme.name
        assert result.category == sample_scheme.category
    
    @pytest.mark.asyncio
    async def test_get_scheme_by_id_not_found(self, database_manager):
        """Test scheme retrieval when scheme is not found."""
        # Get the mock connection from the acquire context manager
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.fetchrow.return_value = None
        
        result = await database_manager.get_scheme_by_id("nonexistent-scheme")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_search_schemes_with_query(self, database_manager, sample_scheme):
        """Test scheme search with text query."""
        # Mock database response
        mock_rows = [{
            'id': str(sample_scheme.id),
            'scheme_id': sample_scheme.scheme_id,
            'name': sample_scheme.name,
            'department': sample_scheme.department,
            'category': sample_scheme.category.value,
            'description': sample_scheme.description,
            'eligibility_criteria': json.dumps(sample_scheme.eligibility_criteria.__dict__),
            'benefits': json.dumps(sample_scheme.benefits.__dict__),
            'application_process': json.dumps(sample_scheme.application_process.__dict__),
            'target_states': json.dumps(sample_scheme.target_states),
            'target_districts': json.dumps([]),
            'is_active': True,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }]
        
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.fetch.return_value = mock_rows
        
        results = await database_manager.search_schemes(query="test", limit=10)
        
        assert len(results) == 1
        assert results[0].scheme_id == sample_scheme.scheme_id
    
    @pytest.mark.asyncio
    async def test_search_schemes_with_filters(self, database_manager):
        """Test scheme search with category and state filters."""
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.fetch.return_value = []
        
        results = await database_manager.search_schemes(
            category=SchemeCategory.AGRICULTURE,
            state="MH",
            tags=["farming"],
            limit=20
        )
        
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_get_scheme_versions(self, database_manager):
        """Test retrieving scheme version history."""
        mock_versions = [
            {'version': 2, 'created_at': datetime.now(), 'change_log': []},
            {'version': 1, 'created_at': datetime.now(), 'change_log': []}
        ]
        
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.fetch.return_value = mock_versions
        
        versions = await database_manager.get_scheme_versions("test-scheme-001")
        
        assert len(versions) == 2
        assert versions[0]['version'] == 2
        assert versions[1]['version'] == 1
    
    @pytest.mark.asyncio
    async def test_get_database_statistics(self, database_manager):
        """Test retrieving database statistics."""
        # Mock database responses
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.fetchval.return_value = 100
        mock_conn.fetch.side_effect = [
            [{'category': 'agriculture', 'count': 25}, {'category': 'health', 'count': 30}],
            [{'data_source': 'government_api', 'count': 10, 'last_update': datetime.now()}]
        ]
        
        stats = await database_manager.get_database_statistics()
        
        assert stats['total_schemes'] == 100
        assert 'schemes_by_category' in stats
        assert 'recent_ingestions' in stats
        assert 'last_update' in stats
    
    @pytest.mark.asyncio
    async def test_auto_categorize_and_tag(self, database_manager, sample_scheme):
        """Test automatic categorization and tagging."""
        # Mock categorizer responses
        with patch.object(database_manager.categorizer, 'categorize_scheme') as mock_categorize:
            mock_categorize.return_value = (SchemeCategory.AGRICULTURE, 0.85, ['farming', 'rural'])
            
            with patch.object(database_manager.categorizer, 'generate_comprehensive_tags') as mock_tags:
                mock_tags.return_value = ['agriculture', 'subsidy', 'rural']
                
                await database_manager._auto_categorize_and_tag(sample_scheme)
                
                assert sample_scheme.category == SchemeCategory.AGRICULTURE
                # Check that tags from both categorizer methods are included
                assert 'agriculture' in sample_scheme.metadata.tags
                assert 'rural' in sample_scheme.metadata.tags
                assert 'subsidy' in sample_scheme.metadata.tags
    
    @pytest.mark.asyncio
    async def test_apply_version_control(self, database_manager, sample_scheme):
        """Test version control application."""
        old_scheme = sample_scheme
        new_scheme = GovernmentScheme.from_dict(sample_scheme.to_dict())
        new_scheme.name = "Updated Test Scheme"
        changes = ['name']
        
        await database_manager._apply_version_control(new_scheme, old_scheme, changes)
        
        assert new_scheme.metadata.version == old_scheme.metadata.version + 1
        assert len(new_scheme.metadata.change_log) > 0
        assert new_scheme.metadata.change_log[-1]['changes'] == changes
    
    @pytest.mark.asyncio
    async def test_archive_scheme_version(self, database_manager, sample_scheme):
        """Test scheme version archiving."""
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.execute = AsyncMock()
        
        await database_manager._archive_scheme_version(sample_scheme)
        
        # Verify that execute was called twice (CREATE TABLE and INSERT)
        assert mock_conn.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_save_new_scheme_success(self, database_manager, sample_scheme):
        """Test successful new scheme saving."""
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.execute = AsyncMock()
        
        result = await database_manager._save_new_scheme(sample_scheme)
        
        assert result is True
        mock_conn.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_new_scheme_failure(self, database_manager, sample_scheme):
        """Test new scheme saving failure."""
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.execute.side_effect = Exception("DB Error")
        
        result = await database_manager._save_new_scheme(sample_scheme)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_update_scheme_in_database_success(self, database_manager, sample_scheme):
        """Test successful scheme update in database."""
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.execute = AsyncMock()
        
        result = await database_manager._update_scheme_in_database(sample_scheme)
        
        assert result is True
        mock_conn.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_scheme_in_database_failure(self, database_manager, sample_scheme):
        """Test scheme update failure in database."""
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.execute.side_effect = Exception("DB Error")
        
        result = await database_manager._update_scheme_in_database(sample_scheme)
        
        assert result is False
    
    def test_row_to_scheme_conversion(self, database_manager, sample_scheme):
        """Test conversion of database row to GovernmentScheme object."""
        row = {
            'id': str(sample_scheme.id),
            'scheme_id': sample_scheme.scheme_id,
            'name': sample_scheme.name,
            'name_hi': sample_scheme.name_hi,
            'name_regional': json.dumps(sample_scheme.name_regional),
            'department': sample_scheme.department,
            'ministry': sample_scheme.ministry,
            'category': sample_scheme.category.value,
            'subcategory': sample_scheme.subcategory,
            'description': sample_scheme.description,
            'description_hi': sample_scheme.description_hi,
            'description_regional': json.dumps(sample_scheme.description_regional),
            'eligibility_criteria': json.dumps(sample_scheme.eligibility_criteria.__dict__),
            'benefits': json.dumps(sample_scheme.benefits.__dict__),
            'application_process': json.dumps(sample_scheme.application_process.__dict__),
            'target_states': json.dumps(sample_scheme.target_states),
            'target_districts': json.dumps(sample_scheme.target_districts),
            'is_active': True,
            'launch_date': sample_scheme.launch_date,
            'end_date': sample_scheme.end_date,
            'budget_allocated': sample_scheme.budget_allocated,
            'beneficiaries_target': sample_scheme.beneficiaries_target,
            'beneficiaries_current': sample_scheme.beneficiaries_current,
            'success_rate': sample_scheme.metadata.success_rate,
            'average_processing_days': sample_scheme.average_processing_days,
            'data_source': sample_scheme.metadata.data_source.value,
            'last_verified_at': sample_scheme.metadata.last_verified_at,
            'created_at': sample_scheme.created_at,
            'updated_at': sample_scheme.updated_at
        }
        
        result = database_manager._row_to_scheme(row)
        
        assert isinstance(result, GovernmentScheme)
        assert result.scheme_id == sample_scheme.scheme_id
        assert result.name == sample_scheme.name
        assert result.category == sample_scheme.category
        assert result.department == sample_scheme.department
    
    def test_row_to_scheme_conversion_error(self, database_manager):
        """Test error handling in row to scheme conversion."""
        invalid_row = {'invalid': 'data'}
        
        with pytest.raises(DatabaseError):
            database_manager._row_to_scheme(invalid_row)
    
    def test_build_database_url(self, database_manager):
        """Test database URL building from configuration."""
        # Patch the config import inside the method
        with patch('bharat_voice_assistant.core.config.config') as mock_config:
            # Create a mock config object with the expected attributes
            mock_config.database.username = "testuser"
            mock_config.database.password = "testpass"
            mock_config.database.host = "testhost"
            mock_config.database.port = 5432
            mock_config.database.database = "testdb"
            
            # Test the URL building method directly
            url = database_manager._build_database_url()
            
            assert "postgresql://testuser:testpass@testhost:5432/testdb" == url
    
    @pytest.mark.asyncio
    async def test_update_ingestion_metrics(self, database_manager, sample_ingestion_result):
        """Test ingestion metrics updating."""
        mock_acquire = database_manager.pool.acquire.return_value
        mock_conn = await mock_acquire.__aenter__()
        mock_conn.execute = AsyncMock()
        
        await database_manager._update_ingestion_metrics(sample_ingestion_result)
        
        assert database_manager.metrics['schemes_processed'] == sample_ingestion_result.total_processed
        assert database_manager.metrics['successful_operations'] == sample_ingestion_result.successful_updates
        assert database_manager.metrics['failed_operations'] == sample_ingestion_result.failed_updates
        
        # Verify metrics were stored in database
        mock_conn.execute.assert_called_once()


class TestSchemeDatabaseManagerIntegration:
    """Integration tests for SchemeDatabaseManager."""
    
    @pytest.mark.asyncio
    async def test_full_ingestion_workflow(self):
        """Test complete ingestion workflow from source to database."""
        # This would be an integration test that requires a test database
        # For now, we'll skip it in unit tests
        pytest.skip("Integration test requires test database")
    
    @pytest.mark.asyncio
    async def test_scheme_lifecycle_management(self):
        """Test complete scheme lifecycle from creation to archival."""
        # This would test the full lifecycle of a scheme
        # For now, we'll skip it in unit tests
        pytest.skip("Integration test requires test database")
    
    @pytest.mark.asyncio
    async def test_concurrent_scheme_updates(self):
        """Test handling of concurrent scheme updates."""
        # This would test race conditions and concurrent access
        # For now, we'll skip it in unit tests
        pytest.skip("Integration test requires test database")


if __name__ == "__main__":
    pytest.main([__file__])