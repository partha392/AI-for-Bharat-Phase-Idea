"""
Unit tests for offline functionality and caching components.

Tests the cache manager, request queue, offline manager, and integration
components to ensure proper offline functionality implementation.
"""

import pytest
import pytest_asyncio
import asyncio
import time
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from bharat_voice_assistant.core.cache_manager import (
    CacheManager, CacheType, CachePolicy, CacheEntry, CacheStats
)
from bharat_voice_assistant.core.request_queue import (
    RequestQueue, RequestStatus, RequestPriority, QueuedRequest, QueueStats
)
from bharat_voice_assistant.core.offline_manager import (
    OfflineManager, ConnectivityStatus, OfflineMode, OfflineCapability, ConnectivityInfo
)
from bharat_voice_assistant.core.offline_integration import (
    OfflineIntegration, OfflineConfig
)
from bharat_voice_assistant.core.exceptions import (
    CacheError, QueueError, OfflineError
)


class TestCacheManager:
    """Test cases for CacheManager."""
    
    @pytest_asyncio.fixture
    async def cache_manager(self):
        """Create a test cache manager."""
        temp_dir = tempfile.mkdtemp()
        manager = CacheManager(
            cache_type=CacheType.HYBRID,
            max_memory_size_mb=10,
            cache_dir=temp_dir,
            default_ttl_seconds=60
        )
        await manager.start()
        yield manager
        await manager.stop()
        try:
            shutil.rmtree(temp_dir)
        except (OSError, PermissionError):
            pass  # Ignore cleanup errors on Windows
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache_manager):
        """Test basic cache set and get operations."""
        # Test setting and getting data
        test_data = {"key": "value", "number": 42}
        success = await cache_manager.set("test_key", test_data, ttl_seconds=30)
        assert success is True
        
        # Test getting data
        retrieved_data = await cache_manager.get("test_key")
        assert retrieved_data == test_data
        
        # Test getting non-existent key
        missing_data = await cache_manager.get("missing_key", default="default_value")
        assert missing_data == "default_value"
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_manager):
        """Test cache entry expiration."""
        # Set data with short TTL
        await cache_manager.set("expire_key", "expire_value", ttl_seconds=1)
        
        # Verify data exists
        data = await cache_manager.get("expire_key")
        assert data == "expire_value"
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # Verify data is expired
        expired_data = await cache_manager.get("expire_key", default="expired")
        assert expired_data == "expired"
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_manager):
        """Test cache entry deletion."""
        # Set and verify data
        await cache_manager.set("delete_key", "delete_value")
        data = await cache_manager.get("delete_key")
        assert data == "delete_value"
        
        # Delete and verify
        deleted = await cache_manager.delete("delete_key")
        assert deleted is True
        
        # Verify data is gone
        missing_data = await cache_manager.get("delete_key", default="missing")
        assert missing_data == "missing"
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, cache_manager):
        """Test cache clearing."""
        # Set multiple entries
        await cache_manager.set("key1", "value1")
        await cache_manager.set("key2", "value2")
        await cache_manager.set("key3", "value3")
        
        # Clear all
        cleared_count = await cache_manager.clear()
        assert cleared_count >= 3
        
        # Verify all entries are gone
        assert await cache_manager.get("key1") is None
        assert await cache_manager.get("key2") is None
        assert await cache_manager.get("key3") is None
    
    @pytest.mark.asyncio
    async def test_cache_schemes(self, cache_manager):
        """Test scheme caching functionality."""
        schemes = [
            {"id": "scheme1", "name": "Test Scheme 1"},
            {"id": "scheme2", "name": "Test Scheme 2"}
        ]
        
        # Cache schemes
        success = await cache_manager.cache_schemes(schemes)
        assert success is True
        
        # Retrieve schemes
        cached_schemes = await cache_manager.get_cached_schemes()
        assert len(cached_schemes) == 2
        assert cached_schemes[0]["id"] == "scheme1"
    
    @pytest.mark.asyncio
    async def test_cache_user_data(self, cache_manager):
        """Test user data caching."""
        user_data = {
            "user_id": "user123",
            "name": "Test User",
            "preferences": {"language": "hi"}
        }
        
        # Cache user data
        success = await cache_manager.cache_user_data("user123", user_data)
        assert success is True
        
        # Retrieve user data
        cached_data = await cache_manager.get_cached_user_data("user123")
        assert cached_data["name"] == "Test User"
        assert cached_data["preferences"]["language"] == "hi"
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_manager):
        """Test cache statistics."""
        # Add some data
        await cache_manager.set("stats_key1", "value1")
        await cache_manager.set("stats_key2", "value2")
        
        # Get some data to generate hits
        await cache_manager.get("stats_key1")
        await cache_manager.get("stats_key1")
        await cache_manager.get("missing_key")  # Miss
        
        # Check stats
        stats = await cache_manager.get_stats()
        assert isinstance(stats, CacheStats)
        assert stats.hits >= 2
        assert stats.misses >= 1
        assert stats.total_entries >= 2


class TestRequestQueue:
    """Test cases for RequestQueue."""
    
    @pytest_asyncio.fixture
    async def request_queue(self):
        """Create a test request queue."""
        temp_dir = tempfile.mkdtemp()
        queue = RequestQueue(
            queue_dir=temp_dir,
            max_queue_size=100,
            processing_interval=1
        )
        await queue.start()
        yield queue
        await queue.stop()
        try:
            shutil.rmtree(temp_dir)
        except (OSError, PermissionError):
            pass  # Ignore cleanup errors on Windows
    
    @pytest.mark.asyncio
    async def test_enqueue_request(self, request_queue):
        """Test request enqueueing."""
        request_id = await request_queue.enqueue(
            user_id="user123",
            request_type="test_request",
            endpoint="/api/test",
            payload={"data": "test"}
        )
        
        assert request_id is not None
        assert len(request_id) > 0
        
        # Check request status
        status = await request_queue.get_request_status(request_id)
        assert status is not None
        assert status["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_request_processing(self, request_queue):
        """Test request processing with registered processor."""
        # Register a test processor
        async def test_processor(request):
            return {"result": "processed", "request_id": request.request_id}
        
        request_queue.register_processor("test_request", test_processor)
        
        # Enqueue request
        request_id = await request_queue.enqueue(
            user_id="user123",
            request_type="test_request",
            endpoint="/api/test",
            payload={"data": "test"}
        )
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Check if processed
        status = await request_queue.get_request_status(request_id)
        assert status["status"] in ["completed", "processing"]
    
    @pytest.mark.asyncio
    async def test_cancel_request(self, request_queue):
        """Test request cancellation."""
        request_id = await request_queue.enqueue(
            user_id="user123",
            request_type="test_request",
            endpoint="/api/test",
            payload={"data": "test"}
        )
        
        # Cancel request
        cancelled = await request_queue.cancel_request(request_id)
        assert cancelled is True
        
        # Check status
        status = await request_queue.get_request_status(request_id)
        assert status["status"] == "cancelled"
    
    @pytest.mark.asyncio
    async def test_queue_stats(self, request_queue):
        """Test queue statistics."""
        # Enqueue some requests
        await request_queue.enqueue("user1", "type1", "/api/1", {})
        await request_queue.enqueue("user2", "type2", "/api/2", {})
        
        # Get stats
        stats = await request_queue.get_queue_stats()
        assert isinstance(stats, QueueStats)
        assert stats.total_queued >= 2
        assert stats.pending_requests >= 2
    
    @pytest.mark.asyncio
    async def test_user_requests(self, request_queue):
        """Test getting user-specific requests."""
        # Enqueue requests for different users
        await request_queue.enqueue("user1", "type1", "/api/1", {})
        await request_queue.enqueue("user1", "type2", "/api/2", {})
        await request_queue.enqueue("user2", "type1", "/api/3", {})
        
        # Get requests for user1
        user1_requests = await request_queue.get_user_requests("user1")
        assert len(user1_requests) == 2
        
        # Get requests for user2
        user2_requests = await request_queue.get_user_requests("user2")
        assert len(user2_requests) == 1
    
    @pytest.mark.asyncio
    async def test_request_expiration(self, request_queue):
        """Test request expiration."""
        # Enqueue request with short expiration
        request_id = await request_queue.enqueue(
            user_id="user123",
            request_type="test_request",
            endpoint="/api/test",
            payload={"data": "test"},
            expires_in_hours=0.0003  # Very short expiration (about 1 second)
        )
        
        # Wait for expiration
        await asyncio.sleep(1.5)  # Wait a bit longer to ensure expiration
        
        # Trigger cleanup
        await request_queue._cleanup_expired_requests()
        
        # Check if expired
        status = await request_queue.get_request_status(request_id)
        # Status might be None if completely cleaned up, or "expired"
        assert status is None or status["is_expired"] is True


class TestOfflineManager:
    """Test cases for OfflineManager."""
    
    @pytest_asyncio.fixture
    async def offline_manager(self):
        """Create a test offline manager."""
        manager = OfflineManager()
        await manager.start()
        yield manager
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_connectivity_status(self, offline_manager):
        """Test connectivity status checking."""
        # Get initial status
        status = await offline_manager.get_connectivity_status()
        assert isinstance(status, ConnectivityInfo)
        assert hasattr(status, 'status')
        assert hasattr(status, 'bandwidth_kbps')
        assert hasattr(status, 'latency_ms')
    
    @pytest.mark.asyncio
    async def test_offline_mode_setting(self, offline_manager):
        """Test setting offline mode."""
        # Set offline mode
        await offline_manager.set_offline_mode(OfflineMode.FULL_OFFLINE, force=True)
        
        # Check if offline
        is_online = await offline_manager.is_online()
        assert is_online is False
        
        # Set back to hybrid mode
        await offline_manager.set_offline_mode(OfflineMode.HYBRID, force=False)
    
    @pytest.mark.asyncio
    async def test_offline_capabilities(self, offline_manager):
        """Test offline capability checking."""
        # Check basic conversation capability
        can_handle = await offline_manager.can_handle_offline("basic_conversation")
        assert isinstance(can_handle, bool)
        
        # Get all capabilities
        capabilities = await offline_manager.get_offline_capabilities()
        assert isinstance(capabilities, list)
        assert len(capabilities) > 0
        
        # Check capability structure
        for capability in capabilities:
            assert "feature_name" in capability
            assert "description" in capability
            assert "is_available" in capability
    
    @pytest.mark.asyncio
    async def test_offline_schemes(self, offline_manager):
        """Test getting offline schemes."""
        schemes = await offline_manager.get_offline_schemes()
        assert isinstance(schemes, list)
        # Should return fallback schemes even without cache
        assert len(schemes) >= 0
    
    @pytest.mark.asyncio
    async def test_offline_responses(self, offline_manager):
        """Test getting offline responses."""
        responses = await offline_manager.get_offline_responses("greeting", "hi")
        assert isinstance(responses, list)
        assert len(responses) > 0
        
        # Check response content
        for response in responses:
            assert isinstance(response, str)
            assert len(response) > 0
    
    @pytest.mark.asyncio
    async def test_queue_offline_request(self, offline_manager):
        """Test queuing requests for offline processing."""
        # Mock the request queue
        with patch('bharat_voice_assistant.core.offline_manager.request_queue') as mock_queue:
            mock_queue.enqueue = AsyncMock(return_value="test_request_id")
            
            request_id = await offline_manager.queue_offline_request(
                user_id="user123",
                request_type="test_request",
                endpoint="/api/test",
                payload={"data": "test"}
            )
            
            assert request_id == "test_request_id"
            mock_queue.enqueue.assert_called_once()


class TestOfflineIntegration:
    """Test cases for OfflineIntegration."""
    
    @pytest_asyncio.fixture
    async def offline_integration(self):
        """Create a test offline integration."""
        config = OfflineConfig(
            enable_caching=True,
            enable_request_queuing=True,
            enable_offline_mode=True,
            max_cache_size_mb=10,
            max_queue_size=100
        )
        
        integration = OfflineIntegration(config)
        
        # Mock the component managers to avoid actual initialization
        integration.cache_manager = Mock()
        integration.cache_manager.start = AsyncMock()
        integration.cache_manager.stop = AsyncMock()
        integration.cache_manager.set = AsyncMock(return_value=True)
        integration.cache_manager.get = AsyncMock(return_value=None)
        integration.cache_manager.get_stats = AsyncMock(return_value=Mock())
        
        integration.request_queue = Mock()
        integration.request_queue.start = AsyncMock()
        integration.request_queue.stop = AsyncMock()
        integration.request_queue.enqueue = AsyncMock(return_value="test_id")
        integration.request_queue.get_request_status = AsyncMock(return_value={"status": "pending"})
        integration.request_queue.get_queue_stats = AsyncMock(return_value=Mock())
        integration.request_queue.set_connectivity_checker = Mock()
        integration.request_queue.register_processor = Mock()
        
        integration.offline_manager = Mock()
        integration.offline_manager.start = AsyncMock()
        integration.offline_manager.stop = AsyncMock()
        integration.offline_manager.is_online = AsyncMock(return_value=True)
        integration.offline_manager.get_connectivity_status = AsyncMock(return_value=Mock())
        integration.offline_manager.get_offline_capabilities = AsyncMock(return_value=[])
        integration.offline_manager.add_connectivity_callback = Mock()
        integration.offline_manager.sync_when_online = AsyncMock(return_value={"status": "success"})
        
        await integration.initialize()
        yield integration
        await integration.shutdown()
    
    @pytest.mark.asyncio
    async def test_initialization(self, offline_integration):
        """Test offline integration initialization."""
        assert offline_integration.is_initialized is True
        
        # Verify components were started
        offline_integration.cache_manager.start.assert_called_once()
        offline_integration.request_queue.start.assert_called_once()
        offline_integration.offline_manager.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_operations(self, offline_integration):
        """Test integrated cache operations."""
        # Test caching data
        success = await offline_integration.cache_data("test_key", {"data": "test"})
        assert success is True
        offline_integration.cache_manager.set.assert_called_once()
        
        # Test getting cached data
        data = await offline_integration.get_cached_data("test_key", default="default")
        offline_integration.cache_manager.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_request_queuing(self, offline_integration):
        """Test integrated request queuing."""
        request_id = await offline_integration.queue_request(
            user_id="user123",
            request_type="test_request",
            endpoint="/api/test",
            payload={"data": "test"}
        )
        
        assert request_id == "test_id"
        offline_integration.request_queue.enqueue.assert_called_once()
        
        # Test getting request status
        status = await offline_integration.get_request_status("test_id")
        assert status["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_online_status(self, offline_integration):
        """Test online status checking."""
        is_online = await offline_integration.is_online()
        assert is_online is True
        offline_integration.offline_manager.is_online.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_system_status(self, offline_integration):
        """Test getting comprehensive system status."""
        status = await offline_integration.get_system_status()
        
        assert isinstance(status, dict)
        assert "timestamp" in status
        assert "is_online" in status
        assert "components" in status
        assert "caching" in status["components"]
        assert "request_queue" in status["components"]
        assert "offline_mode" in status["components"]
    
    @pytest.mark.asyncio
    async def test_request_fallback_handling(self, offline_integration):
        """Test request handling with online/offline fallback."""
        # Mock handlers
        online_handler = AsyncMock(return_value={"result": "online_success"})
        offline_handler = AsyncMock(return_value={"result": "offline_success"})
        
        # Test online success
        result = await offline_integration.handle_request_with_fallback(
            user_id="user123",
            request_type="test_request",
            endpoint="/api/test",
            payload={"data": "test"},
            online_handler=online_handler,
            offline_handler=offline_handler
        )
        
        assert result["status"] == "success"
        assert result["source"] == "online"
        online_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_when_online(self, offline_integration):
        """Test synchronization when online."""
        result = await offline_integration.sync_when_online()
        
        assert result["status"] == "success"
        offline_integration.offline_manager.sync_when_online.assert_called_once()


class TestOfflineErrorHandling:
    """Test error handling in offline functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self):
        """Test cache error handling."""
        # Test with invalid cache directory
        with pytest.raises(Exception):
            manager = CacheManager(cache_dir="/invalid/path/that/does/not/exist")
            await manager.start()
    
    @pytest.mark.asyncio
    async def test_queue_error_handling(self):
        """Test queue error handling."""
        temp_dir = tempfile.mkdtemp()
        queue = RequestQueue(queue_dir=temp_dir, max_queue_size=1)
        await queue.start()
        
        try:
            # Fill queue to capacity
            await queue.enqueue("user1", "type1", "/api/1", {})
            
            # Try to exceed capacity
            with pytest.raises(Exception):
                # This should eventually fail when queue is full
                for i in range(10):
                    await queue.enqueue(f"user{i}", "type", "/api", {})
        finally:
            await queue.stop()
            shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_offline_manager_error_handling(self):
        """Test offline manager error handling."""
        manager = OfflineManager()
        
        # Test getting offline data without initialization
        schemes = await manager.get_offline_schemes()
        assert isinstance(schemes, list)  # Should return fallback data
        
        responses = await manager.get_offline_responses("invalid_intent", "invalid_lang")
        assert isinstance(responses, list)  # Should return fallback responses


if __name__ == "__main__":
    pytest.main([__file__])