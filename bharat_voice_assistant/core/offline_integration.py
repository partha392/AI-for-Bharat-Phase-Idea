"""
Offline integration module for the Bharat Voice Assistant.

This module provides a unified interface for offline functionality,
integrating caching, request queuing, and offline features into
the main application components.

Implements Requirements 5.3, 5.4, and 5.5 integration.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import OfflineError, NetworkError
from bharat_voice_assistant.core.cache_manager import cache_manager, CacheType
from bharat_voice_assistant.core.request_queue import request_queue, RequestPriority, QueuedRequest
from bharat_voice_assistant.core.offline_manager import offline_manager, ConnectivityStatus, OfflineMode

logger = get_logger(__name__)


@dataclass
class OfflineConfig:
    """Configuration for offline functionality."""
    enable_caching: bool = True
    enable_request_queuing: bool = True
    enable_offline_mode: bool = True
    cache_type: CacheType = CacheType.HYBRID
    max_cache_size_mb: int = 100
    max_queue_size: int = 1000
    connectivity_check_interval: int = 30
    sync_interval: int = 60


class OfflineIntegration:
    """
    Unified interface for offline functionality integration.
    
    Coordinates caching, request queuing, and offline features
    across the entire application.
    """
    
    def __init__(self, offline_config: OfflineConfig = None):
        """
        Initialize offline integration.
        
        Args:
            offline_config: Configuration for offline functionality
        """
        self.config = offline_config or OfflineConfig()
        self.is_initialized = False
        
        # Component references
        self.cache_manager = cache_manager
        self.request_queue = request_queue
        self.offline_manager = offline_manager
        
        # Request processors
        self._request_processors: Dict[str, Callable] = {}
        
        logger.info("OfflineIntegration initialized")
    
    async def initialize(self):
        """Initialize all offline components."""
        try:
            if self.is_initialized:
                logger.warning("OfflineIntegration already initialized")
                return
            
            # Initialize cache manager
            if self.config.enable_caching:
                await self.cache_manager.start()
                logger.info("Cache manager started")
            
            # Initialize request queue
            if self.config.enable_request_queuing:
                await self.request_queue.start()
                
                # Register connectivity checker
                self.request_queue.set_connectivity_checker(self._check_connectivity)
                
                # Register default request processors
                self._register_default_processors()
                
                logger.info("Request queue started")
            
            # Initialize offline manager
            if self.config.enable_offline_mode:
                await self.offline_manager.start()
                
                # Register connectivity change callback
                self.offline_manager.add_connectivity_callback(self._on_connectivity_change)
                
                logger.info("Offline manager started")
            
            self.is_initialized = True
            logger.info("OfflineIntegration fully initialized")
            
        except Exception as e:
            logger.error(f"Error initializing offline integration: {e}")
            raise OfflineError(
                "Failed to initialize offline integration",
                error_code="INIT_FAILED",
                context={"error": str(e)}
            )
    
    async def shutdown(self):
        """Shutdown all offline components."""
        try:
            if not self.is_initialized:
                return
            
            # Shutdown components in reverse order
            if self.config.enable_offline_mode:
                await self.offline_manager.stop()
                logger.info("Offline manager stopped")
            
            if self.config.enable_request_queuing:
                await self.request_queue.stop()
                logger.info("Request queue stopped")
            
            if self.config.enable_caching:
                await self.cache_manager.stop()
                logger.info("Cache manager stopped")
            
            self.is_initialized = False
            logger.info("OfflineIntegration shutdown complete")
            
        except Exception as e:
            logger.error(f"Error shutting down offline integration: {e}")
    
    async def cache_data(self, key: str, data: Any, ttl_seconds: int = 3600,
                        metadata: Dict[str, Any] = None) -> bool:
        """
        Cache data with the integrated cache manager.
        
        Args:
            key: Cache key
            data: Data to cache
            ttl_seconds: Time to live
            metadata: Optional metadata
            
        Returns:
            True if cached successfully
        """
        if not self.config.enable_caching:
            return False
        
        try:
            return await self.cache_manager.set(key, data, ttl_seconds, metadata)
        except Exception as e:
            logger.error(f"Error caching data: {e}")
            return False
    
    async def get_cached_data(self, key: str, default: Any = None) -> Any:
        """
        Get cached data.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached data or default
        """
        if not self.config.enable_caching:
            return default
        
        try:
            return await self.cache_manager.get(key, default)
        except Exception as e:
            logger.error(f"Error getting cached data: {e}")
            return default
    
    async def queue_request(self, user_id: str, request_type: str, endpoint: str,
                          payload: Dict[str, Any], priority: RequestPriority = RequestPriority.MEDIUM,
                          max_retries: int = 3) -> Optional[str]:
        """
        Queue a request for processing.
        
        Args:
            user_id: User identifier
            request_type: Type of request
            endpoint: API endpoint
            payload: Request payload
            priority: Request priority
            max_retries: Maximum retry attempts
            
        Returns:
            Request ID if queued successfully, None otherwise
        """
        if not self.config.enable_request_queuing:
            return None
        
        try:
            return await self.request_queue.enqueue(
                user_id=user_id,
                request_type=request_type,
                endpoint=endpoint,
                payload=payload,
                priority=priority,
                max_retries=max_retries
            )
        except Exception as e:
            logger.error(f"Error queuing request: {e}")
            return None
    
    async def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a queued request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Request status or None
        """
        if not self.config.enable_request_queuing:
            return None
        
        try:
            return await self.request_queue.get_request_status(request_id)
        except Exception as e:
            logger.error(f"Error getting request status: {e}")
            return None
    
    async def is_online(self) -> bool:
        """
        Check if system is currently online.
        
        Returns:
            True if online, False if offline
        """
        if not self.config.enable_offline_mode:
            return True  # Assume online if offline mode is disabled
        
        try:
            return await self.offline_manager.is_online()
        except Exception as e:
            logger.error(f"Error checking online status: {e}")
            return False
    
    async def get_offline_schemes(self, user_profile: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get government schemes for offline use.
        
        Args:
            user_profile: Optional user profile for filtering
            
        Returns:
            List of schemes
        """
        if not self.config.enable_offline_mode:
            return []
        
        try:
            return await self.offline_manager.get_offline_schemes(user_profile)
        except Exception as e:
            logger.error(f"Error getting offline schemes: {e}")
            return []
    
    async def get_offline_responses(self, intent: str, language: str = "hi") -> List[str]:
        """
        Get response templates for offline use.
        
        Args:
            intent: Intent identifier
            language: Language code
            
        Returns:
            List of response templates
        """
        if not self.config.enable_offline_mode:
            return []
        
        try:
            return await self.offline_manager.get_offline_responses(intent, language)
        except Exception as e:
            logger.error(f"Error getting offline responses: {e}")
            return []
    
    async def can_handle_offline(self, feature_name: str) -> bool:
        """
        Check if a feature can be handled offline.
        
        Args:
            feature_name: Name of the feature
            
        Returns:
            True if feature is available offline
        """
        if not self.config.enable_offline_mode:
            return False
        
        try:
            return await self.offline_manager.can_handle_offline(feature_name)
        except Exception as e:
            logger.error(f"Error checking offline capability: {e}")
            return False
    
    async def sync_when_online(self) -> Dict[str, Any]:
        """
        Synchronize offline data when connection is restored.
        
        Returns:
            Sync results
        """
        if not self.config.enable_offline_mode:
            return {"status": "disabled", "message": "Offline mode is disabled"}
        
        try:
            return await self.offline_manager.sync_when_online()
        except Exception as e:
            logger.error(f"Error syncing offline data: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status including offline capabilities.
        
        Returns:
            System status information
        """
        try:
            status = {
                "timestamp": time.time(),
                "is_online": await self.is_online(),
                "components": {
                    "caching": {
                        "enabled": self.config.enable_caching,
                        "stats": await self.cache_manager.get_stats() if self.config.enable_caching else None
                    },
                    "request_queue": {
                        "enabled": self.config.enable_request_queuing,
                        "stats": await self.request_queue.get_queue_stats() if self.config.enable_request_queuing else None
                    },
                    "offline_mode": {
                        "enabled": self.config.enable_offline_mode,
                        "connectivity": await self.offline_manager.get_connectivity_status() if self.config.enable_offline_mode else None,
                        "capabilities": await self.offline_manager.get_offline_capabilities() if self.config.enable_offline_mode else []
                    }
                }
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "timestamp": time.time(),
                "error": str(e),
                "is_online": False
            }
    
    def register_request_processor(self, request_type: str, processor: Callable):
        """
        Register a processor for a specific request type.
        
        Args:
            request_type: Type of request to process
            processor: Async function to process the request
        """
        self._request_processors[request_type] = processor
        
        if self.config.enable_request_queuing:
            self.request_queue.register_processor(request_type, processor)
        
        logger.info(f"Registered request processor: {request_type}")
    
    async def handle_request_with_fallback(self, user_id: str, request_type: str,
                                         endpoint: str, payload: Dict[str, Any],
                                         online_handler: Callable, offline_handler: Callable = None,
                                         priority: RequestPriority = RequestPriority.MEDIUM) -> Dict[str, Any]:
        """
        Handle a request with automatic online/offline fallback.
        
        Args:
            user_id: User identifier
            request_type: Type of request
            endpoint: API endpoint
            payload: Request payload
            online_handler: Function to handle request when online
            offline_handler: Optional function to handle request when offline
            priority: Request priority
            
        Returns:
            Request result
        """
        try:
            is_online = await self.is_online()
            
            if is_online:
                # Try online handler first
                try:
                    result = await online_handler(payload)
                    return {
                        "status": "success",
                        "source": "online",
                        "result": result
                    }
                except Exception as e:
                    logger.warning(f"Online handler failed: {e}")
                    
                    # Queue for retry if online handler fails
                    if self.config.enable_request_queuing:
                        request_id = await self.queue_request(
                            user_id, request_type, endpoint, payload, priority
                        )
                        
                        if request_id:
                            logger.info(f"Request queued for retry: {request_id}")
            
            # Use offline handler if available
            if offline_handler and await self.can_handle_offline(request_type):
                try:
                    result = await offline_handler(payload)
                    return {
                        "status": "success",
                        "source": "offline",
                        "result": result
                    }
                except Exception as e:
                    logger.error(f"Offline handler failed: {e}")
            
            # Queue request if we can't handle it now
            if self.config.enable_request_queuing:
                request_id = await self.queue_request(
                    user_id, request_type, endpoint, payload, priority
                )
                
                if request_id:
                    return {
                        "status": "queued",
                        "source": "queue",
                        "request_id": request_id,
                        "message": "Request queued for processing when online"
                    }
            
            # Return error if no fallback available
            return {
                "status": "error",
                "source": "none",
                "message": "Unable to process request online or offline"
            }
            
        except Exception as e:
            logger.error(f"Error in request fallback handling: {e}")
            return {
                "status": "error",
                "source": "error",
                "message": str(e)
            }
    
    async def _check_connectivity(self) -> bool:
        """Check network connectivity for request queue."""
        try:
            return await self.offline_manager.is_online()
        except Exception as e:
            logger.error(f"Error checking connectivity: {e}")
            return False
    
    async def _on_connectivity_change(self, connectivity_info):
        """Handle connectivity status changes."""
        try:
            status = connectivity_info.status
            logger.info(f"Connectivity changed to: {status.value}")
            
            if status == ConnectivityStatus.ONLINE:
                # Trigger sync when coming back online
                asyncio.create_task(self.sync_when_online())
            
        except Exception as e:
            logger.error(f"Error handling connectivity change: {e}")
    
    def _register_default_processors(self):
        """Register default request processors."""
        # Grievance submission processor
        async def process_grievance_submission(request: QueuedRequest) -> Dict[str, Any]:
            try:
                # This would integrate with the actual grievance filing system
                logger.info(f"Processing grievance submission: {request.request_id}")
                
                # Simulate processing
                await asyncio.sleep(1)
                
                return {
                    "status": "submitted",
                    "reference_number": f"GRV{int(time.time())}",
                    "message": "Grievance submitted successfully"
                }
                
            except Exception as e:
                logger.error(f"Error processing grievance submission: {e}")
                raise
        
        # Status inquiry processor
        async def process_status_inquiry(request: QueuedRequest) -> Dict[str, Any]:
            try:
                logger.info(f"Processing status inquiry: {request.request_id}")
                
                # Simulate processing
                await asyncio.sleep(0.5)
                
                return {
                    "status": "in_progress",
                    "message": "Status inquiry processed"
                }
                
            except Exception as e:
                logger.error(f"Error processing status inquiry: {e}")
                raise
        
        # Register processors
        self.register_request_processor("grievance_submission", process_grievance_submission)
        self.register_request_processor("status_inquiry", process_status_inquiry)


# Global offline integration instance
offline_integration = OfflineIntegration()